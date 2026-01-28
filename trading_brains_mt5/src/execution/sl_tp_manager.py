"""
SL/TP Manager V4 - Advanced stop-loss and take-profit management.

Features:
- Partial exits (TP1/TP2/TP3)
- Break-even after TP1
- Trailing stop-loss
- Automatic SL/TP setting for MT5 (retry if not accepted initially)
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TPLevel:
    """Take-profit level."""
    level: int  # 1, 2, 3, etc
    price: float
    volume_pct: float  # % of position to close at this level (e.g., 0.5 = 50%)
    closed: bool = False
    close_time: Optional[datetime] = None


@dataclass
class SLTPConfig:
    """Configuration for SL/TP management."""
    use_partial_exits: bool = True
    tp1_price: Optional[float] = None
    tp1_volume_pct: float = 0.5  # Close 50% at TP1
    tp2_price: Optional[float] = None
    tp2_volume_pct: float = 0.3  # Close 30% at TP2
    tp3_price: Optional[float] = None
    tp3_volume_pct: float = 0.2  # Close 20% at TP3
    
    use_break_even: bool = True  # Move SL to entry after TP1
    break_even_offset: float = 0.5  # 0.5 pips offset after TP1
    
    use_trailing: bool = False
    trailing_distance: float = 10.0  # pips
    trailing_atr_mult: Optional[float] = None  # Or use ATR multiple
    
    sl_price: Optional[float] = None


class SLTPManager:
    """
    Manages stop-loss and take-profit for positions.
    """
    
    def __init__(self, settings):
        """Initialize with settings."""
        self.settings = settings
        self.positions_sltp: dict = {}  # ticket -> {tp_levels, current_sl, ...}
        
        logger.info("SLTPManager initialized")
    
    def setup_sltp(
        self,
        ticket: int,
        position: dict,  # {symbol, side, volume, entry_price, ...}
        sl: Optional[float],
        tp: Optional[float],
        config: Optional[SLTPConfig] = None
    ) -> dict:
        """
        Set up SL/TP for a position, optionally with partial exits.
        
        Args:
            ticket: Order ticket
            position: Position dict
            sl: Stop-loss price
            tp: Take-profit price (can be single price or TP1)
            config: SLTPConfig for advanced features
        
        Returns:
            Setup result
        """
        if config is None:
            config = SLTPConfig()
        
        tp_levels = []
        
        if config.use_partial_exits and config.tp1_price:
            # Set up multiple TP levels
            if config.tp1_price:
                tp_levels.append(TPLevel(1, config.tp1_price, config.tp1_volume_pct))
            if config.tp2_price:
                tp_levels.append(TPLevel(2, config.tp2_price, config.tp2_volume_pct))
            if config.tp3_price:
                tp_levels.append(TPLevel(3, config.tp3_price, config.tp3_volume_pct))
        elif tp:
            # Single TP
            tp_levels.append(TPLevel(1, tp, 1.0))
        
        self.positions_sltp[ticket] = {
            'position': position,
            'tp_levels': tp_levels,
            'current_sl': sl,
            'initial_sl': sl,
            'use_break_even': config.use_break_even,
            'break_even_offset': config.break_even_offset,
            'break_even_activated': False,
            'use_trailing': config.use_trailing,
            'trailing_distance': config.trailing_distance,
            'highest_price': position.get('entry_price', 0),
        }
        
        logger.info(f"Position {ticket} SL/TP setup: "
                   f"SL={sl}, TP_levels={len(tp_levels)}")
        
        return self.positions_sltp[ticket]
    
    def check_tp_levels(
        self,
        ticket: int,
        current_price: float
    ) -> List[dict]:
        """
        Check if any TP levels have been hit.
        
        Returns:
            List of TP hits: [{level, price, volume_pct}, ...]
        """
        if ticket not in self.positions_sltp:
            return []
        
        sltp_data = self.positions_sltp[ticket]
        position = sltp_data['position']
        hits = []
        
        for tp in sltp_data['tp_levels']:
            if tp.closed:
                continue
            
            # Check if TP is hit based on side
            hit = False
            if position['side'] == 'BUY' and current_price >= tp.price:
                hit = True
            elif position['side'] == 'SELL' and current_price <= tp.price:
                hit = True
            
            if hit:
                tp.closed = True
                tp.close_time = datetime.utcnow()
                hits.append({
                    'ticket': ticket,
                    'level': tp.level,
                    'price': tp.price,
                    'volume_pct': tp.volume_pct,
                    'volume_to_close': position['volume'] * tp.volume_pct,
                    'timestamp': tp.close_time
                })
                
                logger.info(f"TP{tp.level} hit for position {ticket} @ {current_price:.5f}")
                
                # Check if should activate break-even
                if sltp_data['use_break_even'] and tp.level == 1:
                    self._activate_break_even(ticket, current_price)
        
        return hits
    
    def _activate_break_even(self, ticket: int, entry_price: float):
        """Activate break-even SL after TP1."""
        if ticket not in self.positions_sltp:
            return
        
        sltp_data = self.positions_sltp[ticket]
        position = sltp_data['position']
        
        # Move SL to entry + offset
        offset = sltp_data['break_even_offset']
        
        if position['side'] == 'BUY':
            new_sl = entry_price + offset
        else:  # SELL
            new_sl = entry_price - offset
        
        sltp_data['current_sl'] = new_sl
        sltp_data['break_even_activated'] = True
        
        logger.info(f"Position {ticket} break-even activated: SL={new_sl:.5f}")
    
    def check_trailing_stop(
        self,
        ticket: int,
        current_price: float,
        atr: Optional[float] = None
    ) -> Optional[float]:
        """
        Update trailing stop if configured.
        
        Returns:
            New SL price if updated, None if no change
        """
        if ticket not in self.positions_sltp:
            return None
        
        sltp_data = self.positions_sltp[ticket]
        if not sltp_data['use_trailing']:
            return None
        
        position = sltp_data['position']
        
        # Update highest/lowest price
        if position['side'] == 'BUY':
            if current_price > sltp_data['highest_price']:
                sltp_data['highest_price'] = current_price
                
                # Calculate trailing SL
                if sltp_data['trailing_atr_mult'] and atr:
                    distance = atr * sltp_data['trailing_atr_mult']
                else:
                    distance = sltp_data['trailing_distance']
                
                new_sl = current_price - distance
                
                # Only move SL up, never down
                if new_sl > sltp_data['current_sl']:
                    old_sl = sltp_data['current_sl']
                    sltp_data['current_sl'] = new_sl
                    logger.info(f"Position {ticket} trailing SL updated: "
                               f"{old_sl:.5f} -> {new_sl:.5f}")
                    return new_sl
        
        else:  # SELL
            if current_price < sltp_data['highest_price']:  # Actually lowest
                sltp_data['highest_price'] = current_price
                
                if sltp_data['trailing_atr_mult'] and atr:
                    distance = atr * sltp_data['trailing_atr_mult']
                else:
                    distance = sltp_data['trailing_distance']
                
                new_sl = current_price + distance
                
                if new_sl < sltp_data['current_sl']:
                    old_sl = sltp_data['current_sl']
                    sltp_data['current_sl'] = new_sl
                    logger.info(f"Position {ticket} trailing SL updated: "
                               f"{old_sl:.5f} -> {new_sl:.5f}")
                    return new_sl
        
        return None
    
    def get_current_sl(self, ticket: int) -> Optional[float]:
        """Get current SL for position (accounting for break-even, trailing, etc)."""
        if ticket not in self.positions_sltp:
            return None
        
        return self.positions_sltp[ticket]['current_sl']
    
    def get_tp_levels(self, ticket: int) -> List[TPLevel]:
        """Get all TP levels for position."""
        if ticket not in self.positions_sltp:
            return []
        
        return self.positions_sltp[ticket]['tp_levels']
    
    def close_position_sltp(self, ticket: int):
        """Clean up SL/TP data when position is closed."""
        if ticket in self.positions_sltp:
            del self.positions_sltp[ticket]
            logger.debug(f"SL/TP data cleaned up for position {ticket}")
