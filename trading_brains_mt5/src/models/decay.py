"""
Knowledge Decay: Mecanismo de envelhecimento de conhecimento
Reduz importância de dados antigos para evitar overfitting em regimes mudados.

V3: Aplicar decay automático por tempo e por mudança de regime.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

import numpy as np

logger = logging.getLogger(__name__)


class KnowledgeDecayPolicy:
    """
    Define como conhecimento envelhece.
    
    Estratégias:
    1. Temporal: exp(-t / half_life)
    2. Regime-aware: reduz conhecimento quando regime muda
    3. Performance-aware: reduz se performance degrada
    4. Catalyst-based: reseta após eventos de volatilidade
    """

    def __init__(
        self,
        half_life_days: float = 30,
        regime_change_decay: float = 0.7,
        performance_threshold: float = 0.5,
    ):
        self.half_life_days = half_life_days
        self.regime_change_decay = regime_change_decay
        self.performance_threshold = performance_threshold
        
    def temporal_decay(
        self,
        timestamp: str,  # ISO format
        current_time: Optional[str] = None,
    ) -> float:
        """
        Calcula fator de decay temporal (0-1).
        
        Modelo: decay(t) = 0.5^(t / T_half)
        Resultado: 50% aos T_half dias, 25% aos 2*T_half, etc
        
        Args:
            timestamp: quando o conhecimento foi adquirido
            current_time: tempo atual (default: agora)
        
        Returns:
            decay factor (0-1), onde 1 = conhecimento fresco
        """
        
        try:
            if current_time is None:
                current_time = datetime.utcnow().isoformat()
            
            ts = datetime.fromisoformat(timestamp)
            ct = datetime.fromisoformat(current_time)
            
            age_days = (ct - ts).total_seconds() / (24 * 3600)
            
            # Half-life decay
            decay_factor = 0.5 ** (age_days / self.half_life_days)
            
            return float(np.clip(decay_factor, 0, 1))
        
        except Exception as e:
            logger.warning(f"Erro ao calcular temporal decay: {e}")
            return 0.5

    def regime_aware_decay(
        self,
        knowledge_regime: str,
        current_regime: str,
        regime_duration_in_current: int,
    ) -> float:
        """
        Reduz confiança em conhecimento de regime diferente.
        
        Lógica: Se regime mudou, conhecimento do regime anterior vale menos.
        Se passaram muitas velas no novo regime, valor ainda menor.
        
        Args:
            knowledge_regime: regime em que o conhecimento foi obtido
            current_regime: regime atual
            regime_duration_in_current: há quantas velas estamos no regime atual
        
        Returns:
            decay factor
        """
        
        if knowledge_regime == current_regime:
            # Mesmo regime: sem decay por regime
            return 1.0
        
        # Regime diferente: base decay
        decay = self.regime_change_decay
        
        # Quanto mais tempo no novo regime, mais decay
        # Após 50 velas no novo regime, conhecimento antigo vale 50%
        additional_decay = 0.5 ** (regime_duration_in_current / 50.0)
        
        return float(decay * additional_decay)

    def performance_aware_decay(
        self,
        current_win_rate: float,
        previous_win_rate: float,
    ) -> float:
        """
        Reduz confiança se performance degrada.
        
        Lógica: Se win_rate caiu muito, conhecimento estava overfitted.
        
        Args:
            current_win_rate: performance recente
            previous_win_rate: performance histórica
        
        Returns:
            decay factor
        """
        
        if previous_win_rate == 0:
            return 1.0
        
        performance_ratio = current_win_rate / (previous_win_rate + 1e-10)
        
        if performance_ratio > self.performance_threshold:
            # Performance melhorou ou estável
            return 1.0
        else:
            # Performance piorou
            decay = max(0.3, performance_ratio)
            return float(decay)

    def catalyst_decay(
        self,
        volatility: float,
        volatility_threshold: float = 5.0,  # 5% ATR
    ) -> float:
        """
        Aplica decay maior quando há catalizador (high vol, breakout, etc).
        
        Lógica: Em eventos de volatilidade alta, passado é menos relevante.
        
        Args:
            volatility: volatilidade atual (%)
            volatility_threshold: acima disto é "catalyst"
        
        Returns:
            decay factor (1 = sem decay, <1 = reduzido)
        """
        
        if volatility < volatility_threshold:
            # Mercado calmo, conhecimento mantém valor
            return 1.0
        
        # Mercado agitado: reduz valor de conhecimento antigo
        # A cada 1% acima do threshold, multiplica decay por 0.9
        decay = 0.9 ** (volatility - volatility_threshold)
        
        return float(np.clip(decay, 0.3, 1.0))

    def combined_decay(
        self,
        timestamp: str,
        knowledge_regime: str,
        current_regime: str,
        regime_duration: int,
        current_win_rate: float,
        previous_win_rate: float,
        current_volatility: float,
        current_time: Optional[str] = None,
    ) -> float:
        """
        Combina todos os fatores de decay.
        
        Decays multiplicam: total = temporal * regime * perf * catalyst
        
        Returns:
            decay factor (0-1), onde 1 = conhecimento com valor total
        """
        
        t_decay = self.temporal_decay(timestamp, current_time)
        r_decay = self.regime_aware_decay(knowledge_regime, current_regime, regime_duration)
        p_decay = self.performance_aware_decay(current_win_rate, previous_win_rate)
        c_decay = self.catalyst_decay(current_volatility)
        
        combined = t_decay * r_decay * p_decay * c_decay
        
        logger.debug(
            f"Decay: temporal={t_decay:.2f}, regime={r_decay:.2f}, "
            f"perf={p_decay:.2f}, catalyst={c_decay:.2f} → combined={combined:.2f}"
        )
        
        return float(np.clip(combined, 0, 1))


class TradeDecayAnalyzer:
    """Analisa impacto de decay em decisões históricas de trading"""

    def __init__(self, policy: KnowledgeDecayPolicy):
        self.policy = policy

    def calculate_decayed_metrics(
        self,
        trades: List[Dict],
        current_regime: str,
        current_volatility: float,
        current_time: Optional[str] = None,
    ) -> Dict:
        """
        Recalcula métricas de performance aplicando decay.
        
        Args:
            trades: lista de trades com timestamps e regime
            current_regime: regime atual
            current_volatility: volatilidade atual
            current_time: tempo de referência
        
        Returns:
            Dict com métricas decayed
        """
        
        if not trades:
            return {
                "win_rate_raw": 0.0,
                "win_rate_decayed": 0.0,
                "profit_factor_raw": 1.0,
                "profit_factor_decayed": 1.0,
                "trades_decayed_count": 0,
            }
        
        if current_time is None:
            current_time = datetime.utcnow().isoformat()
        
        # Calcular win rate bruto
        pnls = [float(t.get("pnl", 0)) for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        raw_win_rate = wins / len(pnls) if pnls else 0
        
        # Calcular com decay
        weights = []
        decayed_pnls = []
        
        for trade in trades:
            timestamp = trade.get("opened_at", current_time)
            trade_regime = trade.get("regime", "unknown")
            pnl = float(trade.get("pnl", 0))
            
            # Calcular decay para esta trade
            regime_duration = 0  # Simplificado, ideal seria rastrear
            current_wr = raw_win_rate  # Simplificado
            
            decay = self.policy.combined_decay(
                timestamp=timestamp,
                knowledge_regime=trade_regime,
                current_regime=current_regime,
                regime_duration=regime_duration,
                current_win_rate=current_wr,
                previous_win_rate=current_wr,
                current_volatility=current_volatility,
                current_time=current_time,
            )
            
            weights.append(decay)
            decayed_pnls.append(pnl * decay)
        
        # Calcular métricas decayed
        decayed_wins = sum(1 for p in decayed_pnls if p > 0)
        total_weight = sum(weights)
        decayed_win_rate = decayed_wins / len(decayed_pnls) if decayed_pnls else 0
        
        # Profit factor decayed
        gains_decayed = sum(p for p in decayed_pnls if p > 0)
        losses_decayed = abs(sum(p for p in decayed_pnls if p < 0))
        pf_decayed = gains_decayed / losses_decayed if losses_decayed > 0 else 1.0
        
        return {
            "win_rate_raw": float(raw_win_rate),
            "win_rate_decayed": float(decayed_win_rate),
            "profit_factor_raw": float(np.sum(pnls) / (abs(min(pnls)) + 1)) if pnls else 1.0,
            "profit_factor_decayed": float(pf_decayed),
            "trades_raw_count": len(trades),
            "trades_effective_count": float(total_weight),
            "average_decay_factor": float(np.mean(weights)) if weights else 0.0,
        }
