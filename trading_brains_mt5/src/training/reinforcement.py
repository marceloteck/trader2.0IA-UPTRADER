"""
Reinforcement Learning: Light RL para otimização de entrada/saída
Sem deep learning, apenas Q-learning simples com estado discretizado.

V3: Aprende a evitar más trades, não apenas maximizar ganhos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import logging
import hashlib

import numpy as np
import pandas as pd

from ..db import repo
from ..config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class RLState:
    """Estado para treinamento RL"""
    regime: str
    prev_regime: str
    hour: int
    volatility_level: str  # LOW, MEDIUM, HIGH
    trend_direction: str  # UP, DOWN, RANGE
    rsi_level: str  # OVERSOLD, NEUTRAL, OVERBOUGHT
    last_action: str  # ENTER, SKIP, NONE
    
    def hash(self) -> str:
        """Gera hash do estado para indexação"""
        state_str = (
            f"{self.regime}_{self.prev_regime}_{self.hour}_{self.volatility_level}_"
            f"{self.trend_direction}_{self.rsi_level}_{self.last_action}"
        )
        return hashlib.md5(state_str.encode()).hexdigest()


@dataclass
class RLAction:
    """Ação no contexto RL"""
    action: str  # "ENTER" ou "SKIP"
    confidence: float  # 0-1


class LightReinforcementLearner:
    """
    Reinforcement Learning simplificado.
    
    Estados: Discretizados (regime × hora × volatilidade × tendência × RSI)
    Ações: ENTER (operar) ou SKIP (não operar)
    Recompensa: -loss em perdas, +profit * Sharpe em ganhos
    
    Aprendizado: Q-learning vanilla com exploração ε-greedy
    """

    def __init__(self, settings: Settings, db_path: str):
        self.settings = settings
        self.db_path = db_path
        
        # Q-table: state_hash → {action: q_value}
        self.q_table: Dict[str, Dict[str, float]] = {}
        
        # Hiperparâmetros
        self.LEARNING_RATE = 0.1
        self.DISCOUNT_FACTOR = 0.95
        self.EPSILON = 0.2  # Exploração (20% de ações aleatórias)
        self.MIN_VISITS = 5  # Mínimo de visitas para usar Q-value
        self.REWARD_SCALE = 100  # Normalizar rewards
        
        # Histórico de estados visitados
        self.visit_counts: Dict[str, int] = {}
        
        # Carregar Q-table do DB
        self._load_q_table()

    def get_action(
        self,
        regime: str,
        hour: int,
        volatility: float,
        trend: float,
        rsi: float,
        base_confidence: float,
        prev_regime: str | None = None,
        last_action: str | None = None,
    ) -> RLAction:
        """
        Recomenda ação baseada em estado atual.
        Usa ε-greedy: 80% exploita melhor ação, 20% explora.
        
        Args:
            regime: regime de mercado
            hour: hora do dia
            volatility: volatilidade (%)
            trend: tendência (-1 a 1)
            rsi: RSI (0-100)
            base_confidence: confiança dos brains (0-1)
        
        Returns:
            RLAction (ENTER ou SKIP) com confidence
        """
        
        # Discretizar estado
        state = self._discretize_state(regime, hour, volatility, trend, rsi, prev_regime, last_action)
        state_hash = state.hash()
        
        # Incrementar visita
        self.visit_counts[state_hash] = self.visit_counts.get(state_hash, 0) + 1
        
        # ε-greedy: exploração vs exploitação
        if np.random.random() < self.EPSILON or state_hash not in self.q_table:
            # Exploração: ação aleatória
            action = np.random.choice(["ENTER", "SKIP"])
            confidence = 0.5
        else:
            # Exploitação: melhor ação conhecida
            q_values = self.q_table[state_hash]
            action = max(q_values, key=q_values.get)
            
            # Confiança baseada em Q-value e visitações
            visits = self.visit_counts[state_hash]
            confidence = min(1.0, visits / (self.MIN_VISITS * 2))
            confidence *= abs(q_values[action])  # Maior Q-value = maior confidence
        
        # Se RL diz SKIP mas brains têm alta confiança, considerar ENTER
        if action == "SKIP" and base_confidence > 0.75:
            action = "ENTER"
            confidence = 0.7
        
        # Se RL diz ENTER mas brains têm baixa confiança, considerar SKIP
        if action == "ENTER" and base_confidence < 0.4:
            action = "SKIP"
            confidence = 0.6
        
        return RLAction(action=action, confidence=confidence)

    def update(
        self,
        regime: str,
        hour: int,
        volatility: float,
        trend: float,
        rsi: float,
        action_taken: str,  # "ENTER" ou "SKIP"
        reward: float,  # PnL or penalty
        next_state_hash: Optional[str] = None,
        prev_regime: str | None = None,
        last_action: str | None = None,
    ) -> None:
        """
        Atualiza Q-table com experiência.
        
        Q(s,a) ← Q(s,a) + α * [R + γ * max Q(s',a') - Q(s,a)]
        
        Args:
            regime, hour, volatility, trend, rsi: estado atual
            action_taken: ação executada
            reward: recompensa observada
            next_state_hash: hash do próximo estado
        """
        
        # Discretizar estado atual
        state = self._discretize_state(regime, hour, volatility, trend, rsi, prev_regime, last_action)
        state_hash = state.hash()
        
        # Inicializar Q-values se novo estado
        if state_hash not in self.q_table:
            self.q_table[state_hash] = {"ENTER": 0.0, "SKIP": 0.0}
        
        # Normalizar reward
        normalized_reward = np.clip(reward / self.REWARD_SCALE, -1, 1)
        
        # Calcular max Q(s',a')
        if next_state_hash and next_state_hash in self.q_table:
            max_next_q = max(self.q_table[next_state_hash].values())
        else:
            max_next_q = 0.0
        
        # Q-learning update
        old_q = self.q_table[state_hash][action_taken]
        new_q = old_q + self.LEARNING_RATE * (
            normalized_reward + self.DISCOUNT_FACTOR * max_next_q - old_q
        )
        
        self.q_table[state_hash][action_taken] = new_q
        
        # Persistir atualização
        self._update_q_value(state_hash, action_taken, new_q)
        
        logger.debug(
            f"RL Update: state={state_hash[:8]}, action={action_taken}, "
            f"reward={normalized_reward:.3f}, Q={new_q:.3f}"
        )

    def _discretize_state(
        self,
        regime: str,
        hour: int,
        volatility: float,
        trend: float,
        rsi: float,
        prev_regime: Optional[str] = None,
        last_action: Optional[str] = None,
    ) -> RLState:
        """Discretiza variáveis contínuas em estado discreto"""
        
        # Volatilidade: LOW (<1.5%), MEDIUM (1.5-2.5%), HIGH (>2.5%)
        if volatility < 1.5:
            vol_level = "LOW"
        elif volatility < 2.5:
            vol_level = "MEDIUM"
        else:
            vol_level = "HIGH"
        
        # Tendência: DOWN (<-0.02), RANGE (-0.02-0.02), UP (>0.02)
        if trend < -0.02:
            trend_level = "DOWN"
        elif trend > 0.02:
            trend_level = "UP"
        else:
            trend_level = "RANGE"
        
        # RSI: OVERSOLD (<30), NEUTRAL (30-70), OVERBOUGHT (>70)
        if rsi < 30:
            rsi_level = "OVERSOLD"
        elif rsi > 70:
            rsi_level = "OVERBOUGHT"
        else:
            rsi_level = "NEUTRAL"
        
        prev_regime_value = prev_regime or "UNKNOWN"
        last_action_value = last_action or "NONE"
        return RLState(
            regime=regime,
            prev_regime=prev_regime_value,
            hour=hour,
            volatility_level=vol_level,
            trend_direction=trend_level,
            rsi_level=rsi_level,
            last_action=last_action_value,
        )

    def _load_q_table(self) -> None:
        """Carrega Q-table do DB"""
        try:
            rows = repo.fetch_reinforcement_policy(self.db_path)
            
            for row in rows:
                state_hash = row.get("state_hash")
                action = row.get("action", "ENTER")
                q_value = float(row.get("q_value", 0.0))
                visits = int(row.get("visit_count", 0))
                
                if state_hash:
                    if state_hash not in self.q_table:
                        self.q_table[state_hash] = {}
                    
                    self.q_table[state_hash][action] = q_value
                    self.visit_counts[state_hash] = visits
            
            logger.info(f"Carregada Q-table com {len(self.q_table)} estados")
        except Exception as e:
            logger.warning(f"Erro ao carregar Q-table: {e}")

    def _update_q_value(self, state_hash: str, action: str, q_value: float) -> None:
        """Persiste Q-value no DB"""
        try:
            visits = self.visit_counts.get(state_hash, 0)
            repo.insert_reinforcement_policy(
                self.db_path,
                state_hash=state_hash,
                action=action,
                q_value=q_value,
                visit_count=visits,
            )
        except Exception as e:
            logger.warning(f"Erro ao persistir Q-value: {e}")

    def get_exploration_score(self) -> float:
        """Calcula quanto do espaço de estado foi explorado"""
        if not self.q_table:
            return 0.0
        
        # Contar estados bem explorados (>MIN_VISITS)
        well_explored = sum(
            1 for visits in self.visit_counts.values()
            if visits >= self.MIN_VISITS
        )
        
        return well_explored / len(self.q_table) if self.q_table else 0.0

    def get_policy_entropy(self) -> float:
        """
        Calcula entropia da política (0 = determinística, 1 = aleatória).
        Usada para detectar convergência.
        """
        
        if not self.q_table:
            return 1.0
        
        entropies = []
        
        for q_values in self.q_table.values():
            if "ENTER" in q_values and "SKIP" in q_values:
                # Distribuição de probabilidade (softmax)
                q_array = np.array([q_values["ENTER"], q_values["SKIP"]])
                q_norm = np.exp(q_array) / np.sum(np.exp(q_array))
                
                # Entropia = -Σ p(x) log p(x)
                entropy = -np.sum(q_norm * np.log(q_norm + 1e-10))
                entropies.append(entropy)
        
        return float(np.mean(entropies)) if entropies else 1.0
