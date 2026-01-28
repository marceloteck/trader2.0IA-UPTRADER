"""
Position Tracker V4 - Maintains state of open positions and reconciliation.

Provides:
- Position state tracking (OPEN, CLOSED, REJECTED)
- Reconciliation with MT5 (detect manual closes, divergences)
- P&L tracking per position
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """State of a single position."""
    ticket: int
    symbol: str
    side: str  # "BUY" or "SELL"
    volume: float
    entry_price: float
    open_time: datetime
    
    sl: Optional[float] = None
    tp: Optional[float] = None
    
    status: str = "OPEN"  # OPEN, CLOSED, REJECTED, ERROR
    close_price: Optional[float] = None
    close_time: Optional[datetime] = None
    
    # P&L tracking
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    
    # Metadata
    comment: str = ""
    magic: int = 0
    last_update: datetime = field(default_factory=datetime.utcnow)
    
    def get_pnl(self, current_price: float) -> tuple[float, float]:
        """Calculate current P&L and percentage."""
        if self.status in ["CLOSED", "REJECTED"]:
            if self.close_price:
                pnl = (self.close_price - self.entry_price) * self.volume
                if self.side == "SELL":
                    pnl = -pnl
                pnl_percent = (pnl / (self.entry_price * self.volume)) * 100
            else:
                pnl = 0
                pnl_percent = 0
        else:
            self.current_price = current_price
            if self.side == "BUY":
                pnl = (current_price - self.entry_price) * self.volume
            else:  # SELL
                pnl = (self.entry_price - current_price) * self.volume
            pnl_percent = (pnl / (self.entry_price * self.volume)) * 100
        
        self.pnl = pnl
        self.pnl_percent = pnl_percent
        return pnl, pnl_percent
    
    def is_open(self) -> bool:
        """Check if position is still open."""
        return self.status == "OPEN"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'ticket': self.ticket,
            'symbol': self.symbol,
            'side': self.side,
            'volume': self.volume,
            'entry_price': self.entry_price,
            'open_time': self.open_time.isoformat(),
            'sl': self.sl,
            'tp': self.tp,
            'status': self.status,
            'close_price': self.close_price,
            'close_time': self.close_time.isoformat() if self.close_time else None,
            'current_price': self.current_price,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'comment': self.comment,
            'magic': self.magic,
        }


class PositionTracker:
    """
    Tracks all open positions and provides reconciliation.
    """
    
    def __init__(self, db_repo=None):
        """
        Initialize position tracker.
        
        Args:
            db_repo: Optional DB repo for loading/saving position state
        """
        self.positions: Dict[int, PositionState] = {}
        self.db_repo = db_repo
        
        # Load existing positions from DB if available
        if db_repo and hasattr(db_repo, 'fetch_open_positions'):
            try:
                existing = db_repo.fetch_open_positions()
                for pos_data in existing:
                    pos = PositionState(
                        ticket=pos_data.get('ticket'),
                        symbol=pos_data.get('symbol'),
                        side=pos_data.get('side'),
                        volume=pos_data.get('volume'),
                        entry_price=pos_data.get('entry_price'),
                        open_time=pos_data.get('open_time'),
                        sl=pos_data.get('sl'),
                        tp=pos_data.get('tp'),
                        status=pos_data.get('status', 'OPEN'),
                        comment=pos_data.get('comment', ''),
                        magic=pos_data.get('magic', 0),
                    )
                    self.positions[pos.ticket] = pos
                logger.info(f"Loaded {len(existing)} existing positions from DB")
            except Exception as e:
                logger.warning(f"Could not load positions from DB: {e}")
    
    def add_position(
        self,
        ticket: int,
        symbol: str,
        side: str,
        volume: float,
        entry_price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        open_time: Optional[datetime] = None,
        comment: str = "",
        magic: int = 0
    ) -> PositionState:
        """Add a new position."""
        if open_time is None:
            open_time = datetime.utcnow()
        
        pos = PositionState(
            ticket=ticket,
            symbol=symbol,
            side=side,
            volume=volume,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            open_time=open_time,
            comment=comment,
            magic=magic,
            status="OPEN"
        )
        
        self.positions[ticket] = pos
        
        if self.db_repo and hasattr(self.db_repo, 'insert_position_state'):
            self.db_repo.insert_position_state(pos.to_dict())
        
        logger.info(f"Position {ticket} added: {side} {volume} {symbol} @ {entry_price:.5f}")
        
        return pos
    
    def get_position(self, ticket: int) -> Optional[PositionState]:
        """Get position by ticket."""
        return self.positions.get(ticket)
    
    def close_position(self, ticket: int, volume: float, close_price: Optional[float] = None) -> bool:
        """
        Close or reduce a position.
        
        Args:
            ticket: Position ticket
            volume: Volume to close (can be partial)
            close_price: Closing price (optional, used for P&L calc)
        
        Returns:
            True if successful
        """
        pos = self.positions.get(ticket)
        if not pos:
            logger.warning(f"Position {ticket} not found")
            return False
        
        if volume >= pos.volume:
            # Full close
            pos.status = "CLOSED"
            pos.volume = 0
            pos.close_time = datetime.utcnow()
            pos.close_price = close_price or pos.entry_price
            logger.info(f"Position {ticket} closed fully")
        else:
            # Partial close - reduce volume
            pos.volume -= volume
            logger.info(f"Position {ticket} reduced by {volume} (remaining: {pos.volume})")
        
        if self.db_repo and hasattr(self.db_repo, 'update_position_state'):
            self.db_repo.update_position_state(pos.to_dict())
        
        return True
    
    def update_position_price(self, ticket: int, current_price: float) -> Optional[tuple[float, float]]:
        """Update current price and return P&L."""
        pos = self.positions.get(ticket)
        if not pos:
            return None
        
        pnl, pnl_pct = pos.get_pnl(current_price)
        return pnl, pnl_pct
    
    def update_all_prices(self, price_map: Dict[str, float]) -> Dict[int, tuple[float, float]]:
        """
        Update all positions with current prices.
        
        Args:
            price_map: {symbol: current_price}
        
        Returns:
            {ticket: (pnl, pnl_percent)}
        """
        results = {}
        for ticket, pos in self.positions.items():
            if pos.status == "OPEN" and pos.symbol in price_map:
                price = price_map[pos.symbol]
                pnl, pnl_pct = pos.get_pnl(price)
                results[ticket] = (pnl, pnl_pct)
        
        return results
    
    def get_open_positions(self) -> List[PositionState]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open()]
    
    def get_all_positions(self) -> List[PositionState]:
        """Get all positions (open and closed)."""
        return list(self.positions.values())
    
    def get_total_pnl(self, current_prices: Dict[str, float]) -> tuple[float, List[float]]:
        """
        Get total P&L across all open positions.
        
        Returns:
            (total_pnl, [pnl_per_position])
        """
        pnls = []
        for pos in self.get_open_positions():
            if pos.symbol in current_prices:
                price = current_prices[pos.symbol]
                pnl, _ = pos.get_pnl(price)
                pnls.append(pnl)
        
        return sum(pnls), pnls
    
    def reconcile_with_mt5(self, mt5_positions: List[Dict]) -> Dict[str, any]:
        """
        Reconcile internal positions with MT5.
        
        Args:
            mt5_positions: Positions from MT5 terminal
        
        Returns:
            {
                'divergences': [...],  # Positions closed by MT5 but not tracked
                'missing': [...],      # Positions in MT5 but not in tracker
                'reconciled': True/False
            }
        """
        mt5_tickets = {p['ticket'] for p in mt5_positions}
        internal_tickets = {t for t, p in self.positions.items() if p.is_open()}
        
        divergences = []
        missing = []
        
        # Check for positions closed by MT5 but open in tracker
        for ticket in internal_tickets - mt5_tickets:
            pos = self.positions[ticket]
            divergences.append({
                'ticket': ticket,
                'type': 'MANUALLY_CLOSED',
                'symbol': pos.symbol,
                'side': pos.side,
                'volume': pos.volume,
                'entry_price': pos.entry_price
            })
            logger.warning(f"Divergence: Position {ticket} closed on MT5 but open in tracker")
            
            # Auto-close in tracker
            self.close_position(ticket, pos.volume)
        
        # Check for new positions on MT5 not in tracker
        for mt5_pos in mt5_positions:
            if mt5_pos['ticket'] not in self.positions:
                missing.append(mt5_pos)
                logger.warning(f"Missing: Position {mt5_pos['ticket']} on MT5 not in tracker")
        
        reconciled = len(divergences) == 0 and len(missing) == 0
        
        return {
            'divergences': divergences,
            'missing': missing,
            'reconciled': reconciled
        }
