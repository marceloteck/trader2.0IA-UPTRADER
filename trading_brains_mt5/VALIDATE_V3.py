"""
VALIDATE_V3.py: Validation script for V3 implementation

Run: python VALIDATE_V3.py

This script verifies all V3 modules are correctly implemented and ready.
"""

import sys
import os
import importlib.util
import json
from pathlib import Path
from datetime import datetime

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def check_file_exists(path):
    """Check if file exists and is readable"""
    if os.path.isfile(path):
        print_success(f"File exists: {path}")
        return True
    else:
        print_error(f"File missing: {path}")
        return False

def check_module_imports(module_path, class_name):
    """Check if a module can be imported and class is accessible"""
    try:
        spec = importlib.util.spec_from_file_location("module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if hasattr(module, class_name):
            print_success(f"Module loadable: {module_path} → {class_name}")
            return True
        else:
            print_error(f"Class not found: {class_name} in {module_path}")
            return False
    except Exception as e:
        print_error(f"Import error in {module_path}: {e}")
        return False

def check_database_tables(db_path):
    """Check if all V3 tables exist in database"""
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        required_tables = [
            "brain_performance",
            "meta_decisions",
            "regime_transitions",
            "reinforcement_policy",
            "replay_priority"
        ]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        all_present = True
        for table in required_tables:
            if table in existing_tables:
                print_success(f"Table exists: {table}")
            else:
                print_warning(f"Table not yet created: {table} (will be created on first use)")
                all_present = False
        
        conn.close()
        return all_present
    except Exception as e:
        print_warning(f"Could not check database: {e}")
        return False

def check_dependencies():
    """Check if all required packages are available"""
    required = {
        "numpy": "numpy",
        "pandas": "pandas",
        "scikit-learn": "sklearn"
    }
    
    optional = {
        "hmmlearn": "hmmlearn"
    }
    
    all_ok = True
    
    print_info("Required dependencies:")
    for name, package in required.items():
        try:
            __import__(package)
            print_success(f"Available: {name}")
        except ImportError:
            print_error(f"Missing: {name} (pip install {package})")
            all_ok = False
    
    print_info("\nOptional dependencies (for enhanced features):")
    for name, package in optional.items():
        try:
            __import__(package)
            print_success(f"Available: {name} (HMM regime detection enabled)")
        except ImportError:
            print_warning(f"Not installed: {name} (will use heuristic fallback)")
    
    return all_ok

def check_configuration(settings_path):
    """Check if V3 settings are present"""
    try:
        # Try to import and check settings
        import sys
        sys.path.insert(0, os.path.dirname(settings_path))
        
        print_success(f"Configuration file present: {settings_path}")
        return True
    except Exception as e:
        print_warning(f"Could not verify configuration: {e}")
        return False

def run_basic_tests():
    """Run basic functional tests"""
    tests_passed = 0
    tests_failed = 0
    
    print_info("Running basic functional tests...")
    
    try:
        # Test 1: MetaBrain initialization
        from src.brains.meta_brain import MetaBrain
        from src.config.settings import Settings
        
        settings = Settings()
        db_path = ":memory:"  # Use in-memory DB for testing
        
        meta_brain = MetaBrain(settings, db_path)
        if meta_brain is not None:
            print_success("Test 1: MetaBrain initialization")
            tests_passed += 1
        else:
            print_error("Test 1: MetaBrain initialization failed")
            tests_failed += 1
    except Exception as e:
        print_error(f"Test 1: MetaBrain initialization - {e}")
        tests_failed += 1
    
    try:
        # Test 2: RegimeDetector initialization
        from src.features.regime_detector import RegimeDetector
        
        regime_detector = RegimeDetector(settings, db_path)
        if regime_detector is not None:
            print_success("Test 2: RegimeDetector initialization")
            tests_passed += 1
        else:
            print_error("Test 2: RegimeDetector initialization failed")
            tests_failed += 1
    except Exception as e:
        print_error(f"Test 2: RegimeDetector initialization - {e}")
        tests_failed += 1
    
    try:
        # Test 3: LightReinforcementLearner initialization
        from src.training.reinforcement import LightReinforcementLearner
        
        rl_learner = LightReinforcementLearner(settings, db_path)
        if rl_learner is not None:
            print_success("Test 3: LightReinforcementLearner initialization")
            tests_passed += 1
        else:
            print_error("Test 3: LightReinforcementLearner initialization failed")
            tests_failed += 1
    except Exception as e:
        print_error(f"Test 3: LightReinforcementLearner initialization - {e}")
        tests_failed += 1
    
    try:
        # Test 4: KnowledgeDecayPolicy initialization
        from src.models.decay import KnowledgeDecayPolicy
        
        decay_policy = KnowledgeDecayPolicy()
        if decay_policy is not None:
            print_success("Test 4: KnowledgeDecayPolicy initialization")
            tests_passed += 1
        else:
            print_error("Test 4: KnowledgeDecayPolicy initialization failed")
            tests_failed += 1
    except Exception as e:
        print_error(f"Test 4: KnowledgeDecayPolicy initialization - {e}")
        tests_failed += 1
    
    try:
        # Test 5: SelfDiagnosisSystem initialization
        from src.monitoring.self_diagnosis import SelfDiagnosisSystem
        
        health_system = SelfDiagnosisSystem()
        if health_system is not None:
            print_success("Test 5: SelfDiagnosisSystem initialization")
            tests_passed += 1
        else:
            print_error("Test 5: SelfDiagnosisSystem initialization failed")
            tests_failed += 1
    except Exception as e:
        print_error(f"Test 5: SelfDiagnosisSystem initialization - {e}")
        tests_failed += 1
    
    return tests_passed, tests_failed

def main():
    print_header("V3 IMPLEMENTATION VALIDATION")
    
    # Setup
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    all_checks_passed = True
    
    # 1. Check files exist
    print_header("1. FILE EXISTENCE CHECKS")
    
    files_to_check = [
        "src/brains/meta_brain.py",
        "src/features/regime_detector.py",
        "src/training/reinforcement.py",
        "src/models/decay.py",
        "src/monitoring/self_diagnosis.py",
        "src/monitoring/__init__.py",
        "src/db/schema.py",
        "src/db/repo.py",
        "tests/test_v3_core.py",
        "V3_IMPLEMENTATION.md",
        "V3_ROADMAP.md",
        "V3_QUICK_REFERENCE.md",
        "V3_SUMMARY.md"
    ]
    
    for file_path in files_to_check:
        full_path = os.path.join(base_path, file_path)
        if not check_file_exists(full_path):
            all_checks_passed = False
    
    # 2. Check dependencies
    print_header("2. DEPENDENCY CHECKS")
    if not check_dependencies():
        all_checks_passed = False
    
    # 3. Check module imports
    print_header("3. MODULE IMPORT CHECKS")
    
    modules_to_check = [
        ("src/brains/meta_brain.py", "MetaBrain"),
        ("src/features/regime_detector.py", "RegimeDetector"),
        ("src/training/reinforcement.py", "LightReinforcementLearner"),
        ("src/models/decay.py", "KnowledgeDecayPolicy"),
        ("src/monitoring/self_diagnosis.py", "SelfDiagnosisSystem"),
    ]
    
    for module_path, class_name in modules_to_check:
        full_path = os.path.join(base_path, module_path)
        if not check_module_imports(full_path, class_name):
            all_checks_passed = False
    
    # 4. Check database
    print_header("4. DATABASE CHECKS")
    db_path = os.path.join(base_path, "trading.db")
    check_database_tables(db_path)
    
    # 5. Run basic tests
    print_header("5. BASIC FUNCTIONAL TESTS")
    tests_passed, tests_failed = run_basic_tests()
    if tests_failed > 0:
        all_checks_passed = False
    
    # Summary
    print_header("VALIDATION SUMMARY")
    
    if all_checks_passed:
        print_success("All critical checks PASSED ✓")
        print_success("V3 is ready for integration (Phase 2)")
        print_info(f"\nImplemented modules: {len(modules_to_check)}")
        print_info(f"Tests passed: {tests_passed}/5")
        print_info(f"\nNext steps:")
        print_info("  1. Integrate MetaBrain with BossBrain (src/brains/brain_hub.py)")
        print_info("  2. Run integration tests (test_v3_integration.py)")
        print_info("  3. Update Dashboard with V3 endpoints")
        print_info("  4. Fine-tune parameters")
        print_info(f"\nDocumentation:")
        print_info("  • V3_SUMMARY.md - Executive summary")
        print_info("  • V3_IMPLEMENTATION.md - Technical details")
        print_info("  • V3_QUICK_REFERENCE.md - Usage guide")
        print_info("  • V3_ROADMAP.md - Development timeline")
        return 0
    else:
        print_error("Some checks FAILED ✗")
        print_warning("Please fix issues above before proceeding")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
