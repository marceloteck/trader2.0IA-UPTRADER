"""
Tests for Level 5: Scalp Manager

Testes para abertura de scalps, fechamento por TP/SL/timeout e rastreamento de eventos.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.execution.scalp_manager import ScalpManager, ScalpSetup, ScalpEvent


@pytest.fixture
def scalp_manager():
    """Cria instância de ScalpManager."""
    return ScalpManager(
        scalp_tp_points=80,
        scalp_sl_points=40,
        scalp_max_hold_seconds=180,
        contract_point_value=1.0,
        protect_profit_after_scalp=True,
        protect_profit_cooldown_seconds=300,
    )


class TestScalpSetupBasics:
    """Testes básicos de ScalpSetup."""
    
    def test_scalp_setup_creation(self):
        """Testar criação de ScalpSetup."""
        now = datetime.now()
        setup = ScalpSetup(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            scalp_tp_points=80,
            scalp_sl_points=40,
            max_hold_seconds=180,
            extra_contracts=1,
            opened_at=now,
        )
        
        assert setup.symbol == "EURUSD"
        assert setup.side == "BUY"
        assert setup.entry_price == 1.0850
    
    def test_scalp_setup_calc_tp_price_buy(self):
        """Testar cálculo de TP para compra."""
        setup = ScalpSetup(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            scalp_tp_points=80,
            scalp_sl_points=40,
            max_hold_seconds=180,
            extra_contracts=1,
            opened_at=datetime.now(),
        )
        
        tp_price = setup.calc_tp_price()
        # TP = 1.0850 + 80 pontos (0.0080)
        assert tp_price == pytest.approx(1.0930, rel=1e-4)
    
    def test_scalp_setup_calc_tp_price_sell(self):
        """Testar cálculo de TP para venda."""
        setup = ScalpSetup(
            symbol="EURUSD",
            side="SELL",
            entry_price=1.0850,
            scalp_tp_points=80,
            scalp_sl_points=40,
            max_hold_seconds=180,
            extra_contracts=1,
            opened_at=datetime.now(),
        )
        
        tp_price = setup.calc_tp_price()
        # TP = 1.0850 - 80 pontos (0.0080)
        assert tp_price == pytest.approx(1.0770, rel=1e-4)
    
    def test_scalp_setup_calc_sl_price_buy(self):
        """Testar cálculo de SL para compra."""
        setup = ScalpSetup(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            scalp_tp_points=80,
            scalp_sl_points=40,
            max_hold_seconds=180,
            extra_contracts=1,
            opened_at=datetime.now(),
        )
        
        sl_price = setup.calc_sl_price()
        # SL = 1.0850 - 40 pontos (0.0040)
        assert sl_price == pytest.approx(1.0810, rel=1e-4)
    
    def test_scalp_setup_calc_sl_price_sell(self):
        """Testar cálculo de SL para venda."""
        setup = ScalpSetup(
            symbol="EURUSD",
            side="SELL",
            entry_price=1.0850,
            scalp_tp_points=80,
            scalp_sl_points=40,
            max_hold_seconds=180,
            extra_contracts=1,
            opened_at=datetime.now(),
        )
        
        sl_price = setup.calc_sl_price()
        # SL = 1.0850 + 40 pontos (0.0040)
        assert sl_price == pytest.approx(1.0890, rel=1e-4)


class TestScalpEventBasics:
    """Testes básicos de ScalpEvent."""
    
    def test_scalp_event_creation(self):
        """Testar criação de ScalpEvent."""
        now = datetime.now()
        event = ScalpEvent(
            time=now,
            symbol="EURUSD",
            event_type="OPENED",
            setup=ScalpSetup(
                symbol="EURUSD",
                side="BUY",
                entry_price=1.0850,
                scalp_tp_points=80,
                scalp_sl_points=40,
                max_hold_seconds=180,
                extra_contracts=1,
                opened_at=now,
            ),
            current_price=1.0850,
            pnl=0.0,
            hold_time_seconds=0,
            reason="Scalp opened",
        )
        
        assert event.event_type == "OPENED"
        assert event.symbol == "EURUSD"


class TestScalpManagerOpenClose:
    """Testes para abertura e fechamento de scalps."""
    
    def test_open_scalp_buy(self, scalp_manager):
        """Testar abertura de scalp para compra."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        active = scalp_manager.get_active_scalp("EURUSD")
        assert active is not None
        assert active.side == "BUY"
        assert active.entry_price == 1.0850
    
    def test_open_scalp_sell(self, scalp_manager):
        """Testar abertura de scalp para venda."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="SELL",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        active = scalp_manager.get_active_scalp("EURUSD")
        assert active is not None
        assert active.side == "SELL"
    
    def test_multiple_scalps_different_symbols(self, scalp_manager):
        """Testar múltiplos scalps em diferentes símbolos."""
        now = datetime.now()
        
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        scalp_manager.open_scalp(
            symbol="GBPUSD",
            side="SELL",
            entry_price=1.2700,
            extra_contracts=1,
            opened_at=now,
        )
        
        eur_scalp = scalp_manager.get_active_scalp("EURUSD")
        gbp_scalp = scalp_manager.get_active_scalp("GBPUSD")
        
        assert eur_scalp is not None
        assert gbp_scalp is not None
        assert eur_scalp.symbol != gbp_scalp.symbol


class TestScalpTargetHit:
    """Testes para fechamento no TP."""
    
    def test_tp_hit_buy(self, scalp_manager):
        """Testar hit de TP em compra."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Preço sobe para TP
        # TP = 1.0850 + 0.0080 = 1.0930
        closed = scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0930,
            current_time=now + timedelta(seconds=60),
        )
        
        assert closed is True
        active = scalp_manager.get_active_scalp("EURUSD")
        assert active is None
    
    def test_tp_hit_sell(self, scalp_manager):
        """Testar hit de TP em venda."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="SELL",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Preço desce para TP
        # TP = 1.0850 - 0.0080 = 1.0770
        closed = scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0770,
            current_time=now + timedelta(seconds=60),
        )
        
        assert closed is True
    
    def test_partial_move_not_tp(self, scalp_manager):
        """Testar que movimento parcial não fecha."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Preço sobe pouco (não chega no TP)
        closed = scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0880,  # Só 30 pontos
            current_time=now + timedelta(seconds=60),
        )
        
        assert closed is False
        active = scalp_manager.get_active_scalp("EURUSD")
        assert active is not None


class TestScalpStopLoss:
    """Testes para fechamento no SL."""
    
    def test_sl_hit_buy(self, scalp_manager):
        """Testar hit de SL em compra."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Preço desce para SL
        # SL = 1.0850 - 0.0040 = 1.0810
        closed = scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0810,
            current_time=now + timedelta(seconds=60),
        )
        
        assert closed is True
    
    def test_sl_hit_sell(self, scalp_manager):
        """Testar hit de SL em venda."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="SELL",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Preço sobe para SL
        # SL = 1.0850 + 0.0040 = 1.0890
        closed = scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0890,
            current_time=now + timedelta(seconds=60),
        )
        
        assert closed is True


class TestScalpTimeout:
    """Testes para fechamento por timeout."""
    
    def test_timeout_close(self, scalp_manager):
        """Testar fechamento por timeout."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Passar máximo de tempo (180 segundos)
        closed = scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0860,
            current_time=now + timedelta(seconds=181),
        )
        
        assert closed is True
    
    def test_before_timeout(self, scalp_manager):
        """Testar que não fecha antes do timeout."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Antes do timeout
        closed = scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0860,
            current_time=now + timedelta(seconds=60),
        )
        
        assert closed is False
        active = scalp_manager.get_active_scalp("EURUSD")
        assert active is not None


class TestScalpPnLCalculation:
    """Testes para cálculo de PnL."""
    
    def test_pnl_buy_positive(self, scalp_manager):
        """Testar PnL positivo em compra."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Vender no TP (preço sobe)
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0930,  # +80 pontos
            current_time=now + timedelta(seconds=60),
        )
        
        events = scalp_manager.get_events(symbol="EURUSD")
        tp_event = next((e for e in events if e.event_type == "TP_HIT"), None)
        
        assert tp_event is not None
        assert tp_event.pnl > 0
    
    def test_pnl_buy_negative(self, scalp_manager):
        """Testar PnL negativo em compra."""
        now = datetime.now()
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        # Hit SL (preço desce)
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0810,  # -40 pontos
            current_time=now + timedelta(seconds=60),
        )
        
        events = scalp_manager.get_events(symbol="EURUSD")
        sl_event = next((e for e in events if e.event_type == "SL_HIT"), None)
        
        assert sl_event is not None
        assert sl_event.pnl < 0


class TestScalpCooldown:
    """Testes para cooldown após lucro."""
    
    def test_cooldown_after_win(self, scalp_manager):
        """Testar ativação de cooldown após vitória."""
        now = datetime.now()
        
        # Abrir e fechar com lucro
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0930,  # TP hit
            current_time=now + timedelta(seconds=60),
        )
        
        # Verificar cooldown
        in_cooldown = scalp_manager.is_in_cooldown("EURUSD")
        assert in_cooldown is True
    
    def test_cooldown_expiration(self, scalp_manager):
        """Testar expiração do cooldown."""
        now = datetime.now()
        
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0930,
            current_time=now + timedelta(seconds=60),
        )
        
        # Cooldown termina após 300 segundos
        remaining = scalp_manager.get_cooldown_remaining_seconds("EURUSD", now + timedelta(seconds=400))
        assert remaining <= 0
    
    def test_no_cooldown_after_loss(self, scalp_manager):
        """Testar que não há cooldown após prejuízo."""
        now = datetime.now()
        
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0810,  # SL hit
            current_time=now + timedelta(seconds=60),
        )
        
        in_cooldown = scalp_manager.is_in_cooldown("EURUSD")
        assert in_cooldown is False


class TestScalpEventTracking:
    """Testes para rastreamento de eventos."""
    
    def test_get_events_all(self, scalp_manager):
        """Testar obtenção de todos os eventos."""
        now = datetime.now()
        
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0930,
            current_time=now + timedelta(seconds=60),
        )
        
        events = scalp_manager.get_events(symbol="EURUSD")
        assert len(events) == 2  # OPENED + TP_HIT
    
    def test_get_events_filtered(self, scalp_manager):
        """Testar filtro de eventos por tipo."""
        now = datetime.now()
        
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0930,
            current_time=now + timedelta(seconds=60),
        )
        
        events = scalp_manager.get_events(symbol="EURUSD", event_type="TP_HIT")
        assert len(events) >= 1


class TestScalpStatistics:
    """Testes para estatísticas de scalp."""
    
    def test_export_stats_basic(self, scalp_manager):
        """Testar exportação de estatísticas básicas."""
        now = datetime.now()
        
        # Scalp vencedor
        scalp_manager.open_scalp(
            symbol="EURUSD",
            side="BUY",
            entry_price=1.0850,
            extra_contracts=1,
            opened_at=now,
        )
        
        scalp_manager.update_scalp(
            symbol="EURUSD",
            current_price=1.0930,
            current_time=now + timedelta(seconds=60),
        )
        
        stats = scalp_manager.export_stats()
        
        assert "total_scalps" in stats
        assert "wins" in stats
        assert "losses" in stats
        assert "winrate" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
