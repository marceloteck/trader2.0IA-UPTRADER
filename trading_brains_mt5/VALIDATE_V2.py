#!/usr/bin/env python3
"""
V2 Implementation Validation Script
Verifica se todos os componentes V2 estão funcionando
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Testa se todos os imports funcionam"""
    print("=" * 60)
    print("VALIDANDO IMPORTS V2")
    print("=" * 60)
    
    try:
        from src.brains.brain_interface import Brain, BrainSignal, Context
        print("✅ brain_interface")
    except Exception as e:
        print(f"❌ brain_interface: {e}")
        return False
    
    try:
        from src.brains.brain_hub import BossBrain
        print("✅ brain_hub (BossBrain)")
    except Exception as e:
        print(f"❌ brain_hub: {e}")
        return False
    
    try:
        from src.brains.elliott_prob import ElliottProbBrain
        print("✅ elliott_prob (ElliottProbBrain)")
    except Exception as e:
        print(f"❌ elliott_prob: {e}")
        return False
    
    try:
        from src.brains.gann_macro import GannMacroBrain
        print("✅ gann_macro (GannMacroBrain)")
    except Exception as e:
        print(f"❌ gann_macro: {e}")
        return False
    
    try:
        from src.brains.wyckoff_adv import WyckoffAdvancedBrain
        print("✅ wyckoff_adv (WyckoffAdvancedBrain)")
    except Exception as e:
        print(f"❌ wyckoff_adv: {e}")
        return False
    
    try:
        from src.brains.cluster_proxy import ClusterProxyBrain
        print("✅ cluster_proxy (ClusterProxyBrain)")
    except Exception as e:
        print(f"❌ cluster_proxy: {e}")
        return False
    
    try:
        from src.brains.liquidity_levels import LiquidityBrain
        print("✅ liquidity_levels (LiquidityBrain)")
    except Exception as e:
        print(f"❌ liquidity_levels: {e}")
        return False
    
    try:
        from src.backtest.engine import run_backtest
        print("✅ backtest.engine")
    except Exception as e:
        print(f"❌ backtest.engine: {e}")
        return False
    
    try:
        from src.training.walk_forward import run_walk_forward
        print("✅ training.walk_forward")
    except Exception as e:
        print(f"❌ training.walk_forward: {e}")
        return False
    
    try:
        from src.dashboard.api import app
        print("✅ dashboard.api")
    except Exception as e:
        print(f"❌ dashboard.api: {e}")
        return False
    
    try:
        from src.db.schema import create_tables
        print("✅ db.schema")
    except Exception as e:
        print(f"❌ db.schema: {e}")
        return False
    
    try:
        from src.db import repo
        print("✅ db.repo")
    except Exception as e:
        print(f"❌ db.repo: {e}")
        return False
    
    try:
        from src.config.settings import load_settings
        print("✅ config.settings")
    except Exception as e:
        print(f"❌ config.settings: {e}")
        return False
    
    return True


def test_brains_instantiation():
    """Testa se todos os cérebros podem ser instanciados"""
    print("\n" + "=" * 60)
    print("VALIDANDO INSTANCIAÇÃO DE CÉREBROS")
    print("=" * 60)
    
    try:
        from src.brains.brain_hub import BossBrain
        boss = BossBrain()
        print(f"✅ BossBrain com {len(boss.brains)} cérebros")
        for brain in boss.brains:
            print(f"  - {brain.name}")
    except Exception as e:
        print(f"❌ BossBrain instantiation: {e}")
        return False
    
    return True


def test_settings():
    """Testa se settings carregam corretamente"""
    print("\n" + "=" * 60)
    print("VALIDANDO SETTINGS V2")
    print("=" * 60)
    
    try:
        from src.config.settings import load_settings
        settings = load_settings()
        
        # Verificar campos V2
        v2_fields = [
            'point_value',
            'min_lot',
            'lot_step',
            'train_window_days',
            'test_window_days',
            'label_horizon_candles',
            'round_level_step',
            'session_start',
            'session_end',
            'enable_dashboard_control',
        ]
        
        for field in v2_fields:
            if hasattr(settings, field):
                value = getattr(settings, field)
                print(f"✅ {field} = {value}")
            else:
                print(f"❌ {field} não encontrado")
                return False
    except Exception as e:
        print(f"❌ Settings loading: {e}")
        return False
    
    return True


def main():
    """Executa todas as validações"""
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Brains Instantiation", test_brains_instantiation()))
    results.append(("Settings V2", test_settings()))
    
    print("\n" + "=" * 60)
    print("RESUMO DE VALIDAÇÃO")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 TODAS AS VALIDAÇÕES PASSARAM - V2 PRONTA!")
        print("=" * 60)
        return 0
    else:
        print("❌ ALGUMAS VALIDAÇÕES FALHARAM")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
