"""
MetaBrain: O Cérebro dos Cérebros
Avalia performance de cada cérebro e ajusta pesos dinamicamente.
Nunca esquece aprendizados, apenas decai conhecimento antigo por regime.

V3 CORE: Aprendizado contínuo sem deep learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging

import pandas as pd
import numpy as np

from ..db import repo
from ..config.settings import Settings
from ..features.regime_transition import RegimeState, RegimeTransitionDetector
from ..models.transition_performance import TransitionPerformanceMatrix
from ..execution.risk_adapter import DynamicRiskAdapter

logger = logging.getLogger(__name__)


@dataclass
class BrainPerformanceMetrics:
    """Métricas de performance de um cérebro em um regime específico"""
    brain_id: str
    regime: str
    win_rate: float = 0.0  # Trades ganhadores / total
    profit_factor: float = 1.0  # Ganhos / perdas
    avg_rr: float = 1.0  # Risk/reward médio realizado
    total_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    last_update: str = ""  # ISO timestamp
    trades: List[Dict] = field(default_factory=list)  # últimos N trades
    confidence: float = 0.5  # confiança da métrica (0-1, cresce com trades)

    def to_dict(self) -> Dict:
        return {
            "brain_id": self.brain_id,
            "regime": self.regime,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_rr": self.avg_rr,
            "total_trades": self.total_trades,
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "last_update": self.last_update,
            "confidence": self.confidence,
        }


@dataclass
class MetaBrainDecision:
    """Decisão do MetaBrain"""
    allow_trading: bool  # Permitir operação?
    weight_adjustment: Dict[str, float]  # {brain_id: peso_final}
    global_confidence: float  # 0-1
    reasoning: List[str]  # Por que essa decisão?
    market_sentiment: str  # BULLISH / BEARISH / NEUTRAL
    risk_level: str  # LOW / MEDIUM / HIGH
    metadata: Dict = field(default_factory=dict)


class MetaBrain:
    """
    O cérebro dos cérebros.
    
    Responsabilidades:
    1. Rastrear performance de cada cérebro por regime
    2. Ajustar pesos dinamicamente baseado no histórico
    3. Aprender a não operar em certos contextos
    4. Detectar degradação de performance
    5. Aplicar decay de conhecimento por tempo e regime
    """

    def __init__(self, settings: Settings, db_path: str):
        self.settings = settings
        self.db_path = db_path
        
        # Performance cache (regime → brain_id → metrics)
        self.performance_cache: Dict[str, Dict[str, BrainPerformanceMetrics]] = {}
        
        # Histórico de decisões
        self.decision_history: List[Dict] = []
        
        # Limites de confiança por métrica
        self.MIN_TRADES_FOR_CONFIDENCE = 5
        self.MIN_CONFIDENCE = 0.3  # Não usar if < 30% confidence
        
        # Decay parameters
        self.DECAY_HALF_LIFE_DAYS = 30  # Conhecimento decai em 30 dias
        self.REGIME_CHANGE_DECAY = 0.7  # Trades em regime diferente valem 70%
        
        # Level 3: Regime-aware components
        self.transition_detector = RegimeTransitionDetector()
        self.transition_performance = TransitionPerformanceMatrix()
        self.risk_adapter = DynamicRiskAdapter(base_risk=settings.RISK_PER_TRADE)
        
        # Level 3: Modes (NORMAL, TRANSITION, CHAOTIC)
        self.meta_mode = "NORMAL"
        self.meta_mode_history: List[Dict] = []
        
        # Load performance history from DB
        self._load_performance_history()

    def evaluate(
        self,
        current_regime: str,
        current_hour: int,
        current_volatility: float,
        brain_scores: Dict[str, float],  # {brain_id: score}
        recent_trades: Optional[List[Dict]] = None,
    ) -> MetaBrainDecision:
        """
        Avalia o contexto atual e decide se/como operar.
        
        Args:
            current_regime: TREND_UP, TREND_DOWN, RANGE, HIGH_VOL, etc
            current_hour: hora do dia (0-23)
            current_volatility: volatilidade atual (%)
            brain_scores: scores dos cérebros
            recent_trades: últimas trades para calcular live metrics
        
        Returns:
            MetaBrainDecision com pesos ajustados e permissão de trading
        """
        
        reasoning = []
        weight_adjustment = {}
        risk_flags = []
        
        # 1. ANÁLISE DE PERFORMANCE POR REGIME
        # ────────────────────────────────────
        regime_performance = self._analyze_regime_performance(current_regime, current_hour)
        reasoning.append(f"Regime: {current_regime} (data points: {len(regime_performance)})")
        
        # 2. CALCULAR PESOS AJUSTADOS
        # ──────────────────────────
        for brain_id, base_score in brain_scores.items():
            # Pega métrica do cérebro no regime atual
            metrics = self.performance_cache.get(current_regime, {}).get(brain_id)
            
            if metrics is None or metrics.total_trades < self.MIN_TRADES_FOR_CONFIDENCE:
                # Cérebro novo ou sem histórico → peso neutro
                adjusted_weight = 1.0
                reasoning.append(f"{brain_id}: novo/sem histórico → peso 1.0")
            else:
                # Peso baseado em performance histórica
                confidence_multiplier = min(1.0, metrics.confidence)
                
                # Penalizar se win_rate ou profit_factor baixos
                win_rate_factor = max(0.5, metrics.win_rate) if metrics.win_rate > 0 else 0.5
                pf_factor = max(0.7, min(1.3, metrics.profit_factor))
                
                # Ajuste combinado
                adjusted_weight = 1.0 * win_rate_factor * pf_factor * confidence_multiplier
                adjusted_weight = max(0.3, min(2.0, adjusted_weight))  # Clamp [0.3, 2.0]
                
                reasoning.append(
                    f"{brain_id}: WR={metrics.win_rate:.1%}, PF={pf_factor:.2f} → "
                    f"peso {adjusted_weight:.2f}"
                )
                
                # Flag de risco se muito ruim
                if metrics.win_rate < 0.3 or metrics.profit_factor < 0.8:
                    risk_flags.append(f"{brain_id} low performance in {current_regime}")
            
            weight_adjustment[brain_id] = adjusted_weight
        
        # 3. AVALIAR SE DEVE OPERIAR BASEADO EM CONFIANÇA GLOBAL
        # ───────────────────────────────────────────────────────
        global_confidence = self._calculate_global_confidence(
            current_regime, regime_performance, risk_flags
        )
        
        # Regra: só opera se confiança > MIN_CONFIDENCE
        allow_trading = global_confidence >= self.MIN_CONFIDENCE
        
        if not allow_trading:
            reasoning.append(f"BLOQUEADO: confiança baixa ({global_confidence:.1%})")
            risk_flags.append(f"confidence_too_low")
        
        # 4. DETECTAR ANOMALIAS
        # ───────────────────
        anomalies = self._detect_anomalies(recent_trades or [])
        if anomalies:
            reasoning.extend(anomalies)
            risk_flags.extend(anomalies)
        
        # 5. DETERMINAR SENTIMENT E RISK LEVEL
        # ────────────────────────────────────
        market_sentiment = self._determine_sentiment(current_regime, regime_performance)
        risk_level = self._assess_risk_level(risk_flags, global_confidence)
        
        # 6. LOG DECISION
        # ──────────────
        decision = MetaBrainDecision(
            allow_trading=allow_trading,
            weight_adjustment=weight_adjustment,
            global_confidence=global_confidence,
            reasoning=reasoning,
            market_sentiment=market_sentiment,
            risk_level=risk_level,
            metadata={
                "regime": current_regime,
                "hour": current_hour,
                "volatility": current_volatility,
                "anomalies": anomalies,
            }
        )
        
        # Persistir decisão
        self._log_decision(decision, current_regime)
        
        return decision

    def _load_performance_history(self) -> None:
        """Carrega histórico de performance do DB"""
        try:
            histories = repo.fetch_brain_performance_history(self.db_path)
            
            for hist in histories:
                regime = hist.get("regime", "unknown")
                brain_id = hist.get("brain_id", "unknown")
                
                if regime not in self.performance_cache:
                    self.performance_cache[regime] = {}
                
                # Reconstruir BrainPerformanceMetrics
                metrics = BrainPerformanceMetrics(
                    brain_id=brain_id,
                    regime=regime,
                    win_rate=float(hist.get("win_rate", 0.0)),
                    profit_factor=float(hist.get("profit_factor", 1.0)),
                    avg_rr=float(hist.get("avg_rr", 1.0)),
                    total_trades=int(hist.get("total_trades", 0)),
                    total_pnl=float(hist.get("total_pnl", 0.0)),
                    max_drawdown=float(hist.get("max_drawdown", 0.0)),
                    last_update=hist.get("last_update", ""),
                    confidence=self._calculate_confidence(int(hist.get("total_trades", 0))),
                )
                
                self.performance_cache[regime][brain_id] = metrics
                
            logger.info(f"Carregado histórico de performance: {len(histories)} entradas")
        except Exception as e:
            logger.warning(f"Erro ao carregar performance history: {e}")

    def _analyze_regime_performance(self, regime: str, hour: int) -> Dict[str, BrainPerformanceMetrics]:
        """Analisa performance de todos os cérebros no regime atual"""
        if regime not in self.performance_cache:
            return {}
        
        # Aplicar decay temporal
        decayed_performance = {}
        for brain_id, metrics in self.performance_cache[regime].items():
            decayed = self._apply_temporal_decay(metrics)
            decayed_performance[brain_id] = decayed
        
        return decayed_performance

    def _apply_temporal_decay(self, metrics: BrainPerformanceMetrics) -> BrainPerformanceMetrics:
        """Aplica decay temporal ao conhecimento antigo"""
        if not metrics.last_update:
            return metrics
        
        try:
            last_update = datetime.fromisoformat(metrics.last_update)
            age_days = (datetime.utcnow() - last_update).days
            
            # Decay exponencial: 50% aos 30 dias
            decay_factor = 0.5 ** (age_days / self.DECAY_HALF_LIFE_DAYS)
            
            # Aumentar incerteza (reduzir confiança)
            decayed_confidence = metrics.confidence * decay_factor
            
            # Criar cópia com confiança reduzida
            decayed = BrainPerformanceMetrics(
                brain_id=metrics.brain_id,
                regime=metrics.regime,
                win_rate=metrics.win_rate,
                profit_factor=metrics.profit_factor,
                avg_rr=metrics.avg_rr,
                total_trades=metrics.total_trades,
                total_pnl=metrics.total_pnl,
                max_drawdown=metrics.max_drawdown,
                last_update=metrics.last_update,
                confidence=decayed_confidence,
            )
            
            return decayed
        except Exception as e:
            logger.warning(f"Erro ao aplicar temporal decay: {e}")
            return metrics

    def _calculate_global_confidence(
        self,
        regime: str,
        regime_performance: Dict[str, BrainPerformanceMetrics],
        risk_flags: List[str],
    ) -> float:
        """Calcula confiança global do sistema no contexto atual"""
        
        if not regime_performance:
            # Sem dados → confiança baixa
            return 0.3
        
        # Média ponderada de confiança dos cérebros
        confidences = [m.confidence for m in regime_performance.values()]
        avg_confidence = np.mean(confidences) if confidences else 0.3
        
        # Penalizar por flags de risco
        risk_penalty = len(risk_flags) * 0.1
        
        global_conf = max(0.0, min(1.0, avg_confidence - risk_penalty))
        
        return global_conf

    def _detect_anomalies(self, recent_trades: List[Dict]) -> List[str]:
        """Detecta anomalias no histórico recente de trades"""
        anomalies = []
        
        if not recent_trades or len(recent_trades) < 3:
            return anomalies
        
        pnls = [float(t.get("pnl", 0)) for t in recent_trades[-20:]]  # últimas 20
        
        # Checar por série de perdas
        consecutive_losses = 0
        for pnl in pnls:
            if pnl < -0.1:  # Perda > 0.1%
                consecutive_losses += 1
            else:
                consecutive_losses = 0
            
            if consecutive_losses >= 3:
                anomalies.append(f"3+ consecutive losses detected")
                break
        
        # Checar drawdown abrupto
        cumulative_pnl = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = (cumulative_pnl - running_max)
        max_dd = np.min(drawdown) if len(drawdown) > 0 else 0
        
        if max_dd < -2.0:  # DD > 2%
            anomalies.append(f"High drawdown detected ({max_dd:.1f}%)")
        
        return anomalies

    def _determine_sentiment(self, regime: str, performance: Dict) -> str:
        """Determina sentimento de mercado baseado em performance"""
        
        if regime.startswith("TREND_UP"):
            avg_pf = np.mean([m.profit_factor for m in performance.values()]) if performance else 1.0
            if avg_pf > 1.2:
                return "BULLISH"
            elif avg_pf > 0.9:
                return "NEUTRAL"
            else:
                return "BEARISH"
        
        elif regime.startswith("TREND_DOWN"):
            avg_pf = np.mean([m.profit_factor for m in performance.values()]) if performance else 1.0
            if avg_pf > 1.2:
                return "BEARISH"
            elif avg_pf > 0.9:
                return "NEUTRAL"
            else:
                return "BULLISH"
        
        else:
            return "NEUTRAL"

    def _assess_risk_level(self, risk_flags: List[str], confidence: float) -> str:
        """Avalia nível de risco"""
        
        if confidence < 0.4 or len(risk_flags) >= 3:
            return "HIGH"
        elif confidence < 0.6 or len(risk_flags) >= 1:
            return "MEDIUM"
        else:
            return "LOW"

    def _calculate_confidence(self, num_trades: int) -> float:
        """Calcula confiança baseada no número de trades (bootstrap confidence)"""
        # Cresce logaritmicamente com trades
        if num_trades < self.MIN_TRADES_FOR_CONFIDENCE:
            return 0.3
        return min(1.0, 0.3 + 0.7 * np.log(num_trades) / np.log(100))

    def update_performance(
        self,
        brain_id: str,
        regime: str,
        trades: List[Dict],
    ) -> None:
        """
        Atualiza performance histórica após trades.
        
        Args:
            brain_id: qual cérebro
            regime: em qual regime
            trades: trades executadas
        """
        
        if regime not in self.performance_cache:
            self.performance_cache[regime] = {}
        
        # Calcular métricas
        if not trades:
            return
        
        pnls = [float(t.get("pnl", 0)) for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        total = len(trades)
        win_rate = wins / total if total > 0 else 0
        
        total_gain = sum(p for p in pnls if p > 0)
        total_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = total_gain / total_loss if total_loss > 0 else 1.0 if total_gain > 0 else 0.0
        
        rrs = [
            abs(float(t.get("mfe", 0)) / (abs(float(t.get("mae", 0))) + 0.0001))
            for t in trades if t.get("mfe") and t.get("mae")
        ]
        avg_rr = np.mean(rrs) if rrs else 1.0
        
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # Atualizar cache
        metrics = BrainPerformanceMetrics(
            brain_id=brain_id,
            regime=regime,
            win_rate=float(win_rate),
            profit_factor=float(profit_factor),
            avg_rr=float(avg_rr),
            total_trades=total,
            total_pnl=float(np.sum(pnls)),
            max_drawdown=float(max_dd),
            last_update=datetime.utcnow().isoformat(),
            confidence=self._calculate_confidence(total),
        )
        
        self.performance_cache[regime][brain_id] = metrics
        
        # Persistir
        repo.insert_brain_performance(self.db_path, metrics.to_dict())
        
        logger.info(
            f"Updated {brain_id} in {regime}: WR={win_rate:.1%}, "
            f"PF={profit_factor:.2f}, trades={total}"
        )

    def _log_decision(self, decision: MetaBrainDecision, regime: str) -> None:
        """Persiste decisão no DB"""
        try:
            repo.insert_meta_decision(
                self.db_path,
                regime=regime,
                allow_trading=decision.allow_trading,
                weight_adjustment=json.dumps(decision.weight_adjustment),
                global_confidence=decision.global_confidence,
                reasoning=json.dumps(decision.reasoning),
                risk_level=decision.risk_level,
            )
        except Exception as e:
            logger.warning(f"Erro ao logar decisão do MetaBrain: {e}")
