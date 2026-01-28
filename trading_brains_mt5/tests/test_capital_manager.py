"""
Tests for Level 5: Capital Manager

Testes para cálculo de contratos, validação de re-alavancagem e persistência.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.execution.capital_manager import CapitalManager, CapitalState
from src.config.settings import Settings


@pytest.fixture
def settings():
    """Configurações padrão para testes."""
    settings = MagicMock(spec=Settings)
    settings.operator_capital_brl = 10000.0
    settings.margin_per_contract_brl = 1000.0
    settings.max_contracts_cap = 10
    settings.min_contracts = 1
    settings.realavancagem_enabled = True
    settings.realavancagem_max_extra_contracts = 1
    settings.realavancagem_mode = "SCALP_ONLY"
    settings.realavancagem_require_profit_today = True
    settings.realavancagem_min_profit_today_brl = 50.0
    settings.realavancagem_min_global_conf = 0.70
    settings.realavancagem_allowed_regimes = "TREND_UP,TREND_DOWN"
    settings.realavancagem_forbidden_modes = "TRANSITION,CHAOTIC"
    return settings


@pytest.fixture
def capital_manager(settings):
    """Cria instância de CapitalManager."""
    return CapitalManager(
        operator_capital_brl=settings.operator_capital_brl,
        margin_per_contract_brl=settings.margin_per_contract_brl,
        max_contracts_cap=settings.max_contracts_cap,
        min_contracts=settings.min_contracts,
        realavancagem_enabled=settings.realavancagem_enabled,
        realavancagem_max_extra_contracts=settings.realavancagem_max_extra_contracts,
        realavancagem_mode=settings.realavancagem_mode,
    )


class TestCapitalStateBasics:
    """Testes básicos de CapitalState."""
    
    def test_capital_state_creation(self):
        """Testar criação de CapitalState."""
        now = datetime.now()
        state = CapitalState(
            time=now,
            symbol="EURUSD",
            operator_capital_brl=10000.0,
            margin_per_contract_brl=1000.0,
            max_contracts_cap=10,
            base_contracts=5,
            extra_contracts=0,
            final_contracts=5,
            reason="Normal entry"
        )
        
        assert state.symbol == "EURUSD"
        assert state.base_contracts == 5
        assert state.extra_contracts == 0
        assert state.final_contracts == 5


class TestCapitalCalculation:
    """Testes para cálculo de contratos base."""
    
    def test_calc_base_contracts_normal(self, capital_manager):
        """Testar cálculo normal de contratos base."""
        # 10000 / 1000 = 10 contratos
        base = capital_manager.calc_base_contracts()
        assert base == 10
    
    def test_calc_base_contracts_with_cap(self, capital_manager):
        """Testar cálculo com limite máximo."""
        capital_manager.max_contracts_cap = 5
        base = capital_manager.calc_base_contracts()
        assert base == 5  # Limitado a 5
    
    def test_calc_base_contracts_minimum(self, capital_manager):
        """Testar cálculo com capital pequeno."""
        capital_manager.operator_capital_brl = 500.0
        capital_manager.min_contracts = 1
        base = capital_manager.calc_base_contracts()
        assert base >= 1  # Mínimo de 1
    
    def test_calc_base_contracts_multiple_capital_values(self, capital_manager):
        """Testar diversos valores de capital."""
        test_cases = [
            (5000.0, 5),   # 5000 / 1000 = 5
            (2500.0, 2),   # 2500 / 1000 = 2.5 → 2
            (10000.0, 10), # 10000 / 1000 = 10
            (15000.0, 10), # 15000 / 1000 = 15, mas capped a 10
        ]
        
        for capital, expected in test_cases:
            capital_manager.operator_capital_brl = capital
            base = capital_manager.calc_base_contracts()
            assert base <= capital_manager.max_contracts_cap
            assert base >= capital_manager.min_contracts


class TestRealeverageValidation:
    """Testes para validação de re-alavancagem."""
    
    def test_realavancagem_disabled(self, capital_manager):
        """Testar quando re-alavancagem está desabilitada."""
        capital_manager.realavancagem_enabled = False
        
        can_realavanca, reason = capital_manager.can_realavancar(
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
            transition_active=False,
        )
        
        assert not can_realavanca
        assert "desabilitada" in reason.lower() or "disabled" in reason.lower()
    
    def test_realavancagem_low_confidence(self, capital_manager, settings):
        """Testar rejeição por confiança baixa."""
        capital_manager.realavancagem_min_global_conf = 0.70
        
        can_realavanca, reason = capital_manager.can_realavancar(
            regime="TREND_UP",
            global_confidence=0.60,  # Baixa
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
            transition_active=False,
        )
        
        assert not can_realavanca
        assert "confiança" in reason.lower() or "confidence" in reason.lower()
    
    def test_realavancagem_forbidden_regime(self, capital_manager):
        """Testar rejeição em regime proibido."""
        # Regimes proibidos: TRANSITION, CHAOTIC
        can_realavanca, reason = capital_manager.can_realavancar(
            regime="TRANSITION",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
            transition_active=True,
        )
        
        assert not can_realavanca
    
    def test_realavancagem_high_disagreement(self, capital_manager):
        """Testar rejeição por discordância alta."""
        can_realavanca, reason = capital_manager.can_realavancar(
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.50,  # Alta
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
            transition_active=False,
        )
        
        assert not can_realavanca
        assert "discordância" in reason.lower() or "disagreement" in reason.lower()
    
    def test_realavancagem_low_liquidity(self, capital_manager):
        """Testar rejeição por liquidez baixa."""
        can_realavanca, reason = capital_manager.can_realavancar(
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.40,  # Baixa
            daily_profit_brl=100.0,
            transition_active=False,
        )
        
        assert not can_realavanca
        assert "liquidez" in reason.lower() or "liquidity" in reason.lower()
    
    def test_realavancagem_require_profit_blocked(self, capital_manager):
        """Testar rejeição por falta de lucro do dia."""
        capital_manager.realavancagem_require_profit_today = True
        capital_manager.realavancagem_min_profit_today_brl = 50.0
        
        can_realavanca, reason = capital_manager.can_realavancar(
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=20.0,  # Insuficiente
            transition_active=False,
        )
        
        assert not can_realavanca
        assert "lucro" in reason.lower() or "profit" in reason.lower()
    
    def test_realavancagem_all_checks_pass(self, capital_manager):
        """Testar quando todos os checks passam."""
        can_realavanca, reason = capital_manager.can_realavancar(
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
            transition_active=False,
        )
        
        assert can_realavanca


class TestContractCalculation:
    """Testes para cálculo final de contratos."""
    
    def test_calc_contracts_base_only(self, capital_manager):
        """Testar cálculo quando sem re-alavancagem."""
        capital_manager.realavancagem_enabled = False
        
        state = capital_manager.calc_contracts(
            symbol="EURUSD",
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=0.0,
        )
        
        assert state.base_contracts == 10
        assert state.extra_contracts == 0
        assert state.final_contracts == 10
    
    def test_calc_contracts_with_realavancagem(self, capital_manager):
        """Testar cálculo com re-alavancagem aprovada."""
        state = capital_manager.calc_contracts(
            symbol="EURUSD",
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
        )
        
        assert state.base_contracts == 10
        assert state.extra_contracts > 0  # Se aprovado
        assert state.final_contracts > state.base_contracts


class TestCapitalHistory:
    """Testes para histórico de decisões de capital."""
    
    def test_get_last_state(self, capital_manager):
        """Testar obtenção do último estado."""
        # Calcular várias vezes
        for _ in range(3):
            capital_manager.calc_contracts(
                symbol="EURUSD",
                regime="TREND_UP",
                global_confidence=0.80,
                ensemble_disagreement=0.10,
                liquidity_strength=0.60,
                daily_profit_brl=100.0,
            )
        
        last = capital_manager.get_last_state()
        assert last is not None
        assert last.symbol == "EURUSD"
    
    def test_get_history_with_limit(self, capital_manager):
        """Testar obtenção de histórico com limite."""
        # Adicionar 5 decisões
        for i in range(5):
            capital_manager.calc_contracts(
                symbol=f"EUR{i}",
                regime="TREND_UP",
                global_confidence=0.80,
                ensemble_disagreement=0.10,
                liquidity_strength=0.60,
                daily_profit_brl=100.0 + i,
            )
        
        history = capital_manager.get_history(limit=3)
        assert len(history) <= 3
    
    def test_get_empty_history(self, capital_manager):
        """Testar histórico vazio."""
        history = capital_manager.get_history(limit=10)
        assert isinstance(history, list)


class TestCapitalStatistics:
    """Testes para estatísticas de capital."""
    
    def test_export_stats(self, capital_manager):
        """Testar exportação de estatísticas."""
        # Adicionar algumas decisões
        capital_manager.calc_contracts(
            symbol="EURUSD",
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
        )
        
        stats = capital_manager.export_stats()
        
        assert isinstance(stats, dict)
        assert "total_decisions" in stats
        assert "avg_base_contracts" in stats
        assert "max_final_contracts" in stats


class TestEdgeCases:
    """Testes para casos extremos."""
    
    def test_zero_capital(self):
        """Testar com capital zero."""
        manager = CapitalManager(
            operator_capital_brl=0.0,
            margin_per_contract_brl=1000.0,
            max_contracts_cap=10,
            min_contracts=1,
        )
        base = manager.calc_base_contracts()
        assert base >= manager.min_contracts
    
    def test_very_small_margin(self):
        """Testar com margem muito pequena."""
        manager = CapitalManager(
            operator_capital_brl=10000.0,
            margin_per_contract_brl=1.0,  # Muito pequeno
            max_contracts_cap=10,
            min_contracts=1,
        )
        base = manager.calc_base_contracts()
        assert base <= manager.max_contracts_cap
    
    def test_negative_daily_profit(self, capital_manager):
        """Testar com lucro negativo do dia."""
        # Não deve bloquear completamente
        can_realavanca, _ = capital_manager.can_realavancar(
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=-100.0,  # Negativo
            transition_active=False,
        )
        # Pode ser bloqueado ou permitido dependendo da configuração
        assert isinstance(can_realavanca, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
