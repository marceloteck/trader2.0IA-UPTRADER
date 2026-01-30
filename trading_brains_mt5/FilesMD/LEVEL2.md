# Level 2 Enhancement: Confidence, Calibration & Ensemble

## Overview

**Level 2** adds **confidence-driven decision making** to Trading Brains MT5. Instead of relying on raw probability scores, L2 combines:

1. **Probability Calibration** - Transform raw probabilities to match actual frequencies
2. **Lightweight Ensemble** - Combine 3 models (LogisticRegression, RandomForest, GradientBoosting) for robustness
3. **Conformal Prediction** - Quantify uncertainty with prediction sets and confidence intervals
4. **Uncertainty Gates** - Block trades when model disagreement or uncertainty is too high
5. **Symbol/Asset Management** - Complete configuration for single or multi-asset trading with auto-selection

**Key Principle**: *Only trade when the system is confident. When uncertain, hold.*

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│ Raw Brain Signals (Elliott, Wyckoff, Momentum, etc.)    │
└──────────────────────┬──────────────────────────────────┘
                       │
            ┌──────────▼──────────┐
            │ Supervised.py       │ (Binary classifier)
            │ (predict_proba)     │
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │ Calibrator.py       │ (Platt/Isotonic)
            │ (calibrate probas)  │
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │ Ensemble.py         │ (3-model voting)
            │ (disagreement_score)│
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │ Conformal.py        │ (prediction sets)
            │ (is_ambiguous?)     │
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │ UncertaintyGate.py  │ (ALLOW/HOLD)
            │ (final filter)      │
            └──────────┬──────────┘
                       │
                  DECISION
```

### Database Tables

**L2 Tables** (new in this level):

| Table | Purpose |
|-------|---------|
| `symbols_config` | Asset configuration (SINGLE/MULTI mode, symbols list) |
| `symbol_health` | Per-symbol health checks (spread, latency, volatility) |
| `symbol_selection_log` | Which symbols were selected (round-robin, auto-select) |
| `model_calibration` | Calibrator coefficients and metrics per brain |
| `ensemble_metrics` | Per-prediction ensemble metrics (disagreement, std) |
| `gate_events` | When gate blocks a trade (reason, thresholds) |
| `calibration_reports` | Daily/weekly calibration quality (ECE, Brier score) |

---

## Configuration

### Settings

Add to `.env` or `settings.py`:

```ini
# === SYMBOL CONFIGURATION ===
PRIMARY_SYMBOL=WIN$N
SYMBOLS=WIN$N,WINM21,WINN21  # Comma-separated for MULTI mode
SYMBOL_MODE=SINGLE            # SINGLE or MULTI
SYMBOL_VALIDATE_ON_START=true # Validate in MT5 at startup
SYMBOL_AUTO_SELECT=true       # Auto-select best symbols in MULTI mode
SYMBOL_AUTO_SELECT_METHOD=LIQUIDITY  # LIQUIDITY, SPREAD, or VOLATILITY
MAX_ACTIVE_SYMBOLS=3

# === PROBABILITY CALIBRATION ===
CALIBRATION_ENABLED=true
CALIBRATION_METHOD=PLATT      # PLATT, ISOTONIC, or NONE
CALIBRATION_TRAIN_SIZE=500    # Samples to fit calibrator

# === ENSEMBLE VOTING ===
ENSEMBLE_ENABLED=true
ENSEMBLE_MODELS=LogisticRegression,RandomForest,GradientBoosting
ENSEMBLE_VOTING=SOFT          # SOFT (average) or WEIGHTED
ENSEMBLE_WEIGHTS=0.33,0.33,0.34  # Only for WEIGHTED mode

# === CONFORMAL PREDICTION ===
CONFORMAL_ENABLED=true
CONFORMAL_ALPHA=0.1           # Significance level (10% = 90% coverage)

# === UNCERTAINTY GATES ===
UNCERTAINTY_GATE_ENABLED=true
MAX_MODEL_DISAGREEMENT=0.25   # Max ensemble disagreement_score
MAX_PROBA_STD=0.15            # Max std dev of probabilities
MIN_GLOBAL_CONFIDENCE=0.55    # Min max(P(0), P(1))
```

### Configuration Modes

#### SINGLE Asset (Backward Compatible)

```python
PRIMARY_SYMBOL = "WIN$N"
SYMBOL_MODE = "SINGLE"
SYMBOL_VALIDATE_ON_START = false  # Existing asset, no validation needed
```

Trade one fixed asset. **Fully backward compatible** with V1-V5-L1.

#### MULTI Asset with Round-Robin

```python
SYMBOLS = "WIN$N,WINM21,WINN21"
SYMBOL_MODE = "MULTI"
SYMBOL_AUTO_SELECT = false      # Fixed rotation
```

Trade each symbol in turn. SymbolManager cycles through list.

#### MULTI Asset with Auto-Select

```python
SYMBOLS = "WIN$N,WINM21,WINN21,WINQ21,WINZ21"
SYMBOL_MODE = "MULTI"
SYMBOL_AUTO_SELECT = true
SYMBOL_AUTO_SELECT_METHOD = "LIQUIDITY"  # or SPREAD, VOLATILITY
MAX_ACTIVE_SYMBOLS = 3
```

SymbolManager selects best 3 symbols by:
- **LIQUIDITY**: Highest tick volume (most active)
- **SPREAD**: Lowest bid-ask spread (tightest)
- **VOLATILITY**: Moderate volatility (0.01 ±50%)

---

## Components in Detail

### 1. Symbol Manager

**File**: `src/mt5/symbol_manager.py`

Unified asset management for single and multiple symbols.

#### Classes

```python
@dataclass
class SymbolInfo:
    """Symbol metadata."""
    symbol: str
    spread: float
    digits: int
    volume_min: float
    volume_max: float
    volatility: float

@dataclass
class SymbolHealth:
    """Symbol health check."""
    symbol: str
    ok: bool
    spread: float
    latency_ms: float
    tick_volume: float
    volatility: float
    error: Optional[str]

class SymbolManager:
    """Main symbol orchestrator."""
    pass
```

#### Methods

```python
# Get active symbols to trade
active = symbol_manager.get_active_symbols()  # List[str]

# Get current symbol (SINGLE mode or current in rotation)
current = symbol_manager.get_current_symbol()  # str

# Update health metrics
symbol_manager.update_symbol_health(
    symbol="WIN$N",
    ok=True,
    spread=0.5,
    latency_ms=15.3,
    tick_volume=1000,
    volatility=0.015
)

# Check all healthy
all_ok = symbol_manager.all_healthy()  # bool
```

#### Usage in Runner

```python
from src.mt5.symbol_manager import SymbolManager

symbol_manager = SymbolManager.load_from_config(settings)

# Main loop
while running:
    for symbol in symbol_manager.get_active_symbols():
        # Process symbol
        features = get_features(symbol)
        signals = brains.predict(features)
        # ...
        
        # Update health
        symbol_manager.update_symbol_health(symbol, ok=True, ...)
```

---

### 2. Probability Calibration

**File**: `src/models/calibrator_l2.py`

Transform raw probabilities to match actual frequencies.

#### Why Calibrate?

Raw classifier probabilities often don't match actual frequencies:
- **Overconfident**: P(positive) = 0.9 but actual frequency = 0.6
- **Underconfident**: P(positive) = 0.4 but actual frequency = 0.6

**Calibrated probabilities**: More reliable for risk management.

#### Methods

**Platt Scaling** (default)
```
P_calibrated = 1 / (1 + exp(A * P_raw + B))
```
Fits sigmoid curve to raw probabilities. Fast, works well for most cases.

**Isotonic Regression**
```
P_calibrated = isotonic_regression(P_raw)
```
Non-parametric mapping. More flexible but requires more data.

#### Usage

```python
from src.models.calibrator_l2 import ProbabilityCalibrator

# Create and fit calibrator
calibrator = ProbabilityCalibrator(method="PLATT")
calibrator.fit(y_true_cal, y_proba_cal)  # Calibration set

# Transform probabilities
y_proba_raw = model.predict_proba(X_test)  # [0.9, 0.1]
y_proba_cal = calibrator.transform(y_proba_raw)  # [0.85, 0.15]

# Get reliability metrics
ece = calibrator.get_reliability_metrics()
# {
#     "expected_calibration_error": 0.025,
#     "max_calibration_error": 0.15,
#     "brier_score": 0.08,
#     "reliability_diagram": {...}
# }
```

#### Calibration Error Metrics

| Metric | Interpretation |
|--------|---|
| **ECE** (Expected Calibration Error) | Avg difference between predicted and actual frequency. Lower is better. |
| **MCE** (Max Calibration Error) | Max difference. Should be < 0.1. |
| **Brier Score** | Mean squared error of probabilities. Lower is better (0-1 range). |

---

### 3. Lightweight Ensemble

**File**: `src/models/ensemble.py`

Combine 3 models with soft or weighted voting.

#### Models

1. **LogisticRegression**: Fast, interpretable, baseline
2. **RandomForest** (50 trees, max_depth=10): Robust to outliers
3. **GradientBoosting** (50 trees, max_depth=5): High accuracy

#### Voting Strategies

**SOFT** (default) - Average probabilities
```
P_ensemble = (P_lr + P_rf + P_gb) / 3
proba_std = std([P_lr, P_rf, P_gb])
disagreement_score = proba_std / 0.5  # Normalized to [0, 1]
```

**WEIGHTED** - Weighted by recent accuracy
```
weights = [accuracy_lr, accuracy_rf, accuracy_gb]
weights = weights / sum(weights)
P_ensemble = weights @ [P_lr, P_rf, P_gb]
```

#### Usage

```python
from src.models.ensemble import LightweightEnsemble, EnsembleMetrics

# Create and fit ensemble
ensemble = LightweightEnsemble(voting="SOFT")
ensemble.fit(X_train, y_train)

# Predict with metrics
X_test = np.array([[...], [...]])
metrics = ensemble.predict_with_metrics(X_test)

# metrics = [
#     EnsembleMetrics(
#         prediction=1,
#         proba_mean=0.75,
#         proba_std=0.08,
#         disagreement_score=0.16,
#         individual_probas={"lr": 0.72, "rf": 0.78, "gb": 0.75},
#         votes={"lr": 1, "rf": 1, "gb": 1}
#     ),
#     ...
# ]
```

#### Interpreting Disagreement

| disagreement_score | Interpretation |
|---|---|
| 0.0 - 0.1 | Perfect agreement. Very confident. |
| 0.1 - 0.2 | Good agreement. Confident. |
| 0.2 - 0.3 | Moderate disagreement. Watch. |
| > 0.3 | High disagreement. Likely GATE blocks. |

---

### 4. Conformal Prediction

**File**: `src/models/conformal.py`

Quantify uncertainty with prediction sets and coverage guarantees.

#### Concepts

**Nonconformity Measure**
```
nonconformity = 1 - P_calibrated(true_class)
```
High = far from confident prediction. Low = very confident.

**Prediction Set**
- **Singleton** {1}: System is confident. Include only most likely class.
- **Doubleton** {0, 1}: System is uncertain. Both classes possible.

**Coverage Guarantee**
- If alpha=0.1 (10% error), true class will be in prediction_set ≥90% of the time.
- Conservative: favors including more classes.

#### Usage

```python
from src.models.conformal import ConformalPredictor

# Create predictor
cp = ConformalPredictor(alpha=0.1, calibrator=my_calibrator)

# Fit on calibration set
cp.set_threshold_from_calibration(y_cal, y_proba_cal)

# Predict with sets
results = cp.predict_with_set(y_proba_test)

# results = [
#     ConformalResult(
#         predicted_class=1,
#         prediction_set={1},          # Singleton = confident
#         confidence=0.90,
#         is_ambiguous=False
#     ),
#     ConformalResult(
#         predicted_class=1,
#         prediction_set={0, 1},       # Doubleton = uncertain
#         confidence=0.45,
#         is_ambiguous=True
#     ),
#     ...
# ]
```

#### Decision Logic

| Scenario | Prediction Set | Confidence | Gate Decision |
|---|---|---|---|
| High confidence buy | {1} | 0.90 | Allow |
| Uncertain | {0, 1} | 0.45 | **BLOCK** (ambiguous) |
| High confidence sell | {0} | 0.90 | Allow |

---

### 5. Uncertainty Gate

**File**: `src/brains/uncertainty_gate.py`

Risk management layer that blocks trades when uncertainty is high.

#### Blocking Conditions

Gate returns `HOLD` if **any** of these:

1. **Ensemble Disagreement** > 0.25
   ```
   disagreement_score = proba_std / 0.5
   ```

2. **Conformal Ambiguity**
   ```
   prediction_set == {0, 1}  # Both classes possible
   ```

3. **Probability Std Dev** > 0.15
   ```
   proba_std = std(model probabilities)
   ```

4. **Global Confidence** < 0.55
   ```
   global_confidence = max(P(0), P(1))
   ```

#### Usage

```python
from src.brains.uncertainty_gate import UncertaintyGate

# Create gate
gate = UncertaintyGate(
    enabled=True,
    max_model_disagreement=0.25,
    max_proba_std=0.15,
    min_global_confidence=0.55
)

# Check before trading
decision = gate.check(
    ensemble_metrics=ensemble_result,
    conformal_result=conformal_result
)

if decision.decision == "HOLD":
    logger.info(f"Gate blocked: {decision.reason}")
    return "HOLD"
else:
    return ensemble_result.prediction  # BUY or SELL
```

#### Integration Point

In `src/brains/meta_brain.py`:

```python
def get_signal(self, features):
    # Get ensemble prediction
    ensemble_metrics = self.ensemble.predict_with_metrics(features)
    
    # Get conformal prediction set
    conformal_result = self.conformal.predict_with_set(
        ensemble_metrics.proba_mean
    )
    
    # Apply uncertainty gate
    gate_decision = self.gate.check(
        ensemble_metrics=ensemble_metrics,
        conformal_result=conformal_result
    )
    
    if gate_decision.decision == "HOLD":
        return "HOLD"
    
    # Return ensemble prediction
    return "BUY" if ensemble_metrics.prediction == 1 else "SELL"
```

---

## Tuning Guide

### When to Increase/Decrease Thresholds

#### Disagreement Threshold

Increase (0.25 → 0.35) if:
- Too many gates blocking (too conservative)
- Models tend to disagree in valid scenarios

Decrease (0.25 → 0.15) if:
- Taking too many losing trades from disagreement
- Want stricter consensus

#### Confidence Threshold

Increase (0.55 → 0.65) if:
- Win rate is low (many close calls)
- Want to trade only very high conviction

Decrease (0.55 → 0.52) if:
- Too few trades (missing opportunities)
- Models are well-calibrated

#### Proba Std Threshold

Similar to disagreement. Represents spread of model probabilities.

#### Conformal Alpha

- Alpha=0.05 → 95% coverage (more conservative, blocks more)
- Alpha=0.10 → 90% coverage (balanced, default)
- Alpha=0.20 → 80% coverage (aggressive, fewer blocks)

### Performance Trade-offs

| Tuning | Effect |
|--------|--------|
| **Stricter gates** | Fewer trades, higher win %, lower drawdown |
| **Relaxed gates** | More trades, potentially lower win %, higher drawdown |
| **Better calibration** | More reliable probabilities, smoother equity curve |
| **More ensemble models** | Slower but more robust (currently 3 is optimal) |

---

## Workflow Examples

### Single Asset, Conservative

```ini
SYMBOL_MODE=SINGLE
PRIMARY_SYMBOL=WIN$N
CALIBRATION_ENABLED=true
CALIBRATION_METHOD=PLATT
ENSEMBLE_ENABLED=true
ENSEMBLE_VOTING=SOFT
UNCERTAINTY_GATE_ENABLED=true
MAX_MODEL_DISAGREEMENT=0.20  # Stricter
MAX_PROBA_STD=0.12
MIN_GLOBAL_CONFIDENCE=0.60   # Higher
CONFORMAL_ALPHA=0.05         # 95% coverage
```

→ Very high conviction trades only. Fewer trades, higher win rate expected.

### Multi-Asset, Balanced

```ini
SYMBOL_MODE=MULTI
SYMBOLS=WIN$N,WINM21,WINN21
SYMBOL_AUTO_SELECT=true
SYMBOL_AUTO_SELECT_METHOD=LIQUIDITY
MAX_ACTIVE_SYMBOLS=2
CALIBRATION_ENABLED=true
ENSEMBLE_ENABLED=true
UNCERTAINTY_GATE_ENABLED=true
MAX_MODEL_DISAGREEMENT=0.25  # Default
MAX_PROBA_STD=0.15
MIN_GLOBAL_CONFIDENCE=0.55
CONFORMAL_ALPHA=0.10         # 90% coverage
```

→ Trade 2 most liquid symbols. More volume, balanced risk/reward.

### High-Volume Aggressive

```ini
SYMBOL_MODE=MULTI
SYMBOL_AUTO_SELECT=true
SYMBOL_AUTO_SELECT_METHOD=LIQUIDITY
MAX_ACTIVE_SYMBOLS=5
CALIBRATION_ENABLED=true
ENSEMBLE_ENABLED=true
UNCERTAINTY_GATE_ENABLED=true
MAX_MODEL_DISAGREEMENT=0.35  # Relaxed
MAX_PROBA_STD=0.20
MIN_GLOBAL_CONFIDENCE=0.52   # Lower
CONFORMAL_ALPHA=0.15         # 85% coverage
```

→ Many symbols, relaxed gates. High volume, accept lower win%.

---

## Diagnostics & Monitoring

### Dashboard Endpoints

New L2 endpoints in `src/dashboard/api.py`:

```python
# GET /symbols/status
{
    "active_symbols": ["WIN$N", "WINM21"],
    "current_symbol": "WIN$N",
    "health_per_symbol": {
        "WIN$N": {"ok": true, "spread": 0.5, "latency_ms": 14.2},
        "WINM21": {"ok": true, "spread": 0.6, "latency_ms": 16.1}
    },
    "mode": "MULTI"
}

# GET /ensemble/status
{
    "enabled": true,
    "models": ["LogisticRegression", "RandomForest", "GradientBoosting"],
    "voting": "SOFT",
    "last_metrics": {
        "disagreement_score": 0.18,
        "proba_std": 0.08,
        "individual_probas": {"lr": 0.72, "rf": 0.75, "gb": 0.76}
    }
}

# GET /performance/confidence_buckets
{
    "buckets": [
        {"confidence": "0.50-0.60", "trades": 12, "win_rate": 0.42},
        {"confidence": "0.60-0.70", "trades": 28, "win_rate": 0.57},
        {"confidence": "0.70-0.80", "trades": 35, "win_rate": 0.71},
        {"confidence": "0.80-1.00", "trades": 18, "win_rate": 0.89}
    ],
    "reliability_diagram": {...}
}
```

### Logs

Gate blocking events:
```
[WARNING] Gate BLOCKED: ensemble disagreement 0.32 > 0.25
[WARNING] Gate BLOCKED: conformal prediction ambiguous (set={0, 1})
[WARNING] Gate BLOCKED: proba_std 0.18 > 0.15
[WARNING] Gate BLOCKED: global confidence 0.51 < 0.55
```

Calibration quality:
```
[INFO] ConformalPredictor threshold=0.35 from 500 calibration samples (alpha=0.1, coverage=90%)
[INFO] ProbabilityCalibrator ECE=0.023, MCE=0.08 (PLATT)
```

---

## Backward Compatibility

**Level 2 is 100% backward compatible with V1-V5-L1.**

Default configuration:
```ini
SYMBOL_MODE=SINGLE
CALIBRATION_ENABLED=false
ENSEMBLE_ENABLED=false
UNCERTAINTY_GATE_ENABLED=false
CONFORMAL_ENABLED=false
```

Old code works unchanged. Enable L2 features selectively.

---

## Testing

Run L2 test suite:

```bash
pytest tests/test_conformal.py -v
pytest tests/test_uncertainty_gate.py -v
pytest tests/test_ensemble.py -v
pytest tests/test_calibration_platt_isotonic.py -v
pytest tests/test_symbol_manager.py -v
```

---

## Summary

| Feature | Benefit | Trade-off |
|---------|---------|-----------|
| **Calibration** | More reliable probabilities | Small accuracy drop (~1-2%) |
| **Ensemble** | Robustness, disagreement detection | Slower predictions |
| **Conformal** | Uncertainty quantification | Overhead minimal |
| **Gates** | Avoid low-conviction trades | Fewer trades |
| **Symbol Manager** | Multi-asset flexibility | Added complexity in MULTI mode |

**Best For**:
- Traders wanting explicit confidence measures
- Systems with multiple assets to trade
- Risk-averse portfolios (prefer quality over quantity)
- Environments with regime changes (gates adapt)

---

## Next Steps (Level 3)

Future enhancements planned:
- Adaptive gates (adjust thresholds by market regime)
- Online calibration (update as new data arrives)
- Per-brain confidence scores
- Ensemble model selection (choose best subset)
- Confidence-based position sizing

---

*See `.env.example` for all L2 configuration parameters.*
