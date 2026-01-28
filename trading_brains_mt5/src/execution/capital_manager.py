"""
Level 5: Capital Manager

Gerencia capital do operador, cálculo de contratos e regras de realavancagem.

Funcionalidades:
- Calcular contratos máximos baseado em capital e margem
- Validar permissão para realavancagem
- Calcular distribuição final (base + extra) de contratos
- Persistência de decisões de capital
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger("trading_brains.execution.capital_manager")


@dataclass
class CapitalState:
    """Estado atual do capital e contratos."""
    time: datetime
    symbol: str
    operator_capital_brl: float
    margin_per_contract_brl: float
    max_contracts_cap: int
    base_contracts: int
    extra_contracts: int
    final_contracts: int
    reason: str


class CapitalManager:
    """
    Gerencia capital e cálculo de contratos de forma segura.
    
    Implementa:
    - Cálculo de contratos base por capital disponível
    - Validação de realavancagem (extra contratos)
    - Limitações por regime e estado do mercado
    - Rastreamento histórico
    """
    
    def __init__(
        self,
        operator_capital_brl: float,
        margin_per_contract_brl: float,
        max_contracts_cap: int,
        min_contracts: int = 1,
    ):
        """
        Inicialize o gerenciador de capital.
        
        Args:
            operator_capital_brl: Capital total do operador em BRL
            margin_per_contract_brl: Margem requerida por contrato em BRL
            max_contracts_cap: Teto máximo absoluto de contratos
            min_contracts: Mínimo de contratos para operar (default 1)
        """
        self.operator_capital_brl = operator_capital_brl
        self.margin_per_contract_brl = margin_per_contract_brl
        self.max_contracts_cap = max_contracts_cap
        self.min_contracts = min_contracts
        
        self.history: list[CapitalState] = []
    
    def calc_base_contracts(self) -> int:
        """
        Calcule número de contratos base pelo capital.
        
        Formula:
            base = floor(capital / margem_por_contrato)
            base = min(base, max_cap)
        
        Returns:
            Número de contratos base (inteiro)
        """
        if self.margin_per_contract_brl <= 0:
            return self.min_contracts
        
        base = int(self.operator_capital_brl / self.margin_per_contract_brl)
        base = min(base, self.max_contracts_cap)
        
        return max(base, self.min_contracts)
    
    def can_realavancar(
        self,
        regime_mode: str,
        global_confidence: float,
        pnl_today_brl: float,
        transition_active: bool,
        disagreement_score: float,
        liquidity_strength: float,
        realavancagem_enabled: bool,
        realavancagem_min_confidence: float,
        realavancagem_require_profit: bool,
        realavancagem_min_profit_brl: float,
        realavancagem_allowed_regimes: list[str],
        realavancagem_forbidden_modes: list[str],
    ) -> Tuple[bool, str]:
        """
        Verifique se realavancagem é permitida.
        
        Args:
            regime_mode: Modo de regime (NORMAL, TREND_UP, TREND_DOWN, RANGE, etc.)
            global_confidence: Confiança global de sinais (0-1)
            pnl_today_brl: PnL realizado hoje em BRL
            transition_active: Se transição está ativa
            disagreement_score: Score de discordância do ensemble (0-1)
            liquidity_strength: Força de liquidez nearby (0-1)
            realavancagem_enabled: Se realavancagem está habilitada
            realavancagem_min_confidence: Confiança mínima requerida
            realavancagem_require_profit: Se exige lucro do dia
            realavancagem_min_profit_brl: Lucro mínimo requerido em BRL
            realavancagem_allowed_regimes: Lista de regimes permitidos
            realavancagem_forbidden_modes: Lista de modos proibidos
        
        Returns:
            (permitido: bool, razão: str)
        """
        # Verificação 1: Feature habilitada?
        if not realavancagem_enabled:
            return False, "Realavancagem desabilitada globalmente"
        
        # Verificação 2: Regime proibido?
        if regime_mode in realavancagem_forbidden_modes:
            return False, f"Regime '{regime_mode}' proibido para realavancagem"
        
        # Verificação 3: Regime não está na whitelist?
        if realavancagem_allowed_regimes and regime_mode not in realavancagem_allowed_regimes:
            return False, f"Regime '{regime_mode}' não autorizado (whitelist: {realavancagem_allowed_regimes})"
        
        # Verificação 4: Transição ativa?
        if transition_active:
            return False, "Realavancagem bloqueada durante transição de regime"
        
        # Verificação 5: Confiança global insuficiente?
        if global_confidence < realavancagem_min_confidence:
            return False, f"Confiança insuficiente: {global_confidence:.2f} < {realavancagem_min_confidence:.2f}"
        
        # Verificação 6: Lucro do dia requerido?
        if realavancagem_require_profit:
            if pnl_today_brl < realavancagem_min_profit_brl:
                return False, f"Lucro do dia insuficiente: {pnl_today_brl:.0f} < {realavancagem_min_profit_brl:.0f}"
        
        # Verificação 7: Liquidez suficiente?
        if liquidity_strength < 0.50:
            return False, f"Liquidez insuficiente: {liquidity_strength:.2f} < 0.50"
        
        # Verificação 8: Discordância do ensemble muito alta?
        if disagreement_score > 0.40:
            return False, f"Discordância do ensemble elevada: {disagreement_score:.2f} > 0.40"
        
        # Todas as verificações passou
        return True, "Realavancagem autorizada"
    
    def calc_contracts(
        self,
        regime_mode: str,
        global_confidence: float,
        pnl_today_brl: float,
        transition_active: bool,
        disagreement_score: float,
        liquidity_strength: float,
        realavancagem_enabled: bool,
        realavancagem_max_extra: int,
        realavancagem_min_confidence: float,
        realavancagem_require_profit: bool,
        realavancagem_min_profit_brl: float,
        realavancagem_allowed_regimes: list[str],
        realavancagem_forbidden_modes: list[str],
    ) -> CapitalState:
        """
        Calcule distribuição final de contratos (base + extra).
        
        Args:
            regime_mode: Modo de regime
            global_confidence: Confiança global
            pnl_today_brl: PnL do dia
            transition_active: Se transição está ativa
            disagreement_score: Discordância do ensemble
            liquidity_strength: Força de liquidez
            realavancagem_enabled: Se realavancagem habilitada
            realavancagem_max_extra: Máximo de contratos extra
            realavancagem_min_confidence: Confiança mínima para realavancagem
            realavancagem_require_profit: Se exige lucro do dia
            realavancagem_min_profit_brl: Lucro mínimo
            realavancagem_allowed_regimes: Regimes permitidos
            realavancagem_forbidden_modes: Modos proibidos
        
        Returns:
            CapitalState com distribuição calculada
        """
        # Calcule contratos base
        base_contracts = self.calc_base_contracts()
        
        # Inicie com zero extras
        extra_contracts = 0
        reason = f"Base: {base_contracts} contratos"
        
        # Verifique se pode realavacar
        can_realeva, realeva_reason = self.can_realavancar(
            regime_mode=regime_mode,
            global_confidence=global_confidence,
            pnl_today_brl=pnl_today_brl,
            transition_active=transition_active,
            disagreement_score=disagreement_score,
            liquidity_strength=liquidity_strength,
            realavancagem_enabled=realavancagem_enabled,
            realavancagem_min_confidence=realavancagem_min_confidence,
            realavancagem_require_profit=realavancagem_require_profit,
            realavancagem_min_profit_brl=realavancagem_min_profit_brl,
            realavancagem_allowed_regimes=realavancagem_allowed_regimes,
            realavancagem_forbidden_modes=realavancagem_forbidden_modes,
        )
        
        if can_realeva and realavancagem_max_extra > 0:
            # Autorizado a realavacar
            extra_contracts = realavancagem_max_extra
            reason += f" + {extra_contracts} extra (realavancagem: {realeva_reason})"
        else:
            reason += f" (sem realavancagem: {realeva_reason})"
        
        final_contracts = min(base_contracts + extra_contracts, self.max_contracts_cap)
        
        # Se final < min: modo seguro
        if final_contracts < self.min_contracts:
            final_contracts = 0
            reason += " [MODO SEGURO: capital insuficiente]"
        
        state = CapitalState(
            time=datetime.utcnow(),
            symbol="MULTI",
            operator_capital_brl=self.operator_capital_brl,
            margin_per_contract_brl=self.margin_per_contract_brl,
            max_contracts_cap=self.max_contracts_cap,
            base_contracts=base_contracts,
            extra_contracts=extra_contracts,
            final_contracts=final_contracts,
            reason=reason,
        )
        
        self.history.append(state)
        
        logger.info(
            f"Capital decision: base={base_contracts}, extra={extra_contracts}, "
            f"final={final_contracts} (cap={self.operator_capital_brl:.0f})"
        )
        
        return state
    
    def get_last_state(self) -> Optional[CapitalState]:
        """Obtenha o último estado de capital calculado."""
        return self.history[-1] if self.history else None
    
    def get_history(self, limit: int = 100) -> list[CapitalState]:
        """Obtenha histórico recente de decisões de capital."""
        return self.history[-limit:]
    
    def export_stats(self) -> Dict:
        """Exporte estatísticas de capital."""
        if not self.history:
            return {
                "total_decisions": 0,
                "avg_base_contracts": 0,
                "max_extra_used": 0,
                "realavancagem_count": 0,
            }
        
        realeva_count = sum(1 for s in self.history if s.extra_contracts > 0)
        
        return {
            "total_decisions": len(self.history),
            "avg_base_contracts": sum(s.base_contracts for s in self.history) / len(self.history),
            "max_extra_used": max((s.extra_contracts for s in self.history), default=0),
            "realavancagem_count": realeva_count,
            "realavancagem_success_rate": realeva_count / len(self.history) if self.history else 0,
        }
