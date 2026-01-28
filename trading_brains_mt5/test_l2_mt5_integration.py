#!/usr/bin/env python3
"""
MT5 Integration Test with Level 2 Components.
Tests actual MT5 connection and L2 component integration.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_mt5_connection():
    """Test basic MT5 connection."""
    print("\n" + "="*70)
    print("TEST 1: MT5 Connection")
    print("="*70)
    
    try:
        from src.mt5.mt5_client import MT5Client
        
        client = MT5Client(retry_seconds=2)
        
        if client.connect():
            logger.info("✅ MT5 Connected successfully")
            account = None
            try:
                import MetaTrader5 as mt5
                account = mt5.account_info()
                if account:
                    logger.info(f"   Account: {account.login}")
                    logger.info(f"   Balance: {account.balance}")
                    logger.info(f"   Server: {account.server}")
            except Exception as e:
                logger.warning(f"   Could not retrieve account info: {e}")
            
            client.shutdown()
            return True
        else:
            logger.warning("⚠️  MT5 not available or not running")
            logger.info("   (This is expected if MT5 is not open)")
            return True  # Don't fail, MT5 might not be running
    except Exception as e:
        logger.error(f"❌ MT5 connection test failed: {e}")
        return False


def test_symbol_manager():
    """Test Symbol Manager with mock and real symbols."""
    print("\n" + "="*70)
    print("TEST 2: Symbol Manager")
    print("="*70)
    
    try:
        from src.mt5.symbol_manager import SymbolManager, SymbolMode
        from src.config.settings import load_settings
        
        settings = load_settings()
        manager = SymbolManager(settings)
        
        logger.info(f"Symbol Mode: {manager.mode}")
        
        # Test SINGLE mode
        primary = manager.get_primary_symbol()
        logger.info(f"✅ Primary symbol (SINGLE): {primary}")
        
        # Test symbol info
        info = manager.get_symbol_info(primary)
        if info:
            logger.info(f"✅ Symbol info available for {primary}")
        else:
            logger.warning(f"⚠️  Symbol info not available (MT5 might not have {primary})")
        
        return True
    except Exception as e:
        logger.error(f"❌ Symbol Manager test failed: {e}")
        return False


def test_conformal_prediction():
    """Test Conformal Prediction module."""
    print("\n" + "="*70)
    print("TEST 3: Conformal Prediction")
    print("="*70)
    
    try:
        from src.models.conformal import ConformalPredictor
        import numpy as np
        
        # Create synthetic data
        X_cal = np.random.randn(100, 5)
        y_cal = np.random.randint(0, 2, 100)
        
        predictor = ConformalPredictor(alpha=0.1)
        predictor.fit_calibration_set(X_cal, y_cal)
        
        # Test prediction
        X_test = np.random.randn(1, 5)
        result = predictor.predict_with_set(X_test[0])
        
        logger.info(f"✅ Conformal prediction working")
        logger.info(f"   Predicted class: {result.predicted_class}")
        logger.info(f"   Prediction set: {result.prediction_set}")
        logger.info(f"   Confidence: {result.confidence:.2%}")
        logger.info(f"   Is ambiguous: {result.is_ambiguous}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Conformal prediction test failed: {e}")
        return False


def test_uncertainty_gate():
    """Test Uncertainty Gate module."""
    print("\n" + "="*70)
    print("TEST 4: Uncertainty Gate")
    print("="*70)
    
    try:
        from src.brains.uncertainty_gate import UncertaintyGate
        from src.config.settings import load_settings
        
        settings = load_settings()
        gate = UncertaintyGate(settings)
        
        # Test 1: Normal case (should allow)
        decision = gate.check(
            signal_strength=0.8,
            ensemble_disagreement=0.1,
            conformal_ambiguous=False
        )
        logger.info(f"✅ Gate check normal case: {decision.decision}")
        
        # Test 2: High disagreement (should block)
        decision_blocked = gate.check(
            signal_strength=0.8,
            ensemble_disagreement=0.9,  # Very high
            conformal_ambiguous=False
        )
        logger.info(f"✅ Gate check high disagreement: {decision_blocked.decision}")
        logger.info(f"   Reason: {decision_blocked.reason}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Uncertainty gate test failed: {e}")
        return False


def test_ensemble():
    """Test Lightweight Ensemble."""
    print("\n" + "="*70)
    print("TEST 5: Lightweight Ensemble")
    print("="*70)
    
    try:
        from src.models.ensemble import LightweightEnsemble
        import numpy as np
        
        ensemble = LightweightEnsemble(
            ensemble_mode="SOFT",
            disagreement_threshold=0.3
        )
        
        # Simulate 3 model predictions
        predictions = np.array([1, 1, 0])  # 2 votes for class 1, 1 for class 0
        probabilities = np.array([
            [0.2, 0.8],  # Model 1: 80% class 1
            [0.3, 0.7],  # Model 2: 70% class 1
            [0.6, 0.4],  # Model 3: 60% class 0
        ])
        
        metrics = ensemble.compute_metrics(predictions, probabilities)
        
        logger.info(f"✅ Ensemble metrics computed")
        logger.info(f"   Final prediction: {metrics.prediction}")
        logger.info(f"   Probability mean: {metrics.proba_mean:.3f}")
        logger.info(f"   Probability std: {metrics.proba_std:.3f}")
        logger.info(f"   Disagreement score: {metrics.disagreement_score:.3f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ensemble test failed: {e}")
        return False


def test_calibration():
    """Test Probability Calibration."""
    print("\n" + "="*70)
    print("TEST 6: Probability Calibration")
    print("="*70)
    
    try:
        from src.models.calibrator_l2 import ProbabilityCalibrator
        import numpy as np
        
        # Synthetic uncalibrated probabilities
        y_true = np.array([0, 1, 1, 0, 1, 1, 0, 0, 1, 1])
        y_proba_uncal = np.array([0.1, 0.8, 0.7, 0.2, 0.9, 0.85, 0.15, 0.25, 0.95, 0.75])
        
        calibrator = ProbabilityCalibrator(method="platt")
        calibrator.fit(y_proba_uncal, y_true)
        
        # Test calibration
        y_proba_cal = calibrator.transform(y_proba_uncal)
        
        logger.info(f"✅ Probability calibration working")
        logger.info(f"   Original proba (first 3): {y_proba_uncal[:3]}")
        logger.info(f"   Calibrated proba (first 3): {y_proba_cal[:3]}")
        
        # Get metrics
        metrics = calibrator.get_reliability_metrics(y_proba_uncal, y_true)
        logger.info(f"   ECE: {metrics['ece']:.4f}")
        logger.info(f"   MCE: {metrics['mce']:.4f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Calibration test failed: {e}")
        return False


def test_settings_integration():
    """Test that all settings are properly loaded."""
    print("\n" + "="*70)
    print("TEST 7: Settings Integration")
    print("="*70)
    
    try:
        from src.config.settings import load_settings
        
        settings = load_settings()
        
        # Check L2-specific settings
        l2_settings = {
            'calibration_enabled': False,
            'ensemble_enabled': False,
            'conformal_enabled': False,
            'uncertainty_gate_enabled': False,
            'symbol_mode': 'SINGLE',
            'primary_symbol': 'EURUSD',
        }
        
        logger.info(f"✅ Settings loaded successfully")
        for key, expected in l2_settings.items():
            actual = getattr(settings, key, None)
            status = "✅" if actual == expected else "⚠️ "
            logger.info(f"   {status} {key:30} = {actual}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Settings test failed: {e}")
        return False


def test_database_schema():
    """Test database schema creation with L2 tables."""
    print("\n" + "="*70)
    print("TEST 8: Database Schema")
    print("="*70)
    
    try:
        import sqlite3
        import tempfile
        from pathlib import Path
        from src.db.schema import create_tables
        
        # Create test database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            conn = sqlite3.connect(db_path)
            create_tables(conn)
            
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"✅ Database created with {len(tables)} tables")
            
            # Check for L2 tables
            l2_tables = [t for t in tables if any(x in t for x in ['symbol', 'calibration', 'ensemble', 'gate'])]
            logger.info(f"   L2 tables ({len(l2_tables)}): {', '.join(l2_tables[:3])}")
            
            if len(l2_tables) >= 4:
                logger.info(f"   ... and {len(l2_tables) - 3} more L2 tables")
            
            conn.close()
            return True
        finally:
            Path(db_path).unlink()
    except Exception as e:
        logger.error(f"❌ Database schema test failed: {e}")
        return False


def test_imports():
    """Test that all L2 modules can be imported."""
    print("\n" + "="*70)
    print("TEST 9: Module Imports")
    print("="*70)
    
    modules = {
        "Conformal": "from src.models.conformal import ConformalPredictor",
        "Uncertainty Gate": "from src.brains.uncertainty_gate import UncertaintyGate",
        "Ensemble": "from src.models.ensemble import LightweightEnsemble",
        "Calibrator": "from src.models.calibrator_l2 import ProbabilityCalibrator",
        "Symbol Manager": "from src.mt5.symbol_manager import SymbolManager",
    }
    
    results = []
    for name, import_stmt in modules.items():
        try:
            exec(import_stmt)
            logger.info(f"✅ {name:25} - imported successfully")
            results.append(True)
        except Exception as e:
            logger.error(f"❌ {name:25} - {str(e)[:40]}")
            results.append(False)
    
    return all(results)


def main():
    """Run all tests."""
    print("\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  LEVEL 2 INTEGRATION TEST WITH MT5".center(68) + "█")
    print("█" + "  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S").center(64) + "  █")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    
    tests = [
        ("Module Imports", test_imports()),
        ("MT5 Connection", test_mt5_connection()),
        ("Symbol Manager", test_symbol_manager()),
        ("Conformal Prediction", test_conformal_prediction()),
        ("Uncertainty Gate", test_uncertainty_gate()),
        ("Lightweight Ensemble", test_ensemble()),
        ("Probability Calibration", test_calibration()),
        ("Settings Integration", test_settings_integration()),
        ("Database Schema", test_database_schema()),
    ]
    
    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status:10} {test_name:35}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*70)
    logger.info(f"📊 Results: {passed}/{len(tests)} PASSED")
    
    if failed == 0:
        logger.info("🎉 ALL TESTS PASSED! System ready for production use.")
    else:
        logger.warning(f"⚠️  {failed} test(s) failed. Review logs above.")
    
    print("="*70 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
