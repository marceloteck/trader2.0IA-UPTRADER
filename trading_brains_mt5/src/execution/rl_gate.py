"""
Level 5: RL Policy Gate

Integra a política de aprendizado por reforço no fluxo de decisão.
Funciona como um "filtro de confiança" que pode:
- Permitir entrada normal (ENTER)
- Forçar entrada conservadora (ENTER_CONSERVATIVE)
- Permitir re-alavancagem (ENTER_WITH_REALAVANCAGEM)
- Bloquear entrada (HOLD)

O RL policy aprende quais ações funcionam melhor em cada regime.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

from ..config.settings import Settings
from ..brains.brain_interface import Decision
from ..features.regime_transition import RegimeState
from ..training.reinforcement_policy import RLPolicy, RLState
from ..execution.capital_manager import CapitalManager
from ..db import repo

logger = logging.getLogger("trading_brains.execution.rl_gate")


class RLGate:
    """
    Gate que aplica política de RL na decisão de entrada.
    
    Funcionalidades:
    - Seleciona ação (HOLD/ENTER/ENTER_CONSERVATIVE/ENTER_WITH_REALAVANCAGEM) via Thompson Sampling
    - Registra decisão no histórico
    - Modifica decisão do BossBrain baseado em RL
    - Integra com CapitalManager para validação de re-leverage
    """
    
    def __init__(
        self,
        settings: Settings,
        db_path: str,
        rl_policy: RLPolicy,
        capital_manager: CapitalManager,
    ):
        self.settings = settings
        self.db_path = db_path
        self.rl_policy = rl_policy
        self.capital_manager = capital_manager
        
        # Configurações de RL
        self.enabled = settings.rl_policy_enabled
        self.realavancagem_enabled = settings.realavancagem_enabled
    
    def apply_gate(
        self,
        boss_decision: Decision,
        regime: str,
        hour: int,
        global_confidence: float,
        ensemble_disagreement: float,
        liquidity_strength: float,
        symbol: str,
        current_price: float,
    ) -> Tuple[Decision, str, bool]:
        """
        Aplica o gate de RL na decisão do BossBrain.
        
        Args:
            boss_decision: Decisão original do BossBrain
            regime: Regime atual (TREND_UP, TREND_DOWN, etc)
            hour: Hora do dia (0-23)
            global_confidence: Confiança global do ensemble (0-1)
            ensemble_disagreement: Discordância entre cérebros (0-1)
            liquidity_strength: Força de liquidez (0-1)
            symbol: Símbolo sendo tradado
            current_price: Preço atual
        
        Returns:
            (modified_decision, rl_action, realavancagem_approved)
        """
        
        if not self.enabled:
            # RL desabilitado, passa decisão como está
            return boss_decision, "NO_RL", False
        
        # 1. Se BossBrain já bloqueou, respeita a decisão
        if boss_decision.action == "HOLD":
            return boss_decision, "HOLD", False
        
        # 2. Construir estado discretizado
        rl_state = RLState(
            regime=regime,
            time_bucket=f"{hour:02d}:00",
            confidence_level=self._discretize_confidence(global_confidence),
            disagreement_level=self._discretize_disagreement(ensemble_disagreement),
        )
        
        # 3. Selecionar ação via Thompson Sampling
        rl_action = self.rl_policy.select_action(regime, rl_state)
        
        logger.info(
            f"RL Gate: regime={regime}, state={rl_state.to_hash()}, "
            f"boss_action={boss_decision.action}, rl_action={rl_action}"
        )
        
        # 4. Aplicar lógica de RL
        realavancagem_approved = False
        modified_decision = boss_decision
        
        if rl_action == "HOLD":
            # RL disse para não entrar
            modified_decision = Decision(
                action="HOLD",
                entry=boss_decision.entry,
                sl=boss_decision.sl,
                tp1=boss_decision.tp1,
                tp2=boss_decision.tp2,
                size=0,
                reason=f"RL blocked: {rl_action}",
                contributors=boss_decision.contributors,
                metadata={**boss_decision.metadata, "rl_action": rl_action}
            )
            
        elif rl_action == "ENTER":
            # RL aprova entrada normal (sem alavancagem extra)
            modified_decision = boss_decision
            modified_decision.metadata["rl_action"] = rl_action
            
        elif rl_action == "ENTER_CONSERVATIVE":
            # RL aprova entrada mas conservadora (reduz posição)
            conservative_size = max(1, int(boss_decision.size * 0.75))
            modified_decision = Decision(
                action=boss_decision.action,
                entry=boss_decision.entry,
                sl=boss_decision.sl,
                tp1=boss_decision.tp1,
                tp2=boss_decision.tp2,
                size=conservative_size,
                reason=f"RL conservative: {rl_action}",
                contributors=boss_decision.contributors,
                metadata={**boss_decision.metadata, "rl_action": rl_action}
            )
            
        elif rl_action == "ENTER_WITH_REALAVANCAGEM":
            # RL aprova re-alavancagem (extra contratos)
            if self.realavancagem_enabled:
                # Validar permissão com CapitalManager
                can_realavanca, reason = self.capital_manager.can_realavancar(
                    regime=regime,
                    global_confidence=global_confidence,
                    ensemble_disagreement=ensemble_disagreement,
                    liquidity_strength=liquidity_strength,
                )
                
                if can_realavanca:
                    realavancagem_approved = True
                    modified_decision = boss_decision
                    modified_decision.metadata["rl_action"] = rl_action
                    modified_decision.metadata["realavancagem_approved"] = True
                    logger.info(f"RL + Capital approved re-leverage for {symbol}")
                else:
                    # CapitalManager bloqueou, faz entrada normal
                    logger.warning(f"RL approved re-leverage but CapitalManager blocked: {reason}")
                    modified_decision = boss_decision
                    modified_decision.metadata["rl_action"] = rl_action
                    modified_decision.metadata["realavancagem_blocked_reason"] = reason
            else:
                # Re-leverage desabilitado, faz entrada normal
                modified_decision = boss_decision
                modified_decision.metadata["rl_action"] = rl_action
        
        # 5. Log do evento de RL
        self._log_rl_event(
            symbol=symbol,
            regime=regime,
            state_hash=rl_state.to_hash(),
            rl_action=rl_action,
            boss_action=boss_decision.action,
            realavancagem_approved=realavancagem_approved,
        )
        
        return modified_decision, rl_action, realavancagem_approved
    
    def _discretize_confidence(self, confidence: float) -> str:
        """Discretizar confiança em níveis."""
        if confidence < 0.55:
            return "LOW"
        elif confidence < 0.70:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _discretize_disagreement(self, disagreement: float) -> str:
        """Discretizar discordância em níveis."""
        if disagreement < 0.15:
            return "LOW"
        elif disagreement < 0.35:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _log_rl_event(
        self,
        symbol: str,
        regime: str,
        state_hash: str,
        rl_action: str,
        boss_action: str,
        realavancagem_approved: bool,
    ) -> None:
        """Log do evento de decisão de RL."""
        try:
            time_str = datetime.now().isoformat()
            event = {
                "regime": regime,
                "state_hash": state_hash,
                "action": rl_action,
                "reward": None,  # Será preenchido durante update
                "reason": f"Boss: {boss_action} → RL: {rl_action}",
                "detail": {
                    "realavancagem_approved": realavancagem_approved,
                    "timestamp": time_str,
                }
            }
            repo.insert_rl_event(self.db_path, time_str, symbol, event)
        except Exception as e:
            logger.error(f"Erro ao logar evento RL: {e}")
    
    def update_from_trade(
        self,
        symbol: str,
        regime: str,
        state_hash: str,
        rl_action: str,
        trade_pnl: float,
        trade_duration_seconds: int,
    ) -> None:
        """
        Atualizar política de RL após fechamento da trade.
        
        Args:
            symbol: Símbolo da trade
            regime: Regime em que foi aberta
            state_hash: Hash do estado de RL
            rl_action: Ação que foi executada
            trade_pnl: PnL da trade fechada
            trade_duration_seconds: Duração em segundos
        """
        
        if not self.enabled:
            return
        
        # Normalizar reward (0-1)
        # Assumindo que normalização é feita em relação ao stop loss
        reward = 1.0 if trade_pnl > 0 else 0.0
        
        try:
            self.rl_policy.update_from_trade(
                regime=regime,
                state_hash=state_hash,
                action=rl_action,
                reward=reward,
                metadata={
                    "pnl": trade_pnl,
                    "duration_seconds": trade_duration_seconds,
                    "symbol": symbol,
                }
            )
            logger.info(
                f"Updated RL policy: {regime}/{state_hash}/{rl_action} "
                f"reward={reward} pnl={trade_pnl:.2f}"
            )
        except Exception as e:
            logger.error(f"Erro ao atualizar RL policy: {e}")
