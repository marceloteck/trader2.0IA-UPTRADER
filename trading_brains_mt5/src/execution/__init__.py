"""
Execution Engine V4 - Unified execution layer for backtest, simulation, and live trading.

This package provides:
- ExecutionEngine: Unified entry point for all executions
- FillModel: Realistic fill simulation (slippage, spread, latency)
- OrderRouter: Unified interface for SIM and MT5 routing
- PositionTracker: Maintains position state and reconciliation
- SLTPManager: Advanced SL/TP management (partial exits, break-even, trailing)
- RiskManager: Professional risk controls (circuit breakers, degrade, limits)
"""

from src.execution.execution_engine import ExecutionEngine, ExecutionResult
from src.execution.fill_model import FillModel, FillResult
from src.execution.order_router import OrderRouter, RouterSim, RouterMT5, PlaceOrderRequest
from src.execution.position_tracker import PositionTracker, PositionState
from src.execution.sl_tp_manager import SLTPManager
from src.execution.risk_manager import RiskManager, RiskEvent, RiskCheckResult

__all__ = [
    'ExecutionEngine',
    'ExecutionResult',
    'FillModel',
    'FillResult',
    'OrderRouter',
    'RouterSim',
    'RouterMT5',
    'PlaceOrderRequest',
    'PositionTracker',
    'PositionState',
    'SLTPManager',
    'RiskManager',
    'RiskEvent',
    'RiskCheckResult',
]
