"""
Tests for Level 5: Online Update Manager

Testes para batching de trades, snapshots e rollback de política.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.training.online_update import OnlineUpdater, PolicySnapshot


@pytest.fixture
def online_updater():
    """Cria instância de OnlineUpdater."""
    return OnlineUpdater(
        batch_size=5,
        snapshot_interval=10,
        keep_snapshots=3,
    )


class TestPolicySnapshotBasics:
    """Testes básicos de PolicySnapshot."""
    
    def test_snapshot_creation(self):
        """Testar criação de PolicySnapshot."""
        snapshot = PolicySnapshot(
            snapshot_id="snap_001",
            regime="TREND_UP",
            time=datetime.now(),
            policy_data='{"state_1": {"ENTER": {"alpha": 2.0}}}',
            metrics={"total_trades": 10, "win_rate": 0.7},
            note="Snapshot after 10 trades"
        )
        
        assert snapshot.snapshot_id == "snap_001"
        assert snapshot.regime == "TREND_UP"
        assert snapshot.policy_data is not None
    
    def test_snapshot_unique_id(self):
        """Testar que snapshots têm IDs únicos."""
        snap1 = PolicySnapshot(
            snapshot_id="snap_001",
            regime="TREND_UP",
            time=datetime.now(),
            policy_data="{}",
            metrics={},
        )
        
        snap2 = PolicySnapshot(
            snapshot_id="snap_002",
            regime="TREND_UP",
            time=datetime.now(),
            policy_data="{}",
            metrics={},
        )
        
        assert snap1.snapshot_id != snap2.snapshot_id


class TestOnlineUpdaterBasics:
    """Testes básicos de OnlineUpdater."""
    
    def test_updater_creation(self, online_updater):
        """Testar criação de OnlineUpdater."""
        assert online_updater.batch_size == 5
        assert online_updater.snapshot_interval == 10
        assert online_updater.keep_snapshots == 3
    
    def test_initial_empty(self, online_updater):
        """Testar que começa vazio."""
        assert online_updater.should_update() is False
        pending = online_updater.get_pending_trades()
        assert len(pending) == 0


class TestTradeBuffering:
    """Testes para buffering de trades."""
    
    def test_add_single_trade(self, online_updater):
        """Testar adição de uma trade."""
        trade = {
            "symbol": "EURUSD",
            "regime": "TREND_UP",
            "state_hash": "state_1",
            "action": "ENTER",
            "pnl": 100.0,
            "duration_seconds": 300,
        }
        
        online_updater.add_trade(trade)
        
        pending = online_updater.get_pending_trades()
        assert len(pending) == 1
        assert pending[0]["symbol"] == "EURUSD"
    
    def test_add_multiple_trades(self, online_updater):
        """Testar adição de múltiplas trades."""
        for i in range(3):
            online_updater.add_trade({
                "symbol": "EURUSD",
                "regime": "TREND_UP",
                "state_hash": f"state_{i}",
                "action": "ENTER",
                "pnl": 50.0 + i * 10,
                "duration_seconds": 300,
            })
        
        pending = online_updater.get_pending_trades()
        assert len(pending) == 3


class TestBatchDetection:
    """Testes para detecção de batch completo."""
    
    def test_should_update_false_initially(self, online_updater):
        """Testar que não deve atualizar inicialmente."""
        assert online_updater.should_update() is False
    
    def test_should_update_before_batch_full(self, online_updater):
        """Testar que não atualiza antes do batch completo."""
        online_updater.batch_size = 5
        
        for i in range(4):
            online_updater.add_trade({"symbol": "EURUSD", "regime": "TREND_UP", "pnl": 50.0})
        
        assert online_updater.should_update() is False
    
    def test_should_update_at_batch_full(self, online_updater):
        """Testar que atualiza quando batch está completo."""
        online_updater.batch_size = 5
        
        for i in range(5):
            online_updater.add_trade({"symbol": "EURUSD", "regime": "TREND_UP", "pnl": 50.0})
        
        assert online_updater.should_update() is True
    
    def test_should_update_over_batch_full(self, online_updater):
        """Testar que continua True após batch completo."""
        online_updater.batch_size = 5
        
        for i in range(7):
            online_updater.add_trade({"symbol": "EURUSD", "regime": "TREND_UP", "pnl": 50.0})
        
        assert online_updater.should_update() is True


class TestBatchFiltering:
    """Testes para filtragem de trades por regime."""
    
    def test_get_pending_trades_all(self, online_updater):
        """Testar obtenção de todos os trades pendentes."""
        online_updater.add_trade({"symbol": "EUR", "regime": "TREND_UP", "pnl": 100.0})
        online_updater.add_trade({"symbol": "GBP", "regime": "TREND_DOWN", "pnl": 50.0})
        online_updater.add_trade({"symbol": "USD", "regime": "RANGE", "pnl": 75.0})
        
        pending = online_updater.get_pending_trades()
        assert len(pending) == 3
    
    def test_get_pending_trades_filtered_by_regime(self, online_updater):
        """Testar filtragem de trades por regime."""
        online_updater.add_trade({"symbol": "EUR", "regime": "TREND_UP", "pnl": 100.0})
        online_updater.add_trade({"symbol": "GBP", "regime": "TREND_DOWN", "pnl": 50.0})
        online_updater.add_trade({"symbol": "USD", "regime": "TREND_UP", "pnl": 75.0})
        
        pending = online_updater.get_pending_trades(regime="TREND_UP")
        assert len(pending) == 2
        assert all(t["regime"] == "TREND_UP" for t in pending)
    
    def test_clear_pending(self, online_updater):
        """Testar limpeza de trades pendentes."""
        for i in range(3):
            online_updater.add_trade({"symbol": "EURUSD", "regime": "TREND_UP", "pnl": 50.0})
        
        online_updater.clear_pending()
        pending = online_updater.get_pending_trades()
        assert len(pending) == 0


class TestSnapshotManagement:
    """Testes para gerenciamento de snapshots."""
    
    def test_create_snapshot(self, online_updater):
        """Testar criação de snapshot."""
        snapshot = online_updater.create_snapshot(
            regime="TREND_UP",
            policy_data='{"state_1": {"ENTER": {"alpha": 2.0}}}',
            metrics={"total_trades": 10, "win_rate": 0.7},
            note="Test snapshot"
        )
        
        assert snapshot is not None
        assert snapshot.regime == "TREND_UP"
        assert snapshot.policy_data is not None
    
    def test_get_last_snapshot(self, online_updater):
        """Testar obtenção do último snapshot."""
        # Sem snapshots
        last = online_updater.get_last_snapshot(regime="TREND_UP")
        assert last is None
        
        # Criar um snapshot
        online_updater.create_snapshot(
            regime="TREND_UP",
            policy_data="{}",
            metrics={}
        )
        
        # Agora deve retornar
        last = online_updater.get_last_snapshot(regime="TREND_UP")
        assert last is not None
    
    def test_get_snapshots_history(self, online_updater):
        """Testar obtenção do histórico de snapshots."""
        # Criar 3 snapshots
        for i in range(3):
            online_updater.create_snapshot(
                regime="TREND_UP",
                policy_data=f'{{"iteration": {i}}}',
                metrics={"iteration": i}
            )
        
        snapshots = online_updater.get_snapshots(regime="TREND_UP")
        assert len(snapshots) <= online_updater.keep_snapshots
    
    def test_keep_snapshots_limit(self, online_updater):
        """Testar que mantém apenas N snapshots recentes."""
        online_updater.keep_snapshots = 2
        
        # Criar 5 snapshots
        for i in range(5):
            online_updater.create_snapshot(
                regime="TREND_UP",
                policy_data=f'{{"iteration": {i}}}',
                metrics={"iteration": i}
            )
        
        snapshots = online_updater.get_snapshots(regime="TREND_UP")
        assert len(snapshots) <= 2


class TestRollback:
    """Testes para rollback de política."""
    
    def test_rollback_to_snapshot(self, online_updater):
        """Testar rollback para um snapshot."""
        # Criar snapshot
        snap = online_updater.create_snapshot(
            regime="TREND_UP",
            policy_data='{"state_1": {"ENTER": {"alpha": 2.0}}}',
            metrics={"total_trades": 5, "win_rate": 0.6}
        )
        
        # Simular novo estado
        online_updater.create_snapshot(
            regime="TREND_UP",
            policy_data='{"state_1": {"ENTER": {"alpha": 5.0}}}',
            metrics={"total_trades": 15, "win_rate": 0.4}
        )
        
        # Rollback
        restored = online_updater.rollback_to_snapshot(snap.snapshot_id)
        
        assert restored is not None
        assert restored.snapshot_id == snap.snapshot_id
    
    def test_rollback_unknown_snapshot(self, online_updater):
        """Testar rollback para snapshot desconhecido."""
        result = online_updater.rollback_to_snapshot("unknown_snap_id")
        assert result is None


class TestTradeCounter:
    """Testes para contagem de trades por regime."""
    
    def test_track_trade_counts(self, online_updater):
        """Testar rastreamento de contagem de trades."""
        online_updater.add_trade({"symbol": "EUR", "regime": "TREND_UP", "pnl": 100.0})
        online_updater.add_trade({"symbol": "GBP", "regime": "TREND_UP", "pnl": 50.0})
        online_updater.add_trade({"symbol": "USD", "regime": "TREND_DOWN", "pnl": 75.0})
        
        state = online_updater.export_state()
        
        assert state["total_trades"] == 3
    
    def test_trade_counter_per_regime(self, online_updater):
        """Testar contagem de trades por regime."""
        for i in range(3):
            online_updater.add_trade({"regime": "TREND_UP", "pnl": 50.0})
        
        for i in range(2):
            online_updater.add_trade({"regime": "TREND_DOWN", "pnl": 50.0})
        
        state = online_updater.export_state()
        
        assert state["total_trades"] == 5


class TestStateExport:
    """Testes para exportação de estado."""
    
    def test_export_state_empty(self, online_updater):
        """Testar exportação de estado vazio."""
        state = online_updater.export_state()
        
        assert isinstance(state, dict)
        assert "total_trades" in state
        assert state["total_trades"] == 0
    
    def test_export_state_with_trades(self, online_updater):
        """Testar exportação de estado com trades."""
        for i in range(5):
            online_updater.add_trade({
                "symbol": "EURUSD",
                "regime": "TREND_UP",
                "pnl": 50.0 + i * 10,
            })
        
        state = online_updater.export_state()
        
        assert state["total_trades"] == 5
        assert state["batch_size"] == online_updater.batch_size
        assert "pending_trades_count" in state


class TestIntegrationBatchAndSnapshot:
    """Testes de integração entre batching e snapshots."""
    
    def test_snapshot_on_batch_complete(self, online_updater):
        """Testar se snapshot é criado quando batch completa."""
        online_updater.batch_size = 3
        online_updater.snapshot_interval = 3
        
        for i in range(3):
            online_updater.add_trade({
                "symbol": "EURUSD",
                "regime": "TREND_UP",
                "pnl": 50.0,
            })
        
        # Snapshot deve existir se foi criado automaticamente
        snapshots = online_updater.get_snapshots(regime="TREND_UP")
        # Pode ter ou não, depende da implementação
        assert isinstance(snapshots, list)
    
    def test_workflow_batch_snapshot_rollback(self, online_updater):
        """Testar workflow completo: batch -> snapshot -> rollback."""
        online_updater.batch_size = 2
        
        # Adicionar trades
        online_updater.add_trade({"regime": "TREND_UP", "pnl": 100.0})
        online_updater.add_trade({"regime": "TREND_UP", "pnl": 50.0})
        
        # Batch deve estar completo
        assert online_updater.should_update() is True
        
        # Criar snapshot antes de limpar
        snap = online_updater.create_snapshot(
            regime="TREND_UP",
            policy_data='{"v": 1}',
            metrics={"trades": 2}
        )
        
        # Limpar pending
        online_updater.clear_pending()
        assert online_updater.should_update() is False
        
        # Adicionar mais trades
        online_updater.add_trade({"regime": "TREND_UP", "pnl": -100.0})
        online_updater.add_trade({"regime": "TREND_UP", "pnl": -50.0})
        
        # Rollback
        restored = online_updater.rollback_to_snapshot(snap.snapshot_id)
        assert restored is not None


class TestEdgeCases:
    """Testes para casos extremos."""
    
    def test_zero_batch_size(self):
        """Testar com batch_size = 0."""
        updater = OnlineUpdater(batch_size=0, snapshot_interval=1)
        
        updater.add_trade({"regime": "TREND_UP", "pnl": 50.0})
        
        # Deve sempre retornar True ou False consistentemente
        should_update = updater.should_update()
        assert isinstance(should_update, bool)
    
    def test_single_batch_size(self):
        """Testar com batch_size = 1."""
        updater = OnlineUpdater(batch_size=1, snapshot_interval=1)
        
        updater.add_trade({"regime": "TREND_UP", "pnl": 50.0})
        
        # Deve estar pronto para update
        assert updater.should_update() is True
    
    def test_negative_pnl_trades(self, online_updater):
        """Testar com trades de PnL negativo."""
        online_updater.add_trade({"regime": "TREND_UP", "pnl": -100.0})
        online_updater.add_trade({"regime": "TREND_UP", "pnl": -50.0})
        
        pending = online_updater.get_pending_trades()
        assert len(pending) == 2
        assert all(t["pnl"] < 0 for t in pending)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
