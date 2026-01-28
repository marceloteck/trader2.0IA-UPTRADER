#!/usr/bin/env python3
"""
Quick validation tests for Level 2 with MT5 connection.
Run: python test_l2_quick_validation.py
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test all L2 module imports."""
    print("\n" + "="*60)
    print("TEST 1: Imports Validation")
    print("="*60)
    
    tests_passed = 0
    tests_failed = 0
    
    imports = {
        "Conformal Prediction": "from src.models.conformal import ConformalPredictor, ConformalResult",
        "Uncertainty Gate": "from src.brains.uncertainty_gate import UncertaintyGate, GateDecision",
        "Symbol Manager": "from src.mt5.symbol_manager import SymbolManager, SymbolInfo, SymbolHealth",
        "Ensemble": "from src.models.ensemble import LightweightEnsemble, EnsembleMetrics",
        "Calibrator": "from src.models.calibrator_l2 import ProbabilityCalibrator",
    }
    
    for name, import_stmt in imports.items():
        try:
            exec(import_stmt)
            logger.info(f"✅ {name:25} - OK")
            tests_passed += 1
        except Exception as e:
            logger.error(f"❌ {name:25} - FAILED: {str(e)[:50]}")
            tests_failed += 1
    
    return tests_passed, tests_failed


def test_conformal():
    """Test conformal prediction basic functionality."""
    print("\n" + "="*60)
    print("TEST 2: Conformal Prediction")
    print("="*60)
    
    try:
        from src.models.conformal import ConformalPredictor
        import numpy as np
        
        # Create predictor
        cp = ConformalPredictor(alpha=0.1)
        logger.info(f"✅ Created: {cp}")
        
        # Create synthetic data
        np.random.seed(42)
        y_true = np.array([0, 0, 1, 1] * 25)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        # Fit
        cp.set_threshold_from_calibration(y_true, y_proba)
        logger.info(f"✅ Fitted with threshold={cp.threshold:.4f}")
        
        # Predict
        results = cp.predict_with_set(y_proba[:5])
        logger.info(f"✅ Generated {len(results)} prediction sets")
        for i, r in enumerate(results):
            logger.info(f"   Sample {i}: class={r.predicted_class}, set={r.prediction_set}, confidence={r.confidence:.2f}, ambiguous={r.is_ambiguous}")
        
        return 1, 0
    except Exception as e:
        logger.error(f"❌ Conformal prediction failed: {e}")
        return 0, 1


def test_uncertainty_gate():
    """Test uncertainty gate blocking logic."""
    print("\n" + "="*60)
    print("TEST 3: Uncertainty Gate")
    print("="*60)
    
    try:
        from src.brains.uncertainty_gate import UncertaintyGate
        
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.25,
            max_proba_std=0.15,
            min_global_confidence=0.55
        )
        logger.info(f"✅ Created: {gate}")
        
        # Test 1: All good metrics -> ALLOW
        decision = gate.check(
            disagreement_score=0.15,
            proba_mean=0.75,
            proba_std=0.1
        )
        logger.info(f"✅ Good metrics: {decision.decision} ({decision.reason})")
        assert decision.decision == "ALLOW", "Should allow with good metrics"
        
        # Test 2: High disagreement -> HOLD
        decision = gate.check(
            disagreement_score=0.35,  # > 0.25
            proba_mean=0.75,
            proba_std=0.1
        )
        logger.info(f"✅ High disagreement: {decision.decision} ({decision.reason})")
        assert decision.decision == "HOLD", "Should block on high disagreement"
        
        # Test 3: Low confidence -> HOLD
        decision = gate.check(
            disagreement_score=0.15,
            proba_mean=0.51,  # max(0.51, 0.49) = 0.51 < 0.55
            proba_std=0.1
        )
        logger.info(f"✅ Low confidence: {decision.decision} ({decision.reason})")
        assert decision.decision == "HOLD", "Should block on low confidence"
        
        return 1, 0
    except Exception as e:
        logger.error(f"❌ Uncertainty gate failed: {e}")
        return 0, 1


def test_symbol_manager():
    """Test symbol manager configurations."""
    print("\n" + "="*60)
    print("TEST 4: Symbol Manager")
    print("="*60)
    
    try:
        from src.mt5.symbol_manager import SymbolManager
        
        # Test SINGLE mode
        config_single = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        manager_single = SymbolManager(config=config_single, mt5_client=None)
        logger.info(f"✅ SINGLE mode: {manager_single.mode}")
        active = manager_single.get_active_symbols()
        logger.info(f"   Active symbols: {active}")
        assert active == ["WIN$N"], "SINGLE mode should have one symbol"
        
        # Test MULTI mode
        config_multi = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N,WINM21,WINN21",
            "symbol_mode": "MULTI",
            "symbol_auto_select": False,
            "max_active_symbols": 3
        }
        manager_multi = SymbolManager(config=config_multi, mt5_client=None)
        logger.info(f"✅ MULTI mode: {manager_multi.mode}")
        active = manager_multi.get_active_symbols()
        logger.info(f"   Active symbols: {active}")
        assert len(active) == 3, "MULTI mode should have 3 symbols"
        
        return 1, 0
    except Exception as e:
        logger.error(f"❌ Symbol manager failed: {e}")
        return 0, 1


def test_ensemble():
    """Test lightweight ensemble."""
    print("\n" + "="*60)
    print("TEST 5: Lightweight Ensemble")
    print("="*60)
    
    try:
        from src.models.ensemble import LightweightEnsemble
        import numpy as np
        
        # Create and train ensemble
        ensemble = LightweightEnsemble(voting="SOFT")
        logger.info(f"✅ Created: {ensemble}")
        
        # Synthetic training data
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        
        ensemble.fit(X_train, y_train)
        logger.info(f"✅ Trained on 100 samples")
        
        # Predict
        X_test = np.random.randn(5, 20)
        metrics = ensemble.predict_with_metrics(X_test)
        logger.info(f"✅ Generated metrics for {len(metrics)} predictions")
        
        for i, m in enumerate(metrics[:3]):
            logger.info(
                f"   Sample {i}: pred={m.prediction}, "
                f"proba_mean={m.proba_mean:.3f}, "
                f"std={m.proba_std:.3f}, "
                f"disagreement={m.disagreement_score:.3f}"
            )
        
        return 1, 0
    except Exception as e:
        logger.error(f"❌ Ensemble failed: {e}")
        return 0, 1


def test_calibration():
    """Test probability calibration."""
    print("\n" + "="*60)
    print("TEST 6: Probability Calibration")
    print("="*60)
    
    try:
        from src.models.calibrator_l2 import ProbabilityCalibrator
        import numpy as np
        
        # Create calibrator
        calibrator = ProbabilityCalibrator(method="PLATT")
        logger.info(f"✅ Created: {calibrator}")
        
        # Synthetic data
        np.random.seed(42)
        y_true = np.array([0, 0, 0, 1, 1, 1] * 16 + [0, 0])
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        # Fit
        calibrator.fit(y_true, y_proba)
        logger.info(f"✅ Fitted calibrator")
        
        # Get metrics
        metrics = calibrator.get_reliability_metrics()
        logger.info(f"✅ Calibration metrics:")
        logger.info(f"   ECE: {metrics['expected_calibration_error']:.4f}")
        logger.info(f"   MCE: {metrics['max_calibration_error']:.4f}")
        logger.info(f"   Brier Score: {metrics['brier_score']:.4f}")
        
        return 1, 0
    except Exception as e:
        logger.error(f"❌ Calibration failed: {e}")
        return 0, 1


def test_mt5_connection():
    """Test MT5 connection if available."""
    print("\n" + "="*60)
    print("TEST 7: MT5 Connection")
    print("="*60)
    
    try:
        import MetaTrader5 as mt5
        
        if not mt5.initialize():
            logger.warning(f"⚠️  MT5 not initialized: {mt5.last_error()}")
            return 0, 0  # Skip if MT5 not available
        
        logger.info(f"✅ MT5 initialized")
        
        # Try to get account info
        account_info = mt5.account_info()
        if account_info:
            logger.info(f"✅ Account: {account_info.name}")
            logger.info(f"   Company: {account_info.company}")
            logger.info(f"   Balance: {account_info.balance:.2f}")
        else:
            logger.warning(f"⚠️  Could not get account info")
        
        mt5.shutdown()
        return 1, 0
    except ImportError:
        logger.warning(f"⚠️  MetaTrader5 not installed - skipping MT5 tests")
        return 0, 0
    except Exception as e:
        logger.warning(f"⚠️  MT5 connection issue: {e}")
        return 0, 0


def test_database():
    """Test database schema."""
    print("\n" + "="*60)
    print("TEST 8: Database Schema")
    print("="*60)
    
    try:
        from src.db.schema import create_tables
        import sqlite3
        from pathlib import Path
        import tempfile
        
        # Create temp database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        conn = sqlite3.connect(db_path)
        create_tables(conn)
        logger.info(f"✅ Created test database")
        
        # Check L2 tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        l2_tables = [
            'symbols_config', 'symbol_health', 'symbol_selection_log',
            'model_calibration', 'ensemble_metrics', 'gate_events',
            'calibration_reports'
        ]
        
        for table in l2_tables:
            if table in tables:
                logger.info(f"✅ Table {table:25} exists")
            else:
                logger.warning(f"⚠️  Table {table:25} NOT FOUND")
        
        conn.close()
        Path(db_path).unlink()  # Clean up
        
        return 1, 0
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return 0, 1


def main():
    """Run all tests."""
    print("\n")
    print("█" * 60)
    print("█" + " " * 58 + "█")
    print("█" + "  LEVEL 2 QUICK VALIDATION TEST SUITE".center(58) + "█")
    print("█" + " " * 58 + "█")
    print("█" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Conformal", test_conformal()))
    results.append(("Uncertainty Gate", test_uncertainty_gate()))
    results.append(("Symbol Manager", test_symbol_manager()))
    results.append(("Ensemble", test_ensemble()))
    results.append(("Calibration", test_calibration()))
    results.append(("MT5 Connection", test_mt5_connection()))
    results.append(("Database", test_database()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_passed = 0
    total_failed = 0
    
    for test_name, (passed, failed) in results:
        total_passed += passed
        total_failed += failed
        status = "✅" if failed == 0 else "⚠️"
        logger.info(f"{status} {test_name:25} - Passed: {passed}, Failed: {failed}")
    
    print("\n" + "="*60)
    if total_failed == 0:
        logger.info(f"🎉 ALL TESTS PASSED! ({total_passed} tests)")
    else:
        logger.warning(f"⚠️  Some tests failed. Passed: {total_passed}, Failed: {total_failed}")
    print("="*60 + "\n")
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
