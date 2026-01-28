"""
Level 5: Scalp Manager

Gerencia saída rápida (scalp) para contratos extras de realavancagem.

Funcionalidades:
- Criar trade com TP/SL específicos para scalp
- Fechar apenas os contratos extra automaticamente
- Manter posição base para TP1/TP2/Runner normais
- Aplicar cooldown pós-lucro
- Registrar eventos de scalp
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger("trading_brains.execution.scalp_manager")


@dataclass
class ScalpSetup:
    """Setup de scalp para contratos extra."""
    symbol: str
    side: str
    entry_price: float
    scalp_tp_points: int
    scalp_sl_points: int
    max_hold_seconds: int
    extra_contracts: int
    
    def calc_tp_price(self) -> float:
        """Calcule TP em preço."""
        point_value = 0.00001
        tp_offset = self.scalp_tp_points * point_value
        
        if self.side == "BUY":
            return self.entry_price + tp_offset
        else:
            return self.entry_price - tp_offset
    
    def calc_sl_price(self) -> float:
        """Calcule SL em preço."""
        point_value = 0.00001
        sl_offset = self.scalp_sl_points * point_value
        
        if self.side == "BUY":
            return self.entry_price - sl_offset
        else:
            return self.entry_price + sl_offset


@dataclass
class ScalpEvent:
    """Evento de scalp (entrada, fechamento, etc.)."""
    time: datetime
    symbol: str
    event_type: str  # OPENED, TP_HIT, SL_HIT, TIMEOUT
    setup: Optional[ScalpSetup]
    current_price: Optional[float] = None
    pnl: Optional[float] = None
    hold_time_seconds: Optional[int] = None
    reason: str = ""


class ScalpManager:
    """
    Gerencia scalps para contratos extra de realavancagem.
    
    Implementa:
    - TP/SL específicos para extras (curtos)
    - Holding time máximo
    - Fechamento automático ao atingir alvo
    - Cooldown pós-lucro
    - Rastreamento de eventos
    """
    
    def __init__(
        self,
        scalp_tp_points: int,
        scalp_sl_points: int,
        scalp_max_hold_seconds: int,
        protect_profit_after_scalp: bool,
        protect_profit_cooldown_seconds: int,
        contract_point_value: float = 1.0,
    ):
        """
        Inicialize o gerenciador de scalp.
        
        Args:
            scalp_tp_points: TP em pontos para scalp
            scalp_sl_points: SL em pontos para scalp
            scalp_max_hold_seconds: Tempo máximo em trade (segundos)
            protect_profit_after_scalp: Aplicar proteção após lucro
            protect_profit_cooldown_seconds: Duração do cooldown
            contract_point_value: Valor do ponto por contrato
        """
        self.scalp_tp_points = scalp_tp_points
        self.scalp_sl_points = scalp_sl_points
        self.scalp_max_hold_seconds = scalp_max_hold_seconds
        self.protect_profit_after_scalp = protect_profit_after_scalp
        self.protect_profit_cooldown_seconds = protect_profit_cooldown_seconds
        self.contract_point_value = contract_point_value
        
        self.active_scalps: Dict[str, ScalpSetup] = {}
        self.scalp_opened_at: Dict[str, datetime] = {}
        self.events: list[ScalpEvent] = []
        self.cooldown_until: Optional[datetime] = None
    
    def open_scalp(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        extra_contracts: int,
    ) -> ScalpSetup:
        """
        Abra um trade de scalp para os contratos extra.
        
        Args:
            symbol: Símbolo
            side: BUY ou SELL
            entry_price: Preço de entrada
            extra_contracts: Número de contratos extra
        
        Returns:
            ScalpSetup criado
        """
        setup = ScalpSetup(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            scalp_tp_points=self.scalp_tp_points,
            scalp_sl_points=self.scalp_sl_points,
            max_hold_seconds=self.scalp_max_hold_seconds,
            extra_contracts=extra_contracts,
        )
        
        self.active_scalps[symbol] = setup
        self.scalp_opened_at[symbol] = datetime.utcnow()
        
        event = ScalpEvent(
            time=datetime.utcnow(),
            symbol=symbol,
            event_type="OPENED",
            setup=setup,
            reason=f"Scalp aberto: {extra_contracts} contratos extra, TP={setup.calc_tp_price():.5f}, SL={setup.calc_sl_price():.5f}",
        )
        self.events.append(event)
        
        logger.info(
            f"Scalp OPENED {symbol}: side={side}, entry={entry_price:.5f}, "
            f"extras={extra_contracts}, tp={setup.calc_tp_price():.5f}, sl={setup.calc_sl_price():.5f}"
        )
        
        return setup
    
    def update_scalp(
        self,
        symbol: str,
        current_price: float,
    ) -> Optional[ScalpEvent]:
        """
        Atualize um scalp ativo e verifique se deve fechar.
        
        Args:
            symbol: Símbolo
            current_price: Preço atual
        
        Returns:
            ScalpEvent se algo ocorreu, None caso contrário
        """
        if symbol not in self.active_scalps:
            return None
        
        setup = self.active_scalps[symbol]
        opened_at = self.scalp_opened_at[symbol]
        now = datetime.utcnow()
        hold_time = (now - opened_at).total_seconds()
        
        # Verifique TP
        tp_price = setup.calc_tp_price()
        if setup.side == "BUY" and current_price >= tp_price:
            event = self._close_scalp(symbol, "TP_HIT", current_price, hold_time)
            if self.protect_profit_after_scalp:
                self.cooldown_until = now + timedelta(seconds=self.protect_profit_cooldown_seconds)
            return event
        elif setup.side == "SELL" and current_price <= tp_price:
            event = self._close_scalp(symbol, "TP_HIT", current_price, hold_time)
            if self.protect_profit_after_scalp:
                self.cooldown_until = now + timedelta(seconds=self.protect_profit_cooldown_seconds)
            return event
        
        # Verifique SL
        sl_price = setup.calc_sl_price()
        if setup.side == "BUY" and current_price <= sl_price:
            event = self._close_scalp(symbol, "SL_HIT", current_price, hold_time)
            return event
        elif setup.side == "SELL" and current_price >= sl_price:
            event = self._close_scalp(symbol, "SL_HIT", current_price, hold_time)
            return event
        
        # Verifique timeout
        if hold_time > self.scalp_max_hold_seconds:
            event = self._close_scalp(symbol, "TIMEOUT", current_price, hold_time)
            return event
        
        return None
    
    def _close_scalp(
        self,
        symbol: str,
        event_type: str,
        exit_price: float,
        hold_time_seconds: float,
    ) -> ScalpEvent:
        """Feche um scalp internamente."""
        setup = self.active_scalps[symbol]
        
        # Calcule PnL
        point_diff = (exit_price - setup.entry_price) / 0.00001
        if setup.side == "SELL":
            point_diff = -point_diff
        
        pnl = point_diff * self.contract_point_value * setup.extra_contracts
        
        event = ScalpEvent(
            time=datetime.utcnow(),
            symbol=symbol,
            event_type=event_type,
            setup=setup,
            current_price=exit_price,
            pnl=pnl,
            hold_time_seconds=int(hold_time_seconds),
            reason=f"Scalp fechado por {event_type}: PnL={pnl:.0f}, hold={hold_time_seconds:.0f}s",
        )
        
        self.events.append(event)
        
        del self.active_scalps[symbol]
        del self.scalp_opened_at[symbol]
        
        logger.info(
            f"Scalp CLOSED {symbol}: {event_type}, exit={exit_price:.5f}, "
            f"pnl={pnl:.0f}, hold={hold_time_seconds:.0f}s"
        )
        
        return event
    
    def get_active_scalp(self, symbol: str) -> Optional[ScalpSetup]:
        """Obtenha scalp ativo para símbolo."""
        return self.active_scalps.get(symbol)
    
    def is_in_cooldown(self) -> bool:
        """Verifique se está em cooldown pós-lucro."""
        if self.cooldown_until is None:
            return False
        
        if datetime.utcnow() > self.cooldown_until:
            self.cooldown_until = None
            return False
        
        return True
    
    def get_cooldown_remaining_seconds(self) -> int:
        """Obtenha segundos restantes de cooldown."""
        if self.cooldown_until is None:
            return 0
        
        remaining = (self.cooldown_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    def get_events(self, symbol: Optional[str] = None, limit: int = 100) -> list[ScalpEvent]:
        """Obtenha eventos de scalp."""
        events = self.events[-limit:] if not symbol else [e for e in self.events if e.symbol == symbol][-limit:]
        return events
    
    def export_stats(self, symbol: Optional[str] = None) -> Dict:
        """Exporte estatísticas de scalp."""
        if symbol:
            events = [e for e in self.events if e.symbol == symbol]
        else:
            events = self.events
        
        if not events:
            return {
                "total_scalps": 0,
                "closed_scalps": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0,
                "winrate": 0,
                "avg_hold_time": 0,
            }
        
        closed = [e for e in events if e.event_type in ["TP_HIT", "SL_HIT", "TIMEOUT"]]
        wins = [e for e in closed if e.pnl and e.pnl > 0]
        losses = [e for e in closed if e.pnl and e.pnl <= 0]
        
        return {
            "total_scalps": len(events),
            "closed_scalps": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "total_pnl": sum(e.pnl or 0 for e in closed),
            "winrate": len(wins) / len(closed) if closed else 0,
            "avg_hold_time": sum(e.hold_time_seconds or 0 for e in closed) / len(closed) if closed else 0,
        }
