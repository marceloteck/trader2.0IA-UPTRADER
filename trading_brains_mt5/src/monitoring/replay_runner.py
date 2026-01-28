"""
Replay Runner V4 - Replay decision engine for post-failure diagnostics.

Allows:
- Replaying historical decisions
- Comparing actual vs simulated outcomes
- Debugging divergences
- Generating diagnostic reports
"""

from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class ReplayRunner:
    """
    Replays decisions from audit trail for diagnostics.
    """
    
    def __init__(self, db_repo, audit_system):
        """
        Initialize replay runner.
        
        Args:
            db_repo: Database repo for loading historical data
            audit_system: AuditSystem for accessing traces
        """
        self.db_repo = db_repo
        self.audit_system = audit_system
    
    def replay_last_decisions(
        self,
        n_decisions: int = 100,
        compare_mode: bool = True
    ) -> Dict:
        """
        Replay the last N decisions and optionally compare with actual outcomes.
        
        Args:
            n_decisions: Number of decisions to replay (default: last 100)
            compare_mode: If True, compare actual vs replayed
        
        Returns:
            Replay report with findings and divergences
        """
        
        logger.info(f"Replaying last {n_decisions} decisions...")
        
        # Get context
        context = self.audit_system.get_failure_context(n_before=n_decisions)
        
        if not context['traces']:
            return {
                'success': False,
                'reason': 'No traces found',
                'divergences': []
            }
        
        traces = context['traces']
        divergences = []
        
        # Replay each decision
        for trace_data in traces:
            # Reconstruct the decision scenario
            scenario = {
                'symbol': trace_data['symbol'],
                'current_price': trace_data['current_price'],
                'atr': trace_data['atr'],
                'regime': trace_data['regime'],
                'regime_confidence': trace_data['regime_confidence'],
                'brain_scores': trace_data['brain_scores'],
                'meta_weights': trace_data['meta_weights'],
                'ensemble_score': trace_data['ensemble_score'],
            }
            
            # Get actual outcome from DB
            if trace_data['executed'] and trace_data['ticket']:
                try:
                    position = self.db_repo.fetch_position_by_ticket(trace_data['ticket'])
                    
                    if compare_mode and position:
                        # Check for divergences
                        if abs(position.get('entry_price', 0) - (trace_data['filled_price'] or 0)) > 0.0001:
                            divergences.append({
                                'type': 'FILL_PRICE_DIVERGENCE',
                                'sequence': trace_data['sequence'],
                                'expected': trace_data['filled_price'],
                                'actual': position.get('entry_price'),
                                'difference': position.get('entry_price', 0) - (trace_data['filled_price'] or 0),
                            })
                except Exception as e:
                    logger.warning(f"Could not fetch position {trace_data['ticket']}: {e}")
        
        # Generate report
        report = {
            'success': True,
            'replay_time': datetime.utcnow().isoformat(),
            'traces_replayed': len(traces),
            'divergences': divergences,
            'summary': {
                'total_divergences': len(divergences),
                'fill_price_divergences': sum(1 for d in divergences if d['type'] == 'FILL_PRICE_DIVERGENCE'),
            }
        }
        
        logger.info(f"Replay complete: {len(traces)} traces, {len(divergences)} divergences found")
        
        return report
    
    def generate_diagnostic_report(self, run_id: str) -> Dict:
        """
        Generate comprehensive diagnostic report for a run.
        
        Args:
            run_id: Run identifier to analyze
        
        Returns:
            Detailed diagnostic report
        """
        
        logger.info(f"Generating diagnostic report for run {run_id}...")
        
        traces = self.audit_system.get_run_traces(run_id)
        
        if not traces:
            return {'success': False, 'reason': 'Run not found'}
        
        # Analyze decision quality
        entered = [t for t in traces if t.decision == "ENTER" and t.executed]
        
        winning_trades = sum(1 for t in entered if t.filled_price and t.executed)
        
        # Analyze brains performance
        brain_performance = {}
        for trace in traces:
            for brain_name, score in trace.brain_scores.items():
                if brain_name not in brain_performance:
                    brain_performance[brain_name] = {'scores': [], 'decisions': []}
                brain_performance[brain_name]['scores'].append(score)
                if trace.decision == "ENTER":
                    brain_performance[brain_name]['decisions'].append(1)
                else:
                    brain_performance[brain_name]['decisions'].append(0)
        
        # Analyze regimes
        regime_stats = {}
        for trace in traces:
            regime = trace.regime
            if regime not in regime_stats:
                regime_stats[regime] = {'count': 0, 'enters': 0, 'skips': 0}
            regime_stats[regime]['count'] += 1
            if trace.decision == "ENTER":
                regime_stats[regime]['enters'] += 1
            else:
                regime_stats[regime]['skips'] += 1
        
        # Generate report
        report = {
            'run_id': run_id,
            'generated_at': datetime.utcnow().isoformat(),
            'traces_analyzed': len(traces),
            
            'decision_stats': {
                'total': len(traces),
                'enters': sum(1 for t in traces if t.decision == "ENTER"),
                'skips': sum(1 for t in traces if t.decision == "SKIP"),
                'executed': sum(1 for t in entered),
                'rejection_rate': sum(1 for t in traces if t.decision == "ENTER" and not t.executed) / sum(1 for t in traces if t.decision == "ENTER") if any(t.decision == "ENTER" for t in traces) else 0,
            },
            
            'brain_performance': {
                brain: {
                    'avg_score': sum(data['scores']) / len(data['scores']) if data['scores'] else 0,
                    'decision_rate': sum(data['decisions']) / len(data['decisions']) if data['decisions'] else 0,
                }
                for brain, data in brain_performance.items()
            },
            
            'regime_analysis': regime_stats,
            
            'health_stats': {
                'green_periods': sum(1 for t in traces if t.health_status == "GREEN"),
                'yellow_periods': sum(1 for t in traces if t.health_status == "YELLOW"),
                'red_periods': sum(1 for t in traces if t.health_status == "RED"),
            },
        }
        
        logger.info(f"Diagnostic report generated: {report['decision_stats']}")
        
        return report
    
    def compare_simulated_vs_actual(
        self,
        run_id: str,
        symbol: str
    ) -> Dict:
        """
        Compare simulated outcomes with actual outcomes.
        
        Args:
            run_id: Run to analyze
            symbol: Symbol to focus on
        
        Returns:
            Comparison report with metrics
        """
        
        logger.info(f"Comparing simulated vs actual for {symbol}...")
        
        traces = [t for t in self.audit_system.get_run_traces(run_id) 
                 if t.symbol == symbol]
        
        if not traces:
            return {'success': False, 'reason': f'No traces for {symbol}'}
        
        simulated_signals = [t for t in traces if t.decision == "ENTER"]
        actual_executions = [t for t in simulated_signals if t.executed]
        
        comparison = {
            'symbol': symbol,
            'run_id': run_id,
            'simulated_signals': len(simulated_signals),
            'actual_executions': len(actual_executions),
            'rejection_rate': (len(simulated_signals) - len(actual_executions)) / len(simulated_signals) if simulated_signals else 0,
            
            'fill_analysis': {
                'avg_slippage': sum(t.slippage for t in actual_executions) / len(actual_executions) if actual_executions else 0,
                'max_slippage': max((t.slippage for t in actual_executions), default=0),
                'min_slippage': min((t.slippage for t in actual_executions), default=0),
            },
            
            'divergences': []
        }
        
        # Check for divergences
        for trace in simulated_signals:
            if trace.executed:
                # Verify fill price is reasonable
                expected_range = [
                    trace.entry_price - (trace.atr * 0.5),
                    trace.entry_price + (trace.atr * 0.5)
                ]
                
                if not (expected_range[0] <= trace.filled_price <= expected_range[1]):
                    comparison['divergences'].append({
                        'sequence': trace.sequence,
                        'type': 'UNEXPECTED_FILL_PRICE',
                        'expected': trace.entry_price,
                        'actual': trace.filled_price,
                    })
        
        return comparison
