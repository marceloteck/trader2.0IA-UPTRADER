"""
Level 5: Reinforcement Learning Policy

Implementa política leve de reforço separada por regime usando Thompson Sampling.

Funcionalidades:
- Manter distribuições de recompensa por regime/ação
- Thompson Sampling para exploração/exploração
- Aprendizado incremental de trades fechados
- Congelamento de updates se performance piora
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("trading_brains.training.reinforcement_policy")


@dataclass
class RLState:
    """Estado para RL (discretizado em buckets)."""
    regime: str
    time_bucket: str  # HH:00 - hora do dia
    confidence_level: str  # LOW, MEDIUM, HIGH
    disagreement_level: str  # LOW, MEDIUM, HIGH
    
    def to_hash(self) -> str:
        """Gere hash determinístico do estado."""
        s = f"{self.regime}_{self.time_bucket}_{self.confidence_level}_{self.disagreement_level}"
        return hashlib.md5(s.encode()).hexdigest()[:8]


@dataclass
class ActionValue:
    """Valor de ação com distribuição Thompson Sampling."""
    action: str  # HOLD, ENTER, ENTER_CONSERVATIVE, ENTER_WITH_REALAVANCAGEM
    alpha: float  # Parâmetro alpha da distribuição Beta (wins + 1)
    beta: float  # Parâmetro beta da distribuição Beta (losses + 1)
    count: int  # Número de vezes acionado
    total_reward: float  # Recompensa acumulada
    updated_at: datetime
    
    def sample(self) -> float:
        """Amostre valor de ação de distribuição Beta."""
        return np.random.beta(self.alpha, self.beta)
    
    def mean(self) -> float:
        """Obtenha média da distribuição."""
        if self.alpha + self.beta <= 1:
            return 0.5
        return self.alpha / (self.alpha + self.beta)


class RLPolicy:
    """
    Política de RL leve separada por regime.
    
    Implementa:
    - Thompson Sampling contextual (por regime/hora/confiança)
    - Aprendizado incremental
    - Congelamento automático se performance piora
    """
    
    def __init__(
        self,
        initial_alpha: float = 1.0,
        initial_beta: float = 1.0,
        freeze_threshold: float = 0.15,
    ):
        """
        Inicialize política RL.
        
        Args:
            initial_alpha: Alpha inicial para Beta (prior)
            initial_beta: Beta inicial para Beta (prior)
            freeze_threshold: Threshold de deterioração para congelar updates
        """
        self.initial_alpha = initial_alpha
        self.initial_beta = initial_beta
        self.freeze_threshold = freeze_threshold
        
        # policy_tables[regime][state_hash][action] = ActionValue
        self.policy_tables: Dict[str, Dict[str, Dict[str, ActionValue]]] = {}
        
        # Rastreamento de performance
        self.performance_baseline: Dict[str, float] = {}  # Por regime
        self.frozen_regimes: set[str] = set()
        
        self.events: List[Dict] = []
    
    def select_action(
        self,
        regime: str,
        state: RLState,
        available_actions: List[str],
    ) -> Tuple[str, float]:
        """
        Selecione ação usando Thompson Sampling.
        
        Args:
            regime: Regime atual
            state: Estado discretizado
            available_actions: Lista de ações disponíveis
        
        Returns:
            (ação: str, valor_amostrado: float)
        """
        if regime not in self.policy_tables:
            self.policy_tables[regime] = {}
        
        state_hash = state.to_hash()
        if state_hash not in self.policy_tables[regime]:
            self.policy_tables[regime][state_hash] = {}
        
        action_values = self.policy_tables[regime][state_hash]
        
        # Inicialize ações faltantes
        for action in available_actions:
            if action not in action_values:
                action_values[action] = ActionValue(
                    action=action,
                    alpha=self.initial_alpha,
                    beta=self.initial_beta,
                    count=0,
                    total_reward=0.0,
                    updated_at=datetime.utcnow(),
                )
        
        # Amostre valores usando Thompson Sampling
        best_action = None
        best_value = -np.inf
        
        for action in available_actions:
            sampled_value = action_values[action].sample()
            if sampled_value > best_value:
                best_value = sampled_value
                best_action = action
        
        return best_action, best_value
    
    def update_from_trade(
        self,
        regime: str,
        state: RLState,
        action: str,
        reward: float,
    ) -> None:
        """
        Atualize política após trade fechado.
        
        Args:
            regime: Regime em que foi executado
            state: Estado quando ação foi selecionada
            action: Ação executada
            reward: Recompensa do trade
        """
        # Se regime congelado, não atualize
        if regime in self.frozen_regimes:
            logger.debug(f"RL update bloqueado: regime {regime} congelado")
            return
        
        if regime not in self.policy_tables:
            self.policy_tables[regime] = {}
        
        state_hash = state.to_hash()
        if state_hash not in self.policy_tables[regime]:
            self.policy_tables[regime][state_hash] = {}
        
        action_values = self.policy_tables[regime][state_hash]
        
        if action not in action_values:
            action_values[action] = ActionValue(
                action=action,
                alpha=self.initial_alpha,
                beta=self.initial_beta,
                count=0,
                total_reward=0.0,
                updated_at=datetime.utcnow(),
            )
        
        av = action_values[action]
        
        # Normalize recompensa para 0-1 range
        normalized_reward = max(0.0, min(1.0, (reward + 100) / 200))  # Range: [-100, 100]
        
        # Thompson Sampling update: Beta distribution
        if normalized_reward > 0.5:
            av.alpha += normalized_reward
        else:
            av.beta += (1.0 - normalized_reward)
        
        av.count += 1
        av.total_reward += reward
        av.updated_at = datetime.utcnow()
        
        logger.debug(
            f"RL update {regime}/{state_hash}/{action}: reward={reward:.0f}, "
            f"alpha={av.alpha:.1f}, beta={av.beta:.1f}, count={av.count}"
        )
        
        # Verifique se deve congelar
        self._check_freeze_regime(regime)
    
    def _check_freeze_regime(self, regime: str) -> None:
        """Verifique se performance piorou muito e congele updates."""
        if regime not in self.policy_tables or regime in self.frozen_regimes:
            return
        
        all_rewards = []
        for state_hash, actions in self.policy_tables[regime].items():
            for av in actions.values():
                if av.count > 0:
                    all_rewards.append(av.total_reward / av.count)
        
        if not all_rewards:
            return
        
        current_mean = np.mean(all_rewards)
        
        # Armazene baseline
        if regime not in self.performance_baseline:
            self.performance_baseline[regime] = current_mean
        
        baseline = self.performance_baseline[regime]
        
        # Verifique deterioração
        deterioration = (baseline - current_mean) / abs(baseline + 1e-6)
        
        if deterioration > self.freeze_threshold:
            self.frozen_regimes.add(regime)
            logger.warning(
                f"RL CONGELADO para regime {regime}: deterioração {deterioration:.2%} > {self.freeze_threshold:.2%}"
            )
    
    def unfreeze_regime(self, regime: str) -> None:
        """Descongeole regime e atualize baseline."""
        if regime in self.frozen_regimes:
            self.frozen_regimes.remove(regime)
            
            # Recompute baseline
            all_rewards = []
            if regime in self.policy_tables:
                for state_hash, actions in self.policy_tables[regime].items():
                    for av in actions.values():
                        if av.count > 0:
                            all_rewards.append(av.total_reward / av.count)
            
            if all_rewards:
                self.performance_baseline[regime] = np.mean(all_rewards)
            
            logger.info(f"RL descongelado para regime {regime}")
    
    def get_action_stats(
        self,
        regime: str,
        state: RLState,
        action: str,
    ) -> Dict:
        """Obtenha estatísticas de ação."""
        if regime not in self.policy_tables:
            return {"count": 0, "mean_reward": 0, "mean_value": 0.5}
        
        state_hash = state.to_hash()
        if state_hash not in self.policy_tables[regime]:
            return {"count": 0, "mean_reward": 0, "mean_value": 0.5}
        
        if action not in self.policy_tables[regime][state_hash]:
            return {"count": 0, "mean_reward": 0, "mean_value": 0.5}
        
        av = self.policy_tables[regime][state_hash][action]
        
        return {
            "count": av.count,
            "mean_reward": av.total_reward / av.count if av.count > 0 else 0,
            "mean_value": av.mean(),
            "alpha": av.alpha,
            "beta": av.beta,
        }
    
    def export_policy_table(self, regime: str) -> Dict:
        """Exporte tabela de política para regime."""
        if regime not in self.policy_tables:
            return {}
        
        result = {}
        for state_hash, actions in self.policy_tables[regime].items():
            result[state_hash] = {}
            for action, av in actions.items():
                result[state_hash][action] = {
                    "alpha": float(av.alpha),
                    "beta": float(av.beta),
                    "count": av.count,
                    "mean_value": float(av.mean()),
                    "total_reward": float(av.total_reward),
                }
        
        return result
    
    def import_policy_table(self, regime: str, policy_dict: Dict) -> None:
        """Importe tabela de política para regime."""
        if regime not in self.policy_tables:
            self.policy_tables[regime] = {}
        
        for state_hash, actions in policy_dict.items():
            if state_hash not in self.policy_tables[regime]:
                self.policy_tables[regime][state_hash] = {}
            
            for action, params in actions.items():
                self.policy_tables[regime][state_hash][action] = ActionValue(
                    action=action,
                    alpha=params.get("alpha", self.initial_alpha),
                    beta=params.get("beta", self.initial_beta),
                    count=params.get("count", 0),
                    total_reward=params.get("total_reward", 0),
                    updated_at=datetime.utcnow(),
                )
    
    def log_event(
        self,
        regime: str,
        state: RLState,
        action: str,
        reward: float,
        reason: str,
    ) -> None:
        """Registre evento de RL."""
        event = {
            "time": datetime.utcnow().isoformat(),
            "regime": regime,
            "state": state.to_hash(),
            "action": action,
            "reward": reward,
            "reason": reason,
            "frozen": regime in self.frozen_regimes,
        }
        self.events.append(event)
    
    def get_events(self, regime: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Obtenha eventos de RL."""
        if regime:
            events = [e for e in self.events if e["regime"] == regime]
        else:
            events = self.events
        
        return events[-limit:]
    
    def export_stats(self) -> Dict:
        """Exporte estatísticas de política."""
        stats = {
            "regimes": list(self.policy_tables.keys()),
            "frozen_regimes": list(self.frozen_regimes),
            "total_events": len(self.events),
        }
        
        for regime in self.policy_tables.keys():
            state_count = len(self.policy_tables[regime])
            
            total_count = sum(
                av.count
                for state_hash in self.policy_tables[regime].values()
                for av in state_hash.values()
            )
            
            total_reward = sum(
                av.total_reward
                for state_hash in self.policy_tables[regime].values()
                for av in state_hash.values()
            )
            
            mean_reward = total_reward / total_count if total_count > 0 else 0
            
            stats[f"regime_{regime}"] = {
                "states": state_count,
                "total_samples": total_count,
                "mean_reward": float(mean_reward),
            }
        
        return stats
