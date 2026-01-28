"""
Execution Engine V4 - Unified execution orchestrator.

Coordinates:
- Risk checks
- Order routing (SIM or MT5)
- SL/TP management
- Position tracking
- Audit logging
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution mode."""
    BACKTEST = "BACKTEST"
    LIVE_SIM = "LIVE_SIM"
    LIVE_REAL = "LIVE_REAL"


@dataclass
class Decision:
    """Trading decision from BossBrain."""
    action: str  # ENTER, SKIP, CLOSE
    symbol: str
    side: Optional[str] = None  # BUY or SELL
    volume: Optional[float] = None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    confidence: float = 0.5
    reason: str = ""
    brain_scores: Dict[str, float] = field(default_factory=dict)
    regime: str = ""
    meta_weights: Dict[str, float] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of execution attempt."""
    success: bool
    decision: Decision
    
    # Order result
    ticket: Optional[int] = None
    filled_price: Optional[float] = None
    slippage: float = 0.0
    
    # Execution details
    order_status: str = ""  # FILLED, REJECTED, ERROR
    reason: str = ""
    
    # Risk check
    risk_passed: bool = False
    risk_reason: str = ""
    
    # P&L if closed
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'success': self.success,
            'decision': {
                'action': self.decision.action,
                'symbol': self.decision.symbol,
                'side': self.decision.side,
                'volume': self.decision.volume,
                'confidence': self.decision.confidence,
            },
            'ticket': self.ticket,
            'filled_price': self.filled_price,
            'slippage': self.slippage,
            'order_status': self.order_status,
            'reason': self.reason,
            'risk_passed': self.risk_passed,
            'risk_reason': self.risk_reason,
            'pnl': self.pnl,
            'timestamp': self.timestamp.isoformat(),
        }


class ExecutionEngine:
    """
    Unified execution engine for all modes.
    
    Orchestrates:
    1. Risk checks
    2. Order routing (SIM or MT5)
    3. SL/TP setup
    4. Position tracking
    5. Audit logging
    """
    
    def __init__(
        self,
        mode: ExecutionMode,
        order_router,
        risk_manager,
        sltp_manager,
        position_tracker,
        fill_model,
        db_repo=None,
        settings=None
    ):
        """
        Initialize execution engine.
        
        Args:
            mode: BACKTEST, LIVE_SIM, or LIVE_REAL
            order_router: OrderRouter instance
            risk_manager: RiskManager instance
            sltp_manager: SLTPManager instance
            position_tracker: PositionTracker instance
            fill_model: FillModel instance
            db_repo: Optional DB repo
            settings: Optional settings dict
        """
        self.mode = mode
        self.order_router = order_router
        self.risk_manager = risk_manager
        self.sltp_manager = sltp_manager
        self.position_tracker = position_tracker
        self.fill_model = fill_model
        self.db_repo = db_repo
        self.settings = settings or {}
        
        logger.info(f"ExecutionEngine initialized: mode={mode.value}")
    
    def execute(
        self,
        decision: Decision,
        current_prices: Optional[Dict[str, float]] = None,
        volatility_data: Optional[Dict[str, float]] = None
    ) -> ExecutionResult:
        """
        Execute a trading decision.
        
        Args:
            decision: Decision from BossBrain
            current_prices: Current market prices {symbol: price}
            volatility_data: Volatility metrics {symbol: atr, ...}
        
        Returns:
            ExecutionResult with outcome
        """
        result = ExecutionResult(success=False, decision=decision)
        
        logger.info(f"Executing decision: {decision.action} {decision.symbol} "
                   f"@ {decision.entry_price} (confidence={decision.confidence:.2f})")
        
        # Handle SKIP action
        if decision.action == "SKIP":
            result.success = True
            result.reason = "Action is SKIP"
            result.order_status = "SKIPPED"
            return result
        
        # Handle CLOSE action
        if decision.action == "CLOSE":
            return self._execute_close(decision)
        
        # ENTER action
        if decision.action != "ENTER":
            result.reason = f"Unknown action: {decision.action}"
            return result
        
        # Validate decision
        if not decision.symbol or not decision.side or not decision.volume:
            result.reason = "Incomplete decision (missing symbol/side/volume)"
            return result
        
        # Run risk checks
        atr = volatility_data.get(decision.symbol, 0) if volatility_data else 0
        current_price = current_prices.get(decision.symbol, 0) if current_prices else 0
        
        risk_check = self.risk_manager.check_can_trade(
            brain_scores=decision.brain_scores,
            atr=atr,
            close_price=current_price
        )
        
        result.risk_passed = risk_check.passed
        result.risk_reason = risk_check.reason
        
        if not risk_check.passed:
            result.reason = f"Risk check failed: {risk_check.reason}"
            logger.warning(f"Trade rejected by risk manager: {risk_check.reason}")
            self._log_execution(result)
            return result
        
        # Apply position size factor from risk degrade
        volume = decision.volume * self.risk_manager.get_position_size_factor()
        
        # Get fill from model
        fill_result = self.fill_model.calculate_fill(
            requested_price=decision.entry_price,
            side=decision.side,
            atr=atr,
            symbol=decision.symbol,
            is_live=(self.mode == ExecutionMode.LIVE_REAL)
        )
        
        if not fill_result.success:
            result.reason = f"Fill model rejected: {fill_result.reason}"
            result.order_status = "REJECTED"
            logger.warning(f"Fill rejected: {fill_result.reason}")
            self._log_execution(result)
            return result
        
        # Place order
        from src.execution.order_router import PlaceOrderRequest
        
        order_request = PlaceOrderRequest(
            symbol=decision.symbol,
            side=decision.side,
            volume=volume,
            entry_price=decision.entry_price,
            sl=decision.sl,
            tp=decision.tp,
            comment=f"Regime:{decision.regime} Conf:{decision.confidence:.2f}",
            magic=hash(f"{decision.symbol}{decision.side}") & 0xFFFFFF
        )
        
        order_event = self.order_router.place_order(order_request)
        
        if order_event.status.value == "FILLED":
            result.success = True
            result.ticket = order_event.ticket
            result.filled_price = order_event.filled_price
            result.slippage = fill_result.slippage
            result.order_status = "FILLED"
            
            # Set up SL/TP management
            position = {
                'symbol': decision.symbol,
                'side': decision.side,
                'volume': volume,
                'entry_price': order_event.filled_price,
            }
            
            from src.execution.sl_tp_manager import SLTPConfig
            
            sltp_config = SLTPConfig(
                sl_price=decision.sl,
                use_partial_exits=self.settings.get('USE_PARTIAL_EXITS', False),
                use_break_even=self.settings.get('BREAK_EVEN_AFTER_TP1', True),
                use_trailing=self.settings.get('TRAILING_ENABLED', False),
            )
            
            self.sltp_manager.setup_sltp(
                ticket=result.ticket,
                position=position,
                sl=decision.sl,
                tp=decision.tp,
                config=sltp_config
            )
            
            # Record for risk tracking
            self.risk_manager.last_trade_time = datetime.utcnow()
            
        else:
            result.success = False
            result.order_status = order_event.status.value
            result.reason = order_event.reason or "Order rejected"
            logger.warning(f"Order rejected: {order_event.reason}")
        
        # Log execution
        self._log_execution(result)
        
        return result
    
    def _execute_close(self, decision: Decision) -> ExecutionResult:
        """Execute close position decision."""
        result = ExecutionResult(success=False, decision=decision)
        
        # Find position to close (for now, close last one)
        open_positions = self.position_tracker.get_open_positions()
        
        if not open_positions:
            result.reason = "No open positions to close"
            return result
        
        # Close the oldest open position
        position = open_positions[0]
        ticket = position.ticket
        
        close_event = self.order_router.close_position(ticket, position.volume)
        
        if close_event.status.value == "FILLED":
            result.success = True
            result.ticket = ticket
            result.close_price = close_event.filled_price
            
            # Calculate P&L
            if position.side == "BUY":
                result.pnl = (close_event.filled_price - position.entry_price) * position.volume
            else:
                result.pnl = (position.entry_price - close_event.filled_price) * position.volume
            
            # Record for risk tracking
            self.risk_manager.record_trade(
                side=position.side,
                volume=position.volume,
                entry=position.entry_price,
                exit_price=close_event.filled_price
            )
            
            # Clean up SL/TP
            self.sltp_manager.close_position_sltp(ticket)
        
        return result
    
    def _log_execution(self, result: ExecutionResult):
        """Log execution result to DB."""
        if self.db_repo and hasattr(self.db_repo, 'insert_execution_result'):
            self.db_repo.insert_execution_result(result.to_dict())
