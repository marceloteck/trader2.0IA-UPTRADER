"""Tests for L1 cost model."""

import pytest
from src.costs import CostModel


def test_cost_model_fixo_mode():
    """Test FIXO mode returns fixed costs."""
    model = CostModel(
        mode="FIXO",
        spread_base=1.0,
        slippage_base=0.5,
        commission=5.0
    )
    
    spread, slip, comm = model.get_costs("EURUSD", hour=14, atr=0.01)
    
    assert spread == 1.0
    assert slip == 0.5
    assert comm == 5.0


def test_cost_model_volatility_adjustment():
    """Test that volatility increases slippage."""
    model = CostModel(
        mode="FIXO",
        spread_base=1.0,
        slippage_base=0.5
    )
    
    _, slip_normal = model.get_costs("EURUSD", hour=14, volatility=1.0)
    _, slip_volatile = model.get_costs("EURUSD", hour=14, volatility=2.0)
    
    assert slip_volatile > slip_normal


def test_cost_model_slippage_clamping():
    """Test that slippage is clamped to max."""
    model = CostModel(
        mode="FIXO",
        slippage_base=10.0,
        slippage_max=2.0
    )
    
    _, slip = model.get_costs("EURUSD", hour=14)
    
    assert slip <= 2.0


def test_cost_model_aprendido_mode():
    """Test APRENDIDO mode adjusts by hour."""
    model = CostModel(mode="APRENDIDO")
    
    # Asian hours (low liquidity)
    _, slip_asian = model.get_costs("EURUSD", hour=2, atr=0.01)
    
    # US hours (high liquidity)
    _, slip_us = model.get_costs("EURUSD", hour=14, atr=0.01)
    
    # Asian should have higher slippage
    assert slip_asian > slip_us


def test_cost_model_as_dict():
    """Test export to dict."""
    model = CostModel(
        mode="FIXO",
        spread_base=1.5,
        commission=10.0
    )
    
    config = model.as_dict()
    
    assert config["mode"] == "FIXO"
    assert config["spread_base"] == 1.5
    assert config["commission"] == 10.0
