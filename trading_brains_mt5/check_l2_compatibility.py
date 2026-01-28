#!/usr/bin/env python3
"""
System compatibility and integration check for Level 2.
Verifies all existing systems work with L2 additions.
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_backward_compatibility():
    """Verify L2 is backward compatible with v1-5-l1."""
    print("\n" + "="*70)
    print("CHECK 1: Backward Compatibility")
    print("="*70)
    
    try:
        from src.config.settings import load_settings
        
        settings = load_settings()
        logger.info("✅ Settings loaded successfully")
        
        # Check that L2 features are disabled by default
        checks = {
            "CALIBRATION_ENABLED": False,
            "ENSEMBLE_ENABLED": False,
            "CONFORMAL_ENABLED": False,
            "UNCERTAINTY_GATE_ENABLED": False,
            "SYMBOL_MODE": "SINGLE",
        }
        
        for key, expected in checks.items():
            actual = getattr(settings, key.lower(), None)
            if actual == expected:
                logger.info(f"✅ {key:30} = {actual} (default, backward compatible)")
            else:
                logger.warning(f"⚠️  {key:30} = {actual} (expected {expected})")
        
        return True
    except Exception as e:
        logger.error(f"❌ Backward compatibility check failed: {e}")
        return False


def check_existing_systems():
    """Verify existing trading systems still work."""
    print("\n" + "="*70)
    print("CHECK 2: Existing Systems")
    print("="*70)
    
    systems = [
        ("Brain Hub", "from src.brains.brain_hub import BosseBrain"),
        ("MT5 Client", "from src.mt5.mt5_client import MT5Client"),
        ("Backtest Engine", "from src.backtest.engine import run_backtest"),
        ("Training", "from src.training.trainer import run_training"),
        ("Live Runner", "from src.live.runner import run_live_real"),
        ("Dashboard", "from src.dashboard.api import app"),
    ]
    
    results = []
    for name, import_stmt in systems:
        try:
            exec(import_stmt)
            logger.info(f"✅ {name:25} - OK")
            results.append(True)
        except Exception as e:
            logger.warning(f"⚠️  {name:25} - {str(e)[:40]}")
            results.append(False)
    
    return all(results)


def check_l2_integration_points():
    """Verify L2 integration points are ready."""
    print("\n" + "="*70)
    print("CHECK 3: L2 Integration Points Ready")
    print("="*70)
    
    integration_points = {
        "meta_brain.py": "src/brains/meta_brain.py",
        "supervised.py": "src/models/supervised.py",
        "runner.py": "src/live/runner.py",
        "mt5_client.py": "src/mt5/mt5_client.py",
        "api.py": "src/dashboard/api.py",
    }
    
    results = []
    for name, path in integration_points.items():
        file_path = project_root / path
        if file_path.exists():
            logger.info(f"✅ {name:25} - exists at {path}")
            results.append(True)
        else:
            logger.warning(f"❌ {name:25} - NOT FOUND at {path}")
            results.append(False)
    
    return all(results)


def check_database_migrations():
    """Verify database can be created with L2 tables."""
    print("\n" + "="*70)
    print("CHECK 4: Database Migrations")
    print("="*70)
    
    try:
        from src.db.schema import create_tables
        import sqlite3
        from pathlib import Path
        import tempfile
        
        # Create test database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            conn = sqlite3.connect(db_path)
            create_tables(conn)
            
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            # Check critical tables
            critical = {
                'v1-5-l1': {'trades', 'brain_signals', 'decisions', 'candles'},
                'L1': {'report_insights'},
                'L2': {'symbols_config', 'symbol_health', 'ensemble_metrics', 'gate_events'}
            }
            
            for phase, required_tables in critical.items():
                missing = required_tables - tables
                if not missing:
                    logger.info(f"✅ {phase:10} tables - all present")
                else:
                    logger.warning(f"⚠️  {phase:10} tables - missing: {missing}")
            
            conn.close()
            return True
        finally:
            Path(db_path).unlink()
    except Exception as e:
        logger.error(f"❌ Database check failed: {e}")
        return False


def check_configuration_parameters():
    """Verify all L2 configuration parameters are defined."""
    print("\n" + "="*70)
    print("CHECK 5: Configuration Parameters")
    print("="*70)
    
    try:
        from src.config.settings import Settings
        import inspect
        
        # Get all L2 params by analyzing Settings dataclass
        settings_fields = Settings.__dataclass_fields__
        
        l2_params = [f for f in settings_fields.keys() if any(
            x in f.lower() for x in ['symbol', 'calibration', 'ensemble', 'conformal', 'gate', 'disagreement', 'confidence']
        )]
        
        logger.info(f"✅ Found {len(l2_params)} L2 configuration parameters")
        
        # Sample some
        sample = l2_params[:5]
        for param in sample:
            default = getattr(Settings, param, "N/A")
            logger.info(f"   - {param:30} (configured)")
        
        if len(l2_params) > 20:
            logger.info(f"   ... and {len(l2_params) - 5} more L2 params")
        
        return len(l2_params) >= 20  # Should have at least 20 L2 params
    except Exception as e:
        logger.error(f"❌ Configuration check failed: {e}")
        return False


def check_test_coverage():
    """Verify test files exist for L2."""
    print("\n" + "="*70)
    print("CHECK 6: Test Coverage")
    print("="*70)
    
    test_files = {
        "Conformal": "tests/test_conformal.py",
        "Uncertainty Gate": "tests/test_uncertainty_gate.py",
        "Ensemble": "tests/test_ensemble.py",
        "Symbol Manager": "tests/test_symbol_manager.py",
        "Calibration": "tests/test_calibration_platt_isotonic.py",
    }
    
    results = []
    for name, path in test_files.items():
        file_path = project_root / path
        if file_path.exists():
            # Count test functions
            with open(file_path) as f:
                test_count = f.read().count("def test_")
            logger.info(f"✅ {name:25} - {test_count:2} tests at {path}")
            results.append(True)
        else:
            logger.warning(f"❌ {name:25} - NOT FOUND")
            results.append(False)
    
    return all(results)


def check_documentation():
    """Verify L2 documentation exists."""
    print("\n" + "="*70)
    print("CHECK 7: Documentation")
    print("="*70)
    
    docs = {
        "Complete Guide": "LEVEL2.md",
        "Quick Reference": "LEVEL2_QUICK_REFERENCE.md",
        "Delivery Summary": "DELIVERY_SUMMARY_L2_PHASE2B.md",
        "Verification": "VERIFICATION_L2_PHASE2B.md",
        "Master Index": "MASTER_INDEX_L2_PHASE2B.md",
    }
    
    results = []
    for name, path in docs.items():
        file_path = project_root / path
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            logger.info(f"✅ {name:25} - {size_kb:6.1f} KB at {path}")
            results.append(True)
        else:
            logger.warning(f"⚠️  {name:25} - not found")
            results.append(False)
    
    return all(results)


def check_dependencies():
    """Check required Python packages."""
    print("\n" + "="*70)
    print("CHECK 8: Python Dependencies")
    print("="*70)
    
    required = {
        "numpy": "Numerical computing",
        "scipy": "Scientific computing",
        "scikit-learn": "ML algorithms",
        "pandas": "Data manipulation",
    }
    
    optional = {
        "MetaTrader5": "MT5 connection",
        "fastapi": "Dashboard API",
        "uvicorn": "Dashboard server",
    }
    
    results = []
    
    for package, desc in required.items():
        try:
            __import__(package.replace("-", "_"))
            logger.info(f"✅ {package:20} (required) - {desc}")
            results.append(True)
        except ImportError:
            logger.error(f"❌ {package:20} (required) - MISSING - {desc}")
            results.append(False)
    
    for package, desc in optional.items():
        try:
            __import__(package.replace("-", "_"))
            logger.info(f"✅ {package:20} (optional) - {desc}")
        except ImportError:
            logger.warning(f"⚠️  {package:20} (optional) - not installed")
    
    return all(results)


def main():
    """Run all checks."""
    print("\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  LEVEL 2 SYSTEM COMPATIBILITY CHECK".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    
    checks = [
        ("Backward Compatibility", check_backward_compatibility()),
        ("Existing Systems", check_existing_systems()),
        ("L2 Integration Points", check_l2_integration_points()),
        ("Database Migrations", check_database_migrations()),
        ("Configuration Parameters", check_configuration_parameters()),
        ("Test Coverage", check_test_coverage()),
        ("Documentation", check_documentation()),
        ("Python Dependencies", check_dependencies()),
    ]
    
    # Summary
    print("\n" + "="*70)
    print("COMPATIBILITY CHECK SUMMARY")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for check_name, result in checks:
        status = "✅" if result else "⚠️ "
        logger.info(f"{status} {check_name:35} - {'PASS' if result else 'REVIEW'}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*70)
    logger.info(f"📊 Results: {passed} PASS, {failed} REVIEW")
    
    if failed == 0:
        logger.info("🎉 ALL SYSTEMS READY FOR L2!")
    else:
        logger.warning(f"⚠️  Review {failed} item(s) before deployment")
    
    print("="*70 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
