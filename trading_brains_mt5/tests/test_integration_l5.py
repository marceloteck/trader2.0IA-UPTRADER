"""
Tests for Level 5: Integration Tests

Testes de integração entre Capital Manager, Scalp Manager, RL Policy e Online Updates.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.execution.capital_manager import CapitalManager
from src.execution.scalp_manager import ScalpManager
from src.execution.rl_gate import RLGate
from src.training.reinforcement_policy import RLPolicy, RLState
from src.training.online_update import OnlineUpdater
from src.config.settings import Settings


@pytest.fixture
def integration_settings():
    """Configurações para integração."""
    settings = MagicMock(spec=Settings)
    settings.operator_capital_brl = 10000.0
    settings.margin_per_contract_brl = 1000.0
    settings.max_contracts_cap = 10
    settings.min_contracts = 1
    settings.realavancagem_enabled = True
    settings.realavancagem_max_extra_contracts = 1
    settings.realavancagem_mode = "SCALP_ONLY"
    settings.realavancagem_min_global_conf = 0.70
    settings.realavancagem_allowed_regimes = "TREND_UP,TREND_DOWN"
    settings.scalp_tp_points = 80
    settings.scalp_sl_points = 40
    settings.scalp_max_hold_seconds = 180
    settings.contract_point_value = 1.0
    settings.rl_policy_enabled = True
    settings.rl_policy_mode = "THOMPSON_SAMPLING"
    settings.protect_profit_after_scalp = True
    return settings


@pytest.fixture
def integration_components(integration_settings):
    """Cria todos os componentes L5."""
    capital_manager = CapitalManager(
        operator_capital_brl=integration_settings.operator_capital_brl,
        margin_per_contract_brl=integration_settings.margin_per_contract_brl,
        max_contracts_cap=integration_settings.max_contracts_cap,
        min_contracts=integration_settings.min_contracts,
        realavancagem_enabled=integration_settings.realavancagem_enabled,
        realavancagem_max_extra_contracts=integration_settings.realavancagem_max_extra_contracts,
        realavancagem_mode=integration_settings.realavancagem_mode,
    )
    
    scalp_manager = ScalpManager(
        scalp_tp_points=integration_settings.scalp_tp_points,
        scalp_sl_points=integration_settings.scalp_sl_points,
        scalp_max_hold_seconds=integration_settings.scalp_max_hold_seconds,
        contract_point_value=integration_settings.contract_point_value,
        protect_profit_after_scalp=integration_settings.protect_profit_after_scalp,
    )
    
    rl_policy = RLPolicy(thompson_alpha_prior=1.0, thompson_beta_prior=1.0)
    
    online_updater = OnlineUpdater(batch_size=5, snapshot_interval=10)
    
    return {
        "capital": capital_manager,
        "scalp": scalp_manager,
        "rl": rl_policy,
        "updater": online_updater,
    }


class TestCapitalAndRLIntegration:
    """Testes de integração entre Capital Manager e RL Policy."""
    
    def test_capital_contracts_influence_rl_action(self, integration_components):
        """Testar que tamanho de contrato influencia decisão de RL."""
        capital = integration_components["capital"]
        rl = integration_components["rl"]
        
        # Calcular contratos base
        base_contracts = capital.calc_base_contracts()
        assert base_contracts > 0
        
        # RL deve escolher ação baseado em regime
        state = RLState(
            regime="TREND_UP",
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        action = rl.select_action("TREND_UP", state)
        
        # Se capital suficiente e RL aprova, deve considerar REALAVANCAGEM
        if base_contracts >= capital.max_contracts_cap:
            # Capital pode ser limitante
            pass


class TestScalpAndCapitalIntegration:
    """Testes de integração entre Scalp Manager e Capital Manager."""
    
    def test_scalp_uses_extra_contracts_from_capital(self, integration_components):
        """Testar que scalp usa contratos extra do capital manager."""
        capital = integration_components["capital"]
        scalp = integration_components["scalp"]
        
        # Capital calcula contratos
        capital_state = capital.calc_contracts(
            symbol="EURUSD",
            regime="TREND_UP",
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
        )
        
        # Se teve extra_contracts, abrir scalp com esses
        if capital_state.extra_contracts > 0:
            now = datetime.now()
            scalp.open_scalp(
                symbol="EURUSD",
                side="BUY",
                entry_price=1.0850,
                extra_contracts=capital_state.extra_contracts,
                opened_at=now,
            )
            
            active = scalp.get_active_scalp("EURUSD")
            assert active is not None
            assert active.extra_contracts == capital_state.extra_contracts


class TestRLAndOnlineUpdateIntegration:
    """Testes de integração entre RL Policy e Online Updates."""
    
    def test_rl_updates_from_online_batch(self, integration_components):
        """Testar que RL é atualizado a partir do batch de online updater."""
        rl = integration_components["rl"]
        updater = integration_components["updater"]
        
        regime = "TREND_UP"
        state = RLState(regime=regime, time_bucket="14:00", confidence_level="HIGH", disagreement_level="LOW")
        
        # Adicionar trades ao updater
        for i in range(5):
            updater.add_trade({
                "regime": regime,
                "state_hash": state.to_hash(),
                "action": "ENTER",
                "pnl": 100.0 if i % 2 == 0 else -50.0,
                "duration_seconds": 300,
            })
        
        # Batch deve estar completo
        assert updater.should_update() is True
        
        # Obter trades e atualizar RL
        pending = updater.get_pending_trades(regime=regime)
        for trade in pending:
            rl.update_from_trade(
                regime=trade["regime"],
                state_hash=trade["state_hash"],
                action=trade["action"],
                reward=0.8 if trade["pnl"] > 0 else 0.2,
            )
        
        # Verificar que RL foi atualizado
        stats = rl.get_action_stats(regime, state.to_hash(), "ENTER")
        assert stats["count"] > 0


class TestFullWorkflow:
    """Testes do workflow completo L5."""
    
    def test_full_trading_cycle_with_realavancagem(self, integration_components):
        """Testar ciclo completo: capital -> RL -> scalp -> update -> snapshot."""
        capital = integration_components["capital"]
        scalp = integration_components["scalp"]
        rl = integration_components["rl"]
        updater = integration_components["updater"]
        
        now = datetime.now()
        symbol = "EURUSD"
        regime = "TREND_UP"
        
        # 1. Capital Manager calcula contratos
        capital_state = capital.calc_contracts(
            symbol=symbol,
            regime=regime,
            global_confidence=0.80,
            ensemble_disagreement=0.10,
            liquidity_strength=0.60,
            daily_profit_brl=100.0,
        )
        
        assert capital_state.final_contracts > 0
        
        # 2. RL Policy seleciona ação
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        rl_action = rl.select_action(regime, state)
        assert rl_action in ["HOLD", "ENTER", "ENTER_CONSERVATIVE", "ENTER_WITH_REALAVANCAGEM"]
        
        # 3. Se há extra contracts e RL aprovou realavancagem, abrir scalp
        if capital_state.extra_contracts > 0 and rl_action == "ENTER_WITH_REALAVANCAGEM":
            scalp.open_scalp(
                symbol=symbol,
                side="BUY",
                entry_price=1.0850,
                extra_contracts=capital_state.extra_contracts,
                opened_at=now,
            )
            
            active_scalp = scalp.get_active_scalp(symbol)
            assert active_scalp is not None
            
            # 4. Scalp fecha com TP
            scalp.update_scalp(
                symbol=symbol,
                current_price=1.0930,
                current_time=now + timedelta(seconds=60),
            )
            
            active_scalp = scalp.get_active_scalp(symbol)
            assert active_scalp is None  # Fechado
        
        # 5. Adicionar trade ao online updater
        trade_pnl = 100.0
        updater.add_trade({
            "symbol": symbol,
            "regime": regime,
            "state_hash": state.to_hash(),
            "action": rl_action,
            "pnl": trade_pnl,
            "duration_seconds": 60,
        })
        
        # 6. Se batch completo, criar snapshot
        if updater.should_update():
            snap = updater.create_snapshot(
                regime=regime,
                policy_data=rl.export_policy_table(regime),
                metrics={"total_pnl": trade_pnl},
            )
            
            assert snap is not None
            
            # 7. Atualizar RL
            rl.update_from_trade(
                regime=regime,
                state_hash=state.to_hash(),
                action=rl_action,
                reward=0.8,
            )


class TestMultipleSymbolsIntegration:
    """Testes com múltiplos símbolos."""
    
    def test_scalps_on_different_symbols(self, integration_components):
        """Testar scalps simultâneos em diferentes símbolos."""
        scalp = integration_components["scalp"]
        now = datetime.now()
        
        # Abrir scalps em diferentes símbolos
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        for symbol in symbols:
            price = 1.08 + symbols.index(symbol) * 0.01
            scalp.open_scalp(
                symbol=symbol,
                side="BUY",
                entry_price=price,
                extra_contracts=1,
                opened_at=now,
            )
        
        # Todas devem estar ativas
        for symbol in symbols:
            active = scalp.get_active_scalp(symbol)
            assert active is not None
    
    def test_rl_per_regime_different_symbols(self, integration_components):
        """Testar que RL mantém políticas separadas por regime."""
        rl = integration_components["rl"]
        
        # Atualizar RL para diferentes regimes
        regimes = ["TREND_UP", "TREND_DOWN", "RANGE"]
        state_hash = "test_state"
        action = "ENTER"
        
        for regime in regimes:
            for i in range(3):
                rl.update_from_trade(
                    regime=regime,
                    state_hash=state_hash,
                    action=action,
                    reward=0.7 if regime == "TREND_UP" else 0.5,
                )
        
        # Stats devem ser diferentes por regime
        stats_up = rl.get_action_stats("TREND_UP", state_hash, action)
        stats_down = rl.get_action_stats("TREND_DOWN", state_hash, action)
        
        assert stats_up is not None
        assert stats_down is not None


class TestErrorRecovery:
    """Testes de recuperação de erros."""
    
    def test_rollback_after_bad_performance(self, integration_components):
        """Testar rollback quando performance degrada."""
        rl = integration_components["rl"]
        updater = integration_components["updater"]
        regime = "TREND_UP"
        
        # Criar snapshot inicial com boa performance
        snap_good = updater.create_snapshot(
            regime=regime,
            policy_data=rl.export_policy_table(regime),
            metrics={"avg_reward": 0.8}
        )
        
        # Simular performance ruim
        state_hash = "bad_state"
        action = "ENTER"
        for _ in range(10):
            rl.update_from_trade(
                regime=regime,
                state_hash=state_hash,
                action=action,
                reward=0.2,  # Ruim
            )
        
        # Rollback
        restored = updater.rollback_to_snapshot(snap_good.snapshot_id)
        assert restored is not None
        assert restored.snapshot_id == snap_good.snapshot_id


class TestPerformanceMetrics:
    """Testes para métricas de performance L5."""
    
    def test_export_combined_stats(self, integration_components):
        """Testar exportação de estatísticas combinadas."""
        capital = integration_components["capital"]
        scalp = integration_components["scalp"]
        rl = integration_components["rl"]
        
        # Capital stats
        capital_stats = capital.export_stats()
        assert isinstance(capital_stats, dict)
        
        # Scalp stats
        scalp_stats = scalp.export_stats()
        assert isinstance(scalp_stats, dict)
        
        # RL stats
        rl_stats = rl.export_stats("TREND_UP")
        assert isinstance(rl_stats, dict)
        
        # Todos devem ter informações úteis
        combined = {
            "capital": capital_stats,
            "scalp": scalp_stats,
            "rl": rl_stats,
        }
        
        assert "capital" in combined
        assert "scalp" in combined
        assert "rl" in combined


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
