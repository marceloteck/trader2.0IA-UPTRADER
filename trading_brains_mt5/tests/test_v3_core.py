"""
Testes para módulos V3

Run: pytest tests/test_v3_*.py -v
"""

import pytest
import json
from datetime import datetime, timedelta
import tempfile
import os

import numpy as np
import pandas as pd

from src.brains.meta_brain import MetaBrain, BrainPerformanceMetrics, MetaBrainDecision
from src.features.regime_detector import RegimeDetector, RegimeState
from src.training.reinforcement import LightReinforcementLearner, RLAction
from src.models.decay import KnowledgeDecayPolicy, TradeDecayAnalyzer
from src.monitoring.self_diagnosis import SelfDiagnosisSystem, HealthReport
from src.config.settings import Settings


@pytest.fixture
def temp_db():
    """Cria banco de dados temporário para testes"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def settings():
    """Cria settings para testes"""
    return Settings()


class TestMetaBrain:
    """Testes para MetaBrain"""

    def test_initialization(self, temp_db, settings):
        """Testa inicialização do MetaBrain"""
        brain = MetaBrain(settings, temp_db)
        
        assert brain is not None
        assert brain.MIN_TRADES_FOR_CONFIDENCE == 5
        assert brain.DECAY_HALF_LIFE_DAYS == 30
        assert brain.MIN_CONFIDENCE == 0.3

    def test_evaluate_with_no_history(self, temp_db, settings):
        """Testa avaliação sem histórico (cérebros novos)"""
        brain = MetaBrain(settings, temp_db)
        
        decision = brain.evaluate(
            current_regime="TREND_UP",
            current_hour=15,
            current_volatility=1.5,
            brain_scores={"Elliott": 0.8, "Gann": 0.6},
            recent_trades=[]
        )
        
        assert isinstance(decision, MetaBrainDecision)
        assert decision.allow_trading == True  # Confiança baixa mas permite
        assert "Elliott" in decision.weight_adjustment
        assert decision.weight_adjustment["Elliott"] == 1.0  # Novo = peso 1.0

    def test_anomaly_detection(self, temp_db, settings):
        """Testa detecção de anomalias (perdas consecutivas)"""
        brain = MetaBrain(settings, temp_db)
        
        # Criar trades com perdas consecutivas
        trades = [
            {"pnl": -0.5, "mfe": 10, "mae": 50},
            {"pnl": -0.3, "mfe": 5, "mae": 40},
            {"pnl": -0.4, "mfe": 8, "mae": 45},
            {"pnl": 0.1, "mfe": 20, "mae": 5},
        ]
        
        decision = brain.evaluate(
            current_regime="TREND_UP",
            current_hour=10,
            current_volatility=2.0,
            brain_scores={"test": 0.5},
            recent_trades=trades
        )
        
        # Deve detectar anomalia
        assert any("consecutive" in s.lower() for s in decision.reasoning)

    def test_performance_update(self, temp_db, settings):
        """Testa atualização de performance histórica"""
        brain = MetaBrain(settings, temp_db)
        
        trades = [
            {"pnl": 0.5, "mfe": 100, "mae": 10},
            {"pnl": 0.3, "mfe": 50, "mae": 5},
            {"pnl": -0.2, "mfe": 20, "mae": 30},
        ]
        
        brain.update_performance("TestBrain", "TREND_UP", trades)
        
        # Verificar se foi atualizado no cache
        assert "TREND_UP" in brain.performance_cache
        assert "TestBrain" in brain.performance_cache["TREND_UP"]
        
        metrics = brain.performance_cache["TREND_UP"]["TestBrain"]
        assert metrics.total_trades == 3
        assert metrics.win_rate == pytest.approx(2/3, abs=0.01)


class TestRegimeDetector:
    """Testes para Regime Detector"""

    def test_initialization(self, temp_db, settings):
        """Testa inicialização"""
        detector = RegimeDetector(settings, temp_db)
        
        assert detector is not None
        assert detector.use_hmm in [True, False]  # Depende de hmmlearn

    def test_feature_extraction(self, temp_db, settings):
        """Testa extração de features"""
        detector = RegimeDetector(settings, temp_db)
        
        # Criar dados de teste (tendência de alta)
        dates = pd.date_range("2024-01-01", periods=100)
        df = pd.DataFrame({
            "open": np.linspace(100, 120, 100),
            "high": np.linspace(101, 121, 100),
            "low": np.linspace(99, 119, 100),
            "close": np.linspace(100.5, 120.5, 100),
            "volume": np.ones(100) * 1000,
        }, index=dates)
        
        features = detector._extract_features(df)
        
        assert "ma_diff" in features
        assert "volatility" in features
        assert "trend_direction" in features
        assert features["trend_direction"] > 0  # Tendência de alta

    def test_regime_detection_uptrend(self, temp_db, settings):
        """Testa detecção de tendência de alta"""
        detector = RegimeDetector(settings, temp_db)
        
        # Dados com tendência clara de alta
        dates = pd.date_range("2024-01-01", periods=100)
        df = pd.DataFrame({
            "open": np.linspace(100, 120, 100),
            "high": np.linspace(101, 121, 100),
            "low": np.linspace(99, 119, 100),
            "close": np.linspace(100.5, 120.5, 100),
            "volume": np.ones(100) * 1000,
        }, index=dates)
        
        state = detector.detect(df, hour=15)
        
        assert state.regime == "TREND_UP"
        assert state.confidence > 0.6
        assert state.trend_direction > 0

    def test_regime_detection_range(self, temp_db, settings):
        """Testa detecção de consolidação"""
        detector = RegimeDetector(settings, temp_db)
        
        # Dados com range-bound
        dates = pd.date_range("2024-01-01", periods=100)
        close = np.sin(np.linspace(0, 4 * np.pi, 100)) * 2 + 100  # Oscilação
        df = pd.DataFrame({
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.ones(100) * 1000,
        }, index=dates)
        
        state = detector.detect(df, hour=15)
        
        assert state.regime in ["RANGE", "UNKNOWN"]


class TestReinforcementLearner:
    """Testes para RL"""

    def test_initialization(self, temp_db, settings):
        """Testa inicialização"""
        learner = LightReinforcementLearner(settings, temp_db)
        
        assert learner is not None
        assert len(learner.q_table) == 0  # Novo
        assert learner.LEARNING_RATE == 0.1

    def test_get_action(self, temp_db, settings):
        """Testa recomendação de ação"""
        learner = LightReinforcementLearner(settings, temp_db)
        
        action = learner.get_action(
            regime="TREND_UP",
            hour=15,
            volatility=1.5,
            trend=0.05,
            rsi=55,
            base_confidence=0.8
        )
        
        assert isinstance(action, RLAction)
        assert action.action in ["ENTER", "SKIP"]
        assert 0 <= action.confidence <= 1

    def test_state_discretization(self, temp_db, settings):
        """Testa discretização de estado"""
        learner = LightReinforcementLearner(settings, temp_db)
        
        state1 = learner._discretize_state("TREND_UP", 15, 1.2, 0.05, 55)
        state2 = learner._discretize_state("TREND_UP", 15, 1.2, 0.05, 55)
        
        # Mesmo estado deve ter mesmo hash
        assert state1.hash() == state2.hash()
        
        # Estados diferentes devem ter hashes diferentes
        state3 = learner._discretize_state("TREND_DOWN", 15, 1.2, 0.05, 55)
        assert state1.hash() != state3.hash()

    def test_q_learning_update(self, temp_db, settings):
        """Testa atualização Q-learning"""
        learner = LightReinforcementLearner(settings, temp_db)
        
        # Fazer uma ação
        learner.update(
            regime="TREND_UP",
            hour=15,
            volatility=1.5,
            trend=0.05,
            rsi=55,
            action_taken="ENTER",
            reward=1.0,  # Ganho
            next_state_hash=None
        )
        
        # Verificar se Q-table foi atualizado
        state = learner._discretize_state("TREND_UP", 15, 1.5, 0.05, 55)
        assert state.hash() in learner.q_table
        assert learner.q_table[state.hash()]["ENTER"] > 0


class TestKnowledgeDecay:
    """Testes para Knowledge Decay"""

    def test_initialization(self):
        """Testa inicialização"""
        policy = KnowledgeDecayPolicy(half_life_days=30)
        
        assert policy.half_life_days == 30

    def test_temporal_decay(self):
        """Testa decay temporal"""
        policy = KnowledgeDecayPolicy(half_life_days=30)
        
        now = datetime.utcnow().isoformat()
        past_30_days = (datetime.utcnow() - timedelta(days=30)).isoformat()
        past_60_days = (datetime.utcnow() - timedelta(days=60)).isoformat()
        
        decay_now = policy.temporal_decay(now, now)
        decay_30 = policy.temporal_decay(past_30_days, now)
        decay_60 = policy.temporal_decay(past_60_days, now)
        
        assert decay_now == pytest.approx(1.0)
        assert decay_30 == pytest.approx(0.5, rel=0.01)  # 50% aos 30 dias
        assert decay_60 < decay_30  # Menos com mais idade

    def test_regime_aware_decay(self):
        """Testa decay por mudança de regime"""
        policy = KnowledgeDecayPolicy(regime_change_decay=0.7)
        
        # Mesmo regime: sem decay
        decay_same = policy.regime_aware_decay("TREND_UP", "TREND_UP", 10)
        assert decay_same == 1.0
        
        # Regime diferente: decay
        decay_diff = policy.regime_aware_decay("TREND_UP", "TREND_DOWN", 10)
        assert decay_diff < 1.0

    def test_combined_decay(self):
        """Testa decay combinado"""
        policy = KnowledgeDecayPolicy()
        
        now = datetime.utcnow().isoformat()
        old = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        # Conhecimento recente no mesmo regime com boa performance
        decay_good = policy.combined_decay(
            timestamp=now,
            knowledge_regime="TREND_UP",
            current_regime="TREND_UP",
            regime_duration=20,
            current_win_rate=0.55,
            previous_win_rate=0.50,
            current_volatility=1.5,
        )
        
        # Conhecimento antigo em regime diferente com performance ruim
        decay_bad = policy.combined_decay(
            timestamp=old,
            knowledge_regime="TREND_DOWN",
            current_regime="TREND_UP",
            regime_duration=100,
            current_win_rate=0.30,
            previous_win_rate=0.60,
            current_volatility=4.0,
        )
        
        assert decay_good > decay_bad


class TestSelfDiagnosis:
    """Testes para Self-Diagnosis"""

    def test_initialization(self):
        """Testa inicialização"""
        system = SelfDiagnosisSystem()
        
        assert system is not None
        assert system.DRAWDOWN_CRITICAL == 10.0

    def test_health_check_green(self):
        """Testa diagnóstico GREEN"""
        system = SelfDiagnosisSystem()
        
        # Trades com performance boa
        trades = [
            {"pnl": 0.5, "opened_at": "2024-01-01T10:00"},
            {"pnl": 0.3, "opened_at": "2024-01-01T11:00"},
            {"pnl": 0.4, "opened_at": "2024-01-01T12:00"},
            {"pnl": 0.2, "opened_at": "2024-01-01T13:00"},
        ]
        
        report = system.diagnose(
            recent_trades=trades,
            brain_performance={},
            current_regime="TREND_UP",
            current_volatility=1.5,
            regime_confidence=0.85,
            data_staleness_minutes=0.5
        )
        
        assert report.status == "GREEN"
        assert report.is_healthy == True
        assert report.overall_score > 0.7

    def test_health_check_red(self):
        """Testa diagnóstico RED"""
        system = SelfDiagnosisSystem()
        
        # Trades com muitas perdas e alto drawdown
        trades = [
            {"pnl": -0.5, "opened_at": "2024-01-01T10:00"},
            {"pnl": -0.4, "opened_at": "2024-01-01T11:00"},
            {"pnl": -0.6, "opened_at": "2024-01-01T12:00"},
            {"pnl": -0.3, "opened_at": "2024-01-01T13:00"},
        ]
        
        report = system.diagnose(
            recent_trades=trades,
            brain_performance={},
            current_regime="UNKNOWN",
            current_volatility=5.5,
            regime_confidence=0.3,
            data_staleness_minutes=40
        )
        
        assert report.status == "RED"
        assert report.is_healthy == False

    def test_position_size_factor(self):
        """Testa cálculo de position size factor"""
        system = SelfDiagnosisSystem()
        
        assert system.get_recommended_position_size_factor("GREEN") == 1.0
        assert system.get_recommended_position_size_factor("YELLOW") == 0.5
        assert system.get_recommended_position_size_factor("RED") == 0.0

    def test_health_trend(self):
        """Testa detecção de tendência de saúde"""
        system = SelfDiagnosisSystem()
        
        # Simular melhoria
        for i in range(5):
            report = HealthReport(
                is_healthy=True,
                overall_score=0.5 + i * 0.1,  # Crescendo
                status="YELLOW",
                issues=[],
                recommendations=[],
                metrics={},
                last_checked=datetime.utcnow().isoformat(),
            )
            system.health_history.append(report)
        
        trend = system.get_health_trend()
        assert trend == "IMPROVING"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
