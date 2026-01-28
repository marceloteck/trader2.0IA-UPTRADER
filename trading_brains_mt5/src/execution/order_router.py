"""
Order Router V4 - Unified interface for placing orders in SIM and MT5.

Abstracts:
- RouterSim: Paper trading (for backtest and live-sim)
- RouterMT5: Live trading (with real MT5 terminal)

Both implement same interface for seamless switching.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order lifecycle states."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"


@dataclass
class PlaceOrderRequest:
    """Request to place an order."""
    symbol: str
    side: str  # "BUY" or "SELL"
    volume: float
    entry_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: str = ""
    magic: int = 0
    order_type: str = "MARKET"  # MARKET or LIMIT
    expires_in_seconds: int = 0
    
    def validate(self) -> tuple[bool, str]:
        """Validate order request."""
        if self.volume <= 0:
            return False, "Volume must be positive"
        if self.entry_price <= 0:
            return False, "Entry price must be positive"
        if self.side.upper() not in ["BUY", "SELL"]:
            return False, "Side must be BUY or SELL"
        if self.sl is not None and self.tp is not None:
            if self.side.upper() == "BUY":
                if self.sl >= self.entry_price or self.tp <= self.entry_price:
                    return False, "For BUY: SL < entry < TP"
            else:  # SELL
                if self.sl <= self.entry_price or self.tp >= self.entry_price:
                    return False, "For SELL: TP < entry < SL"
        return True, ""


@dataclass
class OrderEvent:
    """Order execution event."""
    timestamp: datetime
    ticket: int
    symbol: str
    side: str
    volume: float
    entry_price: float
    filled_price: float
    filled_volume: float
    status: OrderStatus
    sl: Optional[float] = None
    tp: Optional[float] = None
    reason: str = ""
    retcode: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'ticket': self.ticket,
            'symbol': self.symbol,
            'side': self.side,
            'volume': self.volume,
            'entry_price': self.entry_price,
            'filled_price': self.filled_price,
            'filled_volume': self.filled_volume,
            'status': self.status.value,
            'sl': self.sl,
            'tp': self.tp,
            'reason': self.reason,
            'retcode': self.retcode,
        }


class OrderRouter:
    """
    Abstract base for order routing.
    Implementations: RouterSim (paper) and RouterMT5 (live).
    """
    
    def place_order(self, request: PlaceOrderRequest) -> OrderEvent:
        """Place an order. Returns OrderEvent with result."""
        raise NotImplementedError
    
    def modify_order(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        """Modify existing order SL/TP. Returns success."""
        raise NotImplementedError
    
    def close_position(self, ticket: int, volume: float) -> OrderEvent:
        """Close or reduce a position. Returns OrderEvent."""
        raise NotImplementedError
    
    def get_position(self, ticket: int) -> Optional[Dict]:
        """Get position details by ticket."""
        raise NotImplementedError
    
    def get_all_positions(self) -> List[Dict]:
        """Get all open positions."""
        raise NotImplementedError


class RouterSim(OrderRouter):
    """
    Simulation router for backtesting and live-sim.
    Uses in-memory position tracking and fill model.
    """
    
    def __init__(self, fill_model, position_tracker, db_repo=None):
        """
        Initialize simulation router.
        
        Args:
            fill_model: FillModel instance for realistic fills
            position_tracker: PositionTracker for state management
            db_repo: Optional DB repo for logging order events
        """
        self.fill_model = fill_model
        self.position_tracker = position_tracker
        self.db_repo = db_repo
        self.next_ticket = 10000
        self.order_history: Dict[int, OrderEvent] = {}
        
        logger.info("RouterSim initialized (paper trading mode)")
    
    def place_order(self, request: PlaceOrderRequest) -> OrderEvent:
        """
        Place an order in simulation mode.
        Uses fill model for realistic fills.
        """
        # Validate request
        is_valid, reason = request.validate()
        if not is_valid:
            event = OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=0,
                symbol=request.symbol,
                side=request.side,
                volume=request.volume,
                entry_price=request.entry_price,
                filled_price=0,
                filled_volume=0,
                status=OrderStatus.REJECTED,
                reason=reason
            )
            logger.warning(f"Order rejected: {reason}")
            return event
        
        # Get fill from fill model
        fill_result = self.fill_model.calculate_fill(
            requested_price=request.entry_price,
            side=request.side,
            is_live=False
        )
        
        # Create ticket
        ticket = self.next_ticket
        self.next_ticket += 1
        
        # Create order event
        if fill_result.success:
            status = OrderStatus.FILLED
            filled_price = fill_result.filled_price
            filled_volume = request.volume
            reason = ""
        else:
            status = OrderStatus.REJECTED
            filled_price = 0
            filled_volume = 0
            reason = fill_result.reason
        
        event = OrderEvent(
            timestamp=datetime.utcnow(),
            ticket=ticket,
            symbol=request.symbol,
            side=request.side,
            volume=request.volume,
            entry_price=request.entry_price,
            filled_price=filled_price,
            filled_volume=filled_volume,
            status=status,
            sl=request.sl,
            tp=request.tp,
            reason=reason
        )
        
        # Track position
        if status == OrderStatus.FILLED:
            self.position_tracker.add_position(
                ticket=ticket,
                side=request.side,
                volume=filled_volume,
                entry_price=filled_price,
                sl=request.sl,
                tp=request.tp,
                symbol=request.symbol,
                open_time=event.timestamp
            )
        
        # Log to DB if available
        if self.db_repo and hasattr(self.db_repo, 'insert_order_event'):
            self.db_repo.insert_order_event(event.to_dict())
        
        self.order_history[ticket] = event
        logger.info(f"Order {ticket} {request.side} {request.volume} {request.symbol} "
                   f"@ {filled_price:.5f} [{status.value}]")
        
        return event
    
    def modify_order(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        """Modify order SL/TP in simulation."""
        if ticket not in self.position_tracker.positions:
            logger.warning(f"Ticket {ticket} not found")
            return False
        
        position = self.position_tracker.positions[ticket]
        position['sl'] = sl
        position['tp'] = tp
        
        logger.info(f"Order {ticket} modified: SL={sl}, TP={tp}")
        return True
    
    def close_position(self, ticket: int, volume: float) -> OrderEvent:
        """Close position in simulation."""
        position = self.position_tracker.get_position(ticket)
        if not position:
            return OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=ticket,
                symbol="",
                side="",
                volume=volume,
                entry_price=0,
                filled_price=0,
                filled_volume=0,
                status=OrderStatus.REJECTED,
                reason="Position not found"
            )
        
        # Get close price from fill model
        close_side = "SELL" if position['side'] == "BUY" else "BUY"
        fill_result = self.fill_model.calculate_fill(
            requested_price=position['entry_price'],  # Approximate
            side=close_side,
            is_live=False
        )
        
        filled_price = fill_result.filled_price if fill_result.success else 0
        
        event = OrderEvent(
            timestamp=datetime.utcnow(),
            ticket=ticket,
            symbol=position['symbol'],
            side=f"CLOSE_{position['side']}",
            volume=volume,
            entry_price=position['entry_price'],
            filled_price=filled_price,
            filled_volume=volume if fill_result.success else 0,
            status=OrderStatus.FILLED if fill_result.success else OrderStatus.REJECTED,
            reason=fill_result.reason if not fill_result.success else ""
        )
        
        if fill_result.success:
            self.position_tracker.close_position(ticket, volume)
            logger.info(f"Position {ticket} closed @ {filled_price:.5f}")
        
        return event
    
    def get_position(self, ticket: int) -> Optional[Dict]:
        """Get position by ticket."""
        return self.position_tracker.get_position(ticket)
    
    def get_all_positions(self) -> List[Dict]:
        """Get all open positions."""
        return list(self.position_tracker.positions.values())


class RouterMT5(OrderRouter):
    """
    MT5 router for live trading.
    Interfaces with MetaTrader5 terminal.
    """
    
    def __init__(self, mt5_client, fill_model, position_tracker, db_repo=None):
        """
        Initialize MT5 router.
        
        Args:
            mt5_client: MT5Client instance for terminal communication
            fill_model: FillModel for slippage estimation
            position_tracker: PositionTracker for state management
            db_repo: Optional DB repo for logging
        """
        self.mt5_client = mt5_client
        self.fill_model = fill_model
        self.position_tracker = position_tracker
        self.db_repo = db_repo
        self.last_order_time = {}  # ticket -> timestamp for retry logic
        self.retry_backoff = {}  # ticket -> current backoff
        
        logger.info("RouterMT5 initialized (live MT5 mode)")
    
    def place_order(self, request: PlaceOrderRequest) -> OrderEvent:
        """
        Place order on MT5 terminal with retry logic.
        """
        # Validate request
        is_valid, reason = request.validate()
        if not is_valid:
            return OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=0,
                symbol=request.symbol,
                side=request.side,
                volume=request.volume,
                entry_price=request.entry_price,
                filled_price=0,
                filled_volume=0,
                status=OrderStatus.REJECTED,
                reason=reason
            )
        
        # Check MT5 connectivity
        if not self.mt5_client.is_connected():
            return OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=0,
                symbol=request.symbol,
                side=request.side,
                volume=request.volume,
                entry_price=request.entry_price,
                filled_price=0,
                filled_volume=0,
                status=OrderStatus.ERROR,
                reason="MT5 not connected"
            )
        
        # Send to MT5 (implementation delegated to mt5_client)
        try:
            result = self.mt5_client.place_order(
                symbol=request.symbol,
                side=request.side,
                volume=request.volume,
                entry_price=request.entry_price,
                sl=request.sl,
                tp=request.tp,
                comment=request.comment,
                magic=request.magic
            )
            
            # Parse MT5 result into OrderEvent
            ticket = result.get('ticket', 0)
            retcode = result.get('retcode', -1)
            
            if retcode == 0:  # TRADE_RETCODE_DONE
                status = OrderStatus.FILLED
                filled_price = result.get('filled_price', request.entry_price)
                filled_volume = request.volume
            else:
                status = OrderStatus.REJECTED
                filled_price = 0
                filled_volume = 0
            
            event = OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=ticket,
                symbol=request.symbol,
                side=request.side,
                volume=request.volume,
                entry_price=request.entry_price,
                filled_price=filled_price,
                filled_volume=filled_volume,
                status=status,
                sl=request.sl,
                tp=request.tp,
                retcode=retcode,
                reason=result.get('reason', '')
            )
            
            # Track position
            if status == OrderStatus.FILLED:
                self.position_tracker.add_position(
                    ticket=ticket,
                    side=request.side,
                    volume=filled_volume,
                    entry_price=filled_price,
                    sl=request.sl,
                    tp=request.tp,
                    symbol=request.symbol,
                    open_time=event.timestamp
                )
            
            # Log to DB
            if self.db_repo and hasattr(self.db_repo, 'insert_order_event'):
                self.db_repo.insert_order_event(event.to_dict())
            
            logger.info(f"MT5 Order {ticket}: {status.value} retcode={retcode}")
            
            return event
            
        except Exception as e:
            logger.error(f"MT5 order placement failed: {e}")
            return OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=0,
                symbol=request.symbol,
                side=request.side,
                volume=request.volume,
                entry_price=request.entry_price,
                filled_price=0,
                filled_volume=0,
                status=OrderStatus.ERROR,
                reason=str(e)
            )
    
    def modify_order(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        """Modify order on MT5."""
        try:
            result = self.mt5_client.modify_order(ticket, sl, tp)
            success = result.get('retcode', -1) == 0
            if success:
                self.position_tracker.positions[ticket]['sl'] = sl
                self.position_tracker.positions[ticket]['tp'] = tp
                logger.info(f"MT5 Order {ticket} modified")
            return success
        except Exception as e:
            logger.error(f"MT5 modify failed: {e}")
            return False
    
    def close_position(self, ticket: int, volume: float) -> OrderEvent:
        """Close position on MT5."""
        try:
            position = self.position_tracker.get_position(ticket)
            if not position:
                return OrderEvent(
                    timestamp=datetime.utcnow(),
                    ticket=ticket,
                    symbol="",
                    side="",
                    volume=volume,
                    entry_price=0,
                    filled_price=0,
                    filled_volume=0,
                    status=OrderStatus.REJECTED,
                    reason="Position not found"
                )
            
            result = self.mt5_client.close_position(ticket, volume)
            retcode = result.get('retcode', -1)
            
            event = OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=ticket,
                symbol=position['symbol'],
                side=f"CLOSE_{position['side']}",
                volume=volume,
                entry_price=position['entry_price'],
                filled_price=result.get('filled_price', 0),
                filled_volume=volume if retcode == 0 else 0,
                status=OrderStatus.FILLED if retcode == 0 else OrderStatus.REJECTED,
                retcode=retcode,
                reason=result.get('reason', '')
            )
            
            if retcode == 0:
                self.position_tracker.close_position(ticket, volume)
            
            return event
            
        except Exception as e:
            logger.error(f"MT5 close failed: {e}")
            return OrderEvent(
                timestamp=datetime.utcnow(),
                ticket=ticket,
                symbol="",
                side="",
                volume=volume,
                entry_price=0,
                filled_price=0,
                filled_volume=0,
                status=OrderStatus.ERROR,
                reason=str(e)
            )
    
    def get_position(self, ticket: int) -> Optional[Dict]:
        """Get position by ticket."""
        return self.position_tracker.get_position(ticket)
    
    def get_all_positions(self) -> List[Dict]:
        """Get all open positions."""
        return list(self.position_tracker.positions.values())
