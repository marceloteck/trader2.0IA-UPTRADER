"""
Self-Diagnosis: Sistema de auto-diagnóstico
Monitora saúde do sistema e detecta quando pausar/reduzir.

V3: IA sabe quando NÃO deve operar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import logging

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HealthReport:
    """Relatório de saúde do sistema"""
    is_healthy: bool
    overall_score: float  # 0-1
    status: str  # "GREEN", "YELLOW", "RED"
    issues: List[str]
    recommendations: List[str]
    metrics: Dict
    last_checked: str


class SelfDiagnosisSystem:
    """
    Monitora saúde do sistema e recomenda ações:
    - GREEN: operar normalmente
    - YELLOW: reduzir tamanho de posição
    - RED: pausar trading completamente
    
    Diagnósticos:
    1. Drawdown excessivo
    2. Taxa de perda muito alta
    3. Degradação de performance
    4. Regime desconhecido
    5. Volatilidade extrema
    6. Falta de dados
    """

    def __init__(self):
        # Limites de alerta
        self.DRAWDOWN_ALERT = 5.0  # 5% → YELLOW
        self.DRAWDOWN_CRITICAL = 10.0  # 10% → RED
        self.MAX_CONSECUTIVE_LOSSES = 3
        self.MAX_LOSS_RATE = 0.4  # 40% loss rate → YELLOW
        self.MIN_TRADES_FOR_ASSESSMENT = 10
        self.PERFORMANCE_DEGRADATION_PCT = 50  # Se cai 50% → YELLOW
        
        # Estado
        self.last_health_check: Optional[datetime] = None
        self.health_history: List[HealthReport] = []

    def diagnose(
        self,
        recent_trades: List[Dict],
        brain_performance: Dict[str, Dict],
        current_regime: str,
        current_volatility: float,
        regime_confidence: float,
        data_staleness_minutes: float,
    ) -> HealthReport:
        """
        Executa diagnóstico completo do sistema.
        
        Args:
            recent_trades: últimas N trades
            brain_performance: {brain_id: {metrics}}
            current_regime: regime detectado
            current_volatility: volatilidade (%)
            regime_confidence: confiança da detecção de regime (0-1)
            data_staleness_minutes: há quanto tempo foi atualizado dados
        
        Returns:
            HealthReport detalhado
        """
        
        issues = []
        recommendations = []
        scores = {}  # Componentes de score
        
        # 1. ANÁLISE DE DRAWDOWN
        # ─────────────────────
        dd_score, dd_issues, dd_recs = self._check_drawdown(recent_trades)
        scores["drawdown"] = dd_score
        issues.extend(dd_issues)
        recommendations.extend(dd_recs)
        
        # 2. ANÁLISE DE TAXA DE PERDA
        # ──────────────────────────
        loss_score, loss_issues, loss_recs = self._check_loss_rate(recent_trades)
        scores["loss_rate"] = loss_score
        issues.extend(loss_issues)
        recommendations.extend(loss_recs)
        
        # 3. ANÁLISE DE DEGRADAÇÃO DE PERFORMANCE
        # ──────────────────────────────────────
        perf_score, perf_issues, perf_recs = self._check_performance_degradation(
            recent_trades, brain_performance
        )
        scores["performance"] = perf_score
        issues.extend(perf_issues)
        recommendations.extend(perf_recs)
        
        # 4. ANÁLISE DE REGIME
        # ──────────────────
        regime_score, regime_issues, regime_recs = self._check_regime(
            current_regime, regime_confidence
        )
        scores["regime"] = regime_score
        issues.extend(regime_issues)
        recommendations.extend(regime_recs)
        
        # 5. ANÁLISE DE VOLATILIDADE
        # ─────────────────────────
        vol_score, vol_issues, vol_recs = self._check_volatility(current_volatility)
        scores["volatility"] = vol_score
        issues.extend(vol_issues)
        recommendations.extend(vol_recs)
        
        # 6. ANÁLISE DE DADOS
        # ──────────────────
        data_score, data_issues, data_recs = self._check_data(data_staleness_minutes)
        scores["data"] = data_score
        issues.extend(data_issues)
        recommendations.extend(data_recs)
        
        # 7. SÍNTESE
        # ─────────
        overall_score = float(np.mean(list(scores.values())))
        
        if len(issues) >= 3 or any("CRITICAL" in issue for issue in issues):
            status = "RED"
            is_healthy = False
        elif len(issues) >= 1 or overall_score < 0.6:
            status = "YELLOW"
            is_healthy = True  # Ainda saudável, mas cauteloso
        else:
            status = "GREEN"
            is_healthy = True
        
        # Remover duplicatas
        issues = list(set(issues))
        recommendations = list(set(recommendations))
        
        report = HealthReport(
            is_healthy=is_healthy,
            overall_score=overall_score,
            status=status,
            issues=issues,
            recommendations=recommendations,
            metrics={
                "component_scores": scores,
                "recent_trades": len(recent_trades),
                "current_volatility": current_volatility,
                "regime_confidence": regime_confidence,
                "data_staleness_minutes": data_staleness_minutes,
            },
            last_checked=datetime.utcnow().isoformat(),
        )
        
        self.health_history.append(report)
        self.last_health_check = datetime.utcnow()
        
        logger.info(
            f"Health check: {status} (score={overall_score:.2f}, "
            f"issues={len(issues)}, recommendations={len(recommendations)})"
        )
        
        return report

    def _check_drawdown(self, trades: List[Dict]) -> tuple:
        """Verifica drawdown recente"""
        
        if not trades or len(trades) < 3:
            return 1.0, [], []
        
        pnls = [float(t.get("pnl", 0)) for t in trades[-50:]]  # Últimas 50
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        max_dd_pct = (max_dd / (abs(max(cumulative)) + 1)) * 100
        
        issues = []
        recommendations = []
        
        if max_dd_pct > self.DRAWDOWN_CRITICAL:
            score = 0.2
            issues.append(f"CRITICAL: Drawdown {max_dd_pct:.1f}% exceeds {self.DRAWDOWN_CRITICAL}%")
            recommendations.append("PAUSE trading immediately, review system")
        elif max_dd_pct > self.DRAWDOWN_ALERT:
            score = 0.5
            issues.append(f"HIGH: Drawdown {max_dd_pct:.1f}%")
            recommendations.append("Reduce position size by 50%")
        else:
            score = 1.0
        
        return score, issues, recommendations

    def _check_loss_rate(self, trades: List[Dict]) -> tuple:
        """Verifica taxa de perdas consecutivas"""
        
        if not trades or len(trades) < self.MIN_TRADES_FOR_ASSESSMENT:
            return 1.0, [], []
        
        pnls = [float(t.get("pnl", 0)) for t in trades[-50:]]
        losses = sum(1 for p in pnls if p < -0.1)
        loss_rate = losses / len(pnls) if pnls else 0
        
        # Verificar perdas consecutivas
        consecutive_losses = 0
        max_consecutive = 0
        for pnl in pnls:
            if pnl < -0.1:
                consecutive_losses += 1
                max_consecutive = max(max_consecutive, consecutive_losses)
            else:
                consecutive_losses = 0
        
        issues = []
        recommendations = []
        
        if max_consecutive >= self.MAX_CONSECUTIVE_LOSSES:
            score = 0.3
            issues.append(f"HIGH: {max_consecutive} consecutive losses")
            recommendations.append("Pause and review signal quality")
        elif loss_rate > self.MAX_LOSS_RATE:
            score = 0.5
            issues.append(f"WARNING: Loss rate {loss_rate:.0%}")
            recommendations.append("Reduce risk per trade")
        else:
            score = 1.0
        
        return score, issues, recommendations

    def _check_performance_degradation(
        self,
        trades: List[Dict],
        brain_performance: Dict[str, Dict],
    ) -> tuple:
        """Detecta degradação de performance recente"""
        
        if not trades or len(trades) < self.MIN_TRADES_FOR_ASSESSMENT:
            return 1.0, [], []
        
        # Dividir em períodos recente vs antigo
        mid = len(trades) // 2
        old_trades = trades[:mid]
        recent_trades = trades[mid:]
        
        def calc_wr(t_list):
            if not t_list:
                return 0.5
            wins = sum(1 for t in t_list if float(t.get("pnl", 0)) > 0)
            return wins / len(t_list)
        
        old_wr = calc_wr(old_trades)
        recent_wr = calc_wr(recent_trades)
        
        if old_wr > 0:
            degradation = (old_wr - recent_wr) / old_wr
        else:
            degradation = 0
        
        issues = []
        recommendations = []
        
        if degradation > self.PERFORMANCE_DEGRADATION_PCT / 100:
            score = 0.4
            issues.append(
                f"PERFORMANCE: Win rate fell {degradation:.0%} "
                f"({old_wr:.0%} → {recent_wr:.0%})"
            )
            recommendations.append("Retrain models or adjust parameters")
            score = 0.4
        else:
            score = 1.0
        
        return score, issues, recommendations

    def _check_regime(self, regime: str, confidence: float) -> tuple:
        """Verifica confiança na detecção de regime"""
        
        issues = []
        recommendations = []
        
        if regime == "UNKNOWN" or regime == "HIGH_VOL":
            score = 0.5
            issues.append(f"REGIME: {regime} (uncertain market)")
            recommendations.append("Reduce position size until regime clears")
        elif confidence < 0.5:
            score = 0.6
            issues.append(f"REGIME: Low confidence ({confidence:.0%}) in {regime}")
            recommendations.append("Wait for regime to stabilize")
        else:
            score = 1.0
        
        return score, issues, recommendations

    def _check_volatility(self, volatility: float) -> tuple:
        """Verifica volatilidade extrema"""
        
        issues = []
        recommendations = []
        
        if volatility > 5.0:
            score = 0.3
            issues.append(f"VOLATILITY: Extremely high ({volatility:.1f}%)")
            recommendations.append("Consider reducing size or pausing")
        elif volatility > 3.0:
            score = 0.6
            issues.append(f"VOLATILITY: High ({volatility:.1f}%)")
            recommendations.append("Use tighter stops")
        else:
            score = 1.0
        
        return score, issues, recommendations

    def _check_data(self, staleness_minutes: float) -> tuple:
        """Verifica atualização de dados"""
        
        issues = []
        recommendations = []
        
        if staleness_minutes > 30:
            score = 0.1
            issues.append(f"CRITICAL: Data {staleness_minutes:.0f} minutes stale")
            recommendations.append("PAUSE - reconnect data feed")
        elif staleness_minutes > 5:
            score = 0.5
            issues.append(f"WARNING: Data {staleness_minutes:.0f} minutes delayed")
            recommendations.append("Monitor data connection")
        else:
            score = 1.0
        
        return score, issues, recommendations

    def get_recommended_position_size_factor(self, health_status: str) -> float:
        """
        Retorna fator multiplicador de tamanho de posição baseado em saúde.
        
        GREEN: 1.0 (100%)
        YELLOW: 0.5 (50%)
        RED: 0.0 (pausado)
        """
        
        factors = {
            "GREEN": 1.0,
            "YELLOW": 0.5,
            "RED": 0.0,
        }
        
        return factors.get(health_status, 0.5)

    def get_health_trend(self, lookback: int = 10) -> str:
        """
        Analisa tendência de saúde.
        
        Returns:
            "IMPROVING", "DEGRADING", "STABLE"
        """
        
        if len(self.health_history) < 2:
            return "STABLE"
        
        recent = self.health_history[-lookback:]
        scores = [h.overall_score for h in recent]
        
        first_half_avg = np.mean(scores[: len(scores) // 2])
        second_half_avg = np.mean(scores[len(scores) // 2 :])
        
        if second_half_avg > first_half_avg + 0.1:
            return "IMPROVING"
        elif second_half_avg < first_half_avg - 0.1:
            return "DEGRADING"
        else:
            return "STABLE"
