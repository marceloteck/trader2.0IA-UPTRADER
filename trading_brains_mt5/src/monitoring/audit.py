"""
Audit System V4 - Complete decision trail and replay capability.

Provides:
- Decision trace (context, scores, reasoning, execution)
- Export for debugging and compliance
- Replay mechanism for post-failure analysis
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class DecisionTrace:
    """Complete record of a trading decision."""
    
    # Identification
    run_id: str  # Unique run identifier
    sequence: int  # Order in this run
    timestamp: datetime
    
    # Input context
    symbol: str
    current_price: float
    atr: float
    regime: str
    regime_confidence: float
    hour: int
    
    # Scoring
    brain_scores: Dict[str, float]  # Raw scores from each brain
    meta_weights: Dict[str, float]  # V3 MetaBrain adjustments
    adjusted_scores: Dict[str, float]  # After MetaBrain weighting
    ensemble_score: float  # Final ensemble score
    
    # RL and health
    rl_action: str  # ENTER or SKIP
    rl_confidence: float
    health_status: str  # GREEN, YELLOW, RED
    health_score: float
    
    # Liquidity
    liquidity_sufficient: bool
    spread: float
    
    # Decision
    decision: str  # ENTER, SKIP, CLOSE
    side: Optional[str] = None
    volume: Optional[float] = None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    
    # Reasoning
    reason: str = ""
    decision_factors: Dict[str, Any] = None
    
    # Execution result
    executed: bool = False
    ticket: Optional[int] = None
    filled_price: Optional[float] = None
    slippage: float = 0.0
    execution_status: str = "PENDING"  # FILLED, REJECTED, ERROR
    execution_reason: str = ""
    
    # Risk context
    risk_checks: Dict[str, bool] = None  # {check_name: passed}
    position_size_factor: float = 1.0
    daily_pnl: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        if isinstance(self.decision_factors, dict):
            d['decision_factors'] = self.decision_factors
        if isinstance(self.risk_checks, dict):
            d['risk_checks'] = self.risk_checks
        return d
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class AuditSystem:
    """
    Records and manages decision audit trail.
    """
    
    def __init__(self, db_repo=None):
        """
        Initialize audit system.
        
        Args:
            db_repo: Optional DB repo for persistence
        """
        self.db_repo = db_repo
        self.traces: Dict[int, DecisionTrace] = {}  # sequence -> trace
        self.current_run_id = ""
        self.sequence_counter = 0
        
        logger.info("AuditSystem initialized")
    
    def start_run(self, run_id: str):
        """Start new audit run."""
        self.current_run_id = run_id
        self.sequence_counter = 0
        logger.info(f"Audit run started: {run_id}")
    
    def record_decision(
        self,
        symbol: str,
        current_price: float,
        regime: str,
        regime_confidence: float,
        brain_scores: Dict[str, float],
        meta_weights: Dict[str, float],
        adjusted_scores: Dict[str, float],
        ensemble_score: float,
        rl_action: str,
        rl_confidence: float,
        health_status: str,
        health_score: float,
        liquidity_sufficient: bool,
        spread: float,
        decision: str,
        side: Optional[str] = None,
        volume: Optional[float] = None,
        entry_price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        reason: str = "",
        atr: float = 0.0,
        hour: int = 0,
        risk_checks: Optional[Dict] = None,
        daily_pnl: float = 0.0,
        position_size_factor: float = 1.0,
    ) -> DecisionTrace:
        """Record a trading decision."""
        
        self.sequence_counter += 1
        
        trace = DecisionTrace(
            run_id=self.current_run_id,
            sequence=self.sequence_counter,
            timestamp=datetime.utcnow(),
            symbol=symbol,
            current_price=current_price,
            atr=atr,
            regime=regime,
            regime_confidence=regime_confidence,
            hour=hour,
            brain_scores=brain_scores,
            meta_weights=meta_weights,
            adjusted_scores=adjusted_scores,
            ensemble_score=ensemble_score,
            rl_action=rl_action,
            rl_confidence=rl_confidence,
            health_status=health_status,
            health_score=health_score,
            liquidity_sufficient=liquidity_sufficient,
            spread=spread,
            decision=decision,
            side=side,
            volume=volume,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            reason=reason,
            risk_checks=risk_checks or {},
            daily_pnl=daily_pnl,
            position_size_factor=position_size_factor,
        )
        
        self.traces[self.sequence_counter] = trace
        
        # Save to DB
        if self.db_repo and hasattr(self.db_repo, 'insert_audit_trail'):
            self.db_repo.insert_audit_trail(trace.to_dict())
        
        logger.debug(f"Decision recorded: seq={self.sequence_counter}, "
                    f"symbol={symbol}, action={decision}")
        
        return trace
    
    def record_execution(
        self,
        sequence: int,
        executed: bool,
        ticket: Optional[int] = None,
        filled_price: Optional[float] = None,
        slippage: float = 0.0,
        status: str = "PENDING",
        reason: str = ""
    ):
        """Record execution result for a decision."""
        if sequence not in self.traces:
            logger.warning(f"Sequence {sequence} not found for execution record")
            return
        
        trace = self.traces[sequence]
        trace.executed = executed
        trace.ticket = ticket
        trace.filled_price = filled_price
        trace.slippage = slippage
        trace.execution_status = status
        trace.execution_reason = reason
        
        # Update DB
        if self.db_repo and hasattr(self.db_repo, 'update_audit_trail_execution'):
            self.db_repo.update_audit_trail_execution(
                run_id=trace.run_id,
                sequence=sequence,
                execution_data={
                    'executed': executed,
                    'ticket': ticket,
                    'filled_price': filled_price,
                    'slippage': slippage,
                    'status': status,
                    'reason': reason,
                }
            )
    
    def get_trace(self, sequence: int) -> Optional[DecisionTrace]:
        """Get trace for a specific sequence."""
        return self.traces.get(sequence)
    
    def get_run_traces(self, run_id: str) -> List[DecisionTrace]:
        """Get all traces for a run."""
        return [t for t in self.traces.values() if t.run_id == run_id]
    
    def export_run(self, run_id: str, filepath: str) -> bool:
        """
        Export all traces for a run to JSON file.
        
        Args:
            run_id: Run identifier
            filepath: Output file path
        
        Returns:
            True if successful
        """
        traces = self.get_run_traces(run_id)
        
        if not traces:
            logger.warning(f"No traces found for run {run_id}")
            return False
        
        try:
            data = {
                'run_id': run_id,
                'exported_at': datetime.utcnow().isoformat(),
                'trace_count': len(traces),
                'traces': [t.to_dict() for t in traces]
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Exported {len(traces)} traces to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export traces: {e}")
            return False
    
    def get_decision_summary(self, run_id: str) -> Dict:
        """Get summary statistics for a run."""
        traces = self.get_run_traces(run_id)
        
        if not traces:
            return {}
        
        total = len(traces)
        entered = sum(1 for t in traces if t.decision == "ENTER" and t.executed)
        skipped = sum(1 for t in traces if t.decision == "SKIP")
        rejected = sum(1 for t in traces if t.decision == "ENTER" and not t.executed)
        
        avg_slippage = sum(t.slippage for t in traces if t.executed) / max(entered, 1)
        
        return {
            'run_id': run_id,
            'total_decisions': total,
            'entered': entered,
            'skipped': skipped,
            'rejected': rejected,
            'avg_slippage': avg_slippage,
            'hit_rate': entered / max(total, 1),
        }
    
    def get_failure_context(self, n_before: int = 50) -> Dict:
        """
        Get context before a failure (last N decisions).
        Used for diagnostics and replay.
        
        Args:
            n_before: Number of decisions to include
        
        Returns:
            Context dict with recent traces and analysis
        """
        if not self.traces:
            return {}
        
        recent = sorted(self.traces.values(), key=lambda t: t.sequence)[-n_before:]
        
        context = {
            'run_id': self.current_run_id,
            'trace_count': len(recent),
            'traces': [t.to_dict() for t in recent],
            'analysis': {
                'last_decision': recent[-1].to_dict() if recent else None,
                'recent_regimes': list(set(t.regime for t in recent)),
                'avg_ensemble_score': sum(t.ensemble_score for t in recent) / len(recent) if recent else 0,
                'decision_distribution': {
                    'ENTER': sum(1 for t in recent if t.decision == "ENTER"),
                    'SKIP': sum(1 for t in recent if t.decision == "SKIP"),
                    'CLOSE': sum(1 for t in recent if t.decision == "CLOSE"),
                }
            }
        }
        
        return context
