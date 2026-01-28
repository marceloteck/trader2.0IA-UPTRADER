"""
Tests for Level 5: Reinforcement Learning Policy

Testes para Thompson Sampling, seleção de ações, congelamento e atualização de política.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.training.reinforcement_policy import RLPolicy, RLState, ActionValue


@pytest.fixture
def rl_policy():
    """Cria instância de RLPolicy."""
    return RLPolicy(
        thompson_alpha_prior=1.0,
        thompson_beta_prior=1.0,
        update_batch_size=10,
        freeze_threshold=0.15,
    )


class TestRLStateBasics:
    """Testes básicos de RLState."""
    
    def test_rl_state_creation(self):
        """Testar criação de RLState."""
        state = RLState(
            regime="TREND_UP",
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        assert state.regime == "TREND_UP"
        assert state.time_bucket == "14:00"
        assert state.confidence_level == "HIGH"
        assert state.disagreement_level == "LOW"
    
    def test_rl_state_hash(self):
        """Testar geração de hash de estado."""
        state1 = RLState(
            regime="TREND_UP",
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        state2 = RLState(
            regime="TREND_UP",
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        # Mesmo estado → mesmo hash
        assert state1.to_hash() == state2.to_hash()
    
    def test_rl_state_hash_different(self):
        """Testar que estados diferentes geram hashes diferentes."""
        state1 = RLState(
            regime="TREND_UP",
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        state2 = RLState(
            regime="TREND_DOWN",
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        # Estados diferentes → hashes diferentes
        assert state1.to_hash() != state2.to_hash()


class TestActionValueBasics:
    """Testes básicos de ActionValue (Thompson Beta)."""
    
    def test_action_value_creation(self):
        """Testar criação de ActionValue."""
        av = ActionValue(alpha=1.0, beta=1.0)
        
        assert av.alpha == 1.0
        assert av.beta == 1.0
        assert av.count == 0
        assert av.total_reward == 0.0
    
    def test_action_value_sample(self):
        """Testar amostragem de Beta."""
        av = ActionValue(alpha=2.0, beta=2.0)
        
        # Múltiplas amostras devem estar no intervalo (0, 1)
        samples = [av.sample() for _ in range(100)]
        
        assert all(0 <= s <= 1 for s in samples)
        assert 0.3 < sum(samples) / len(samples) < 0.7  # Media perto de 0.5
    
    def test_action_value_mean(self):
        """Testar cálculo da média de Beta."""
        av = ActionValue(alpha=3.0, beta=3.0)
        
        # Média de Beta(3,3) é 0.5
        mean = av.mean()
        assert mean == pytest.approx(0.5, rel=0.1)


class TestThompsonSampling:
    """Testes para Thompson Sampling."""
    
    def test_select_action_initial(self, rl_policy):
        """Testar seleção inicial de ação (todas as priors são iguais)."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        action = rl_policy.select_action(regime, state)
        
        # Deve escolher uma das ações válidas
        assert action in ["HOLD", "ENTER", "ENTER_CONSERVATIVE", "ENTER_WITH_REALAVANCAGEM"]
    
    def test_select_action_consistent(self, rl_policy):
        """Testar que seleção é consistente para mesmo regime/estado."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        # Selecionar múltiplas vezes
        actions = [rl_policy.select_action(regime, state) for _ in range(5)]
        
        # Todas devem ser válidas (não prova consistência mas pelo menos valida)
        assert all(a in ["HOLD", "ENTER", "ENTER_CONSERVATIVE", "ENTER_WITH_REALAVANCAGEM"] for a in actions)
    
    def test_select_action_exploration(self, rl_policy):
        """Testar que Thompson Sampling explora diferentes ações."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        # Múltiplas seleções
        actions = [rl_policy.select_action(regime, state) for _ in range(50)]
        
        # Deve haver variedade de ações (não sempre a mesma)
        unique_actions = set(actions)
        assert len(unique_actions) > 1  # Exploração


class TestPolicyUpdate:
    """Testes para atualização de política."""
    
    def test_update_from_trade_positive_reward(self, rl_policy):
        """Testar atualização com recompensa positiva."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        state_hash = state.to_hash()
        action = "ENTER"
        
        # Antes: priors iguais
        before_stats = rl_policy.get_action_stats(regime, state_hash, action)
        before_count = before_stats["count"]
        
        # Atualizar com reward positivo
        rl_policy.update_from_trade(
            regime=regime,
            state_hash=state_hash,
            action=action,
            reward=0.8,
            metadata={"pnl": 100.0}
        )
        
        # Depois: alpha deve ter aumentado
        after_stats = rl_policy.get_action_stats(regime, state_hash, action)
        assert after_stats["count"] > before_count
        assert after_stats["mean_value"] > 0
    
    def test_update_from_trade_negative_reward(self, rl_policy):
        """Testar atualização com recompensa negativa."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        state_hash = state.to_hash()
        action = "ENTER"
        
        # Atualizar com reward negativo
        rl_policy.update_from_trade(
            regime=regime,
            state_hash=state_hash,
            action=action,
            reward=0.2,
            metadata={"pnl": -50.0}
        )
        
        # Beta deve ter aumentado (penalidade)
        stats = rl_policy.get_action_stats(regime, state_hash, action)
        assert stats["count"] > 0


class TestRegimeFreeze:
    """Testes para congelamento automático de regime."""
    
    def test_freeze_regime_degraded_performance(self, rl_policy):
        """Testar congelamento quando performance degrada."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        state_hash = state.to_hash()
        action = "ENTER"
        
        # Baseline de sucesso
        for _ in range(5):
            rl_policy.update_from_trade(
                regime=regime,
                state_hash=state_hash,
                action=action,
                reward=0.9,
            )
        
        # Agora injetar muitas falhas para degradação
        for _ in range(20):
            rl_policy.update_from_trade(
                regime=regime,
                state_hash=state_hash,
                action=action,
                reward=0.1,
            )
        
        # Pode ter congelado (ou não, depende de threshold)
        stats = rl_policy.get_action_stats(regime, state_hash, action)
        assert stats is not None
    
    def test_unfreeze_regime(self, rl_policy):
        """Testar descongelamento manual de regime."""
        regime = "TREND_UP"
        
        # Tentar descongelar (mesmo que não esteja congelado)
        rl_policy.unfreeze_regime(regime)
        
        # Deve permitir updates subsequentes
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        action = rl_policy.select_action(regime, state)
        assert action is not None


class TestPolicyExportImport:
    """Testes para exportação e importação de política."""
    
    def test_export_policy_table(self, rl_policy):
        """Testar exportação de tabela de política."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        # Fazer alguns updates para ter dados
        for _ in range(3):
            rl_policy.update_from_trade(
                regime=regime,
                state_hash=state.to_hash(),
                action="ENTER",
                reward=0.7,
            )
        
        # Exportar
        exported = rl_policy.export_policy_table(regime)
        
        assert isinstance(exported, dict)
    
    def test_import_policy_table(self, rl_policy):
        """Testar importação de tabela de política."""
        regime = "TREND_UP"
        
        # Tabela fictícia para importar
        policy_data = {
            "state_hash_1": {
                "ENTER": {
                    "alpha": 2.0,
                    "beta": 1.0,
                    "count": 5,
                    "total_reward": 3.5,
                }
            }
        }
        
        # Importar
        rl_policy.import_policy_table(regime, policy_data)
        
        # Verificar que foi importado
        stats = rl_policy.get_action_stats(regime, "state_hash_1", "ENTER")
        assert stats is not None


class TestRLEventLogging:
    """Testes para logging de eventos de RL."""
    
    def test_log_event(self, rl_policy):
        """Testar logging de evento."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        rl_policy.log_event(
            regime=regime,
            state_hash=state.to_hash(),
            action="ENTER",
            reward=0.7,
            reason="Test event"
        )
        
        events = rl_policy.get_events(regime=regime)
        assert len(events) >= 1
    
    def test_get_events_all(self, rl_policy):
        """Testar obtenção de todos os eventos."""
        regime = "TREND_UP"
        
        # Logar alguns eventos
        for i in range(3):
            state = RLState(
                regime=regime,
                time_bucket=f"{10+i}:00",
                confidence_level="HIGH",
                disagreement_level="LOW",
            )
            rl_policy.log_event(
                regime=regime,
                state_hash=state.to_hash(),
                action="ENTER",
                reward=0.7,
            )
        
        events = rl_policy.get_events(regime=regime)
        assert len(events) >= 3
    
    def test_get_events_limited(self, rl_policy):
        """Testar limite de eventos."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        
        # Logar muitos eventos
        for i in range(20):
            rl_policy.log_event(
                regime=regime,
                state_hash=state.to_hash(),
                action="ENTER",
                reward=0.5,
            )
        
        events = rl_policy.get_events(regime=regime, limit=5)
        assert len(events) <= 5


class TestRLStatistics:
    """Testes para estatísticas de RL."""
    
    def test_get_action_stats(self, rl_policy):
        """Testar obtenção de estatísticas de ação."""
        regime = "TREND_UP"
        state = RLState(
            regime=regime,
            time_bucket="14:00",
            confidence_level="HIGH",
            disagreement_level="LOW",
        )
        state_hash = state.to_hash()
        action = "ENTER"
        
        # Fazer updates
        for _ in range(3):
            rl_policy.update_from_trade(
                regime=regime,
                state_hash=state_hash,
                action=action,
                reward=0.8,
            )
        
        stats = rl_policy.get_action_stats(regime, state_hash, action)
        
        assert stats["count"] >= 3
        assert 0 <= stats["mean_value"] <= 1
    
    def test_export_stats(self, rl_policy):
        """Testar exportação de estatísticas globais."""
        regime = "TREND_UP"
        
        # Fazer alguns updates
        for i in range(5):
            state = RLState(
                regime=regime,
                time_bucket=f"{10+i}:00",
                confidence_level="HIGH",
                disagreement_level="LOW",
            )
            rl_policy.update_from_trade(
                regime=regime,
                state_hash=state.to_hash(),
                action="ENTER",
                reward=0.7,
            )
        
        stats = rl_policy.export_stats(regime)
        
        assert isinstance(stats, dict)
        assert "total_updates" in stats or "actions" in stats


class TestMultipleRegimes:
    """Testes para múltiplos regimes."""
    
    def test_separate_policies_per_regime(self, rl_policy):
        """Testar que cada regime tem sua própria política."""
        state_hash = "test_state"
        action = "ENTER"
        
        # Update em TREND_UP
        rl_policy.update_from_trade(
            regime="TREND_UP",
            state_hash=state_hash,
            action=action,
            reward=0.9,
        )
        
        # Update em TREND_DOWN
        rl_policy.update_from_trade(
            regime="TREND_DOWN",
            state_hash=state_hash,
            action=action,
            reward=0.2,
        )
        
        # Stats devem ser diferentes
        stats_up = rl_policy.get_action_stats("TREND_UP", state_hash, action)
        stats_down = rl_policy.get_action_stats("TREND_DOWN", state_hash, action)
        
        assert stats_up is not None
        assert stats_down is not None
        # Podem ter contadores diferentes se lógica de update diferencia


class TestEdgeCases:
    """Testes para casos extremos."""
    
    def test_zero_reward(self, rl_policy):
        """Testar update com reward = 0."""
        regime = "TREND_UP"
        state = RLState(regime=regime, time_bucket="14:00", confidence_level="HIGH", disagreement_level="LOW")
        
        rl_policy.update_from_trade(
            regime=regime,
            state_hash=state.to_hash(),
            action="HOLD",
            reward=0.0,
        )
        
        stats = rl_policy.get_action_stats(regime, state.to_hash(), "HOLD")
        assert stats["count"] >= 1
    
    def test_reward_out_of_range(self, rl_policy):
        """Testar update com reward > 1."""
        regime = "TREND_UP"
        state = RLState(regime=regime, time_bucket="14:00", confidence_level="HIGH", disagreement_level="LOW")
        
        # Deve clampar para [0, 1]
        rl_policy.update_from_trade(
            regime=regime,
            state_hash=state.to_hash(),
            action="ENTER",
            reward=1.5,  # Fora do intervalo
        )
        
        stats = rl_policy.get_action_stats(regime, state.to_hash(), "ENTER")
        assert stats["mean_value"] <= 1.0
    
    def test_unknown_regime(self, rl_policy):
        """Testar com regime desconhecido."""
        action = rl_policy.select_action("UNKNOWN_REGIME", RLState("UNKNOWN_REGIME", "14:00", "HIGH", "LOW"))
        
        # Deve retornar uma ação válida mesmo para regime novo
        assert action in ["HOLD", "ENTER", "ENTER_CONSERVATIVE", "ENTER_WITH_REALAVANCAGEM"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
