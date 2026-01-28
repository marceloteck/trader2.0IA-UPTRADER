# Level 1 Phase 2 Integration Guide

## Overview
Phase 1 created 6 new L1 modules. Phase 2 integrates them into existing components.

## Integration Checklist

### 1. fill_model.py Integration
**File**: `src/execution/fill_model.py` (V4 component)
**Goal**: Use CostModel instead of fixed spread/slippage

```python
# Current (pseudo):
spread = settings.spread_max
slippage = settings.slippage

# New:
from src.costs import CostModel
cost_model = CostModel(
    mode=settings.cost_mode,
    spread_base=settings.cost_spread_base,
    slippage_base=settings.cost_slippage_base,
    slippage_max=settings.cost_slippage_max,
    commission=settings.cost_commission
)

spread, slip, comm = cost_model.get_costs(symbol, hour=now.hour, atr=atr_value)
```

**Files to Update**:
- [ ] `src/execution/fill_model.py` - integrate CostModel

---

### 2. Reports Enhancement
**Files**: `src/reports/daily_report.py`, `src/reports/weekly_report.py` (V5)
**Goal**: Add regime/hour performance breakdown

**What to add**:
- Performance by regime (trending, ranging, volatile)
- Performance by hour (heatmap)
- Brain contribution analysis
- Suggested windows to block

```python
# In daily_report.py:
def add_performance_by_hour(trades, symbol):
    """Create hourly performance heatmap."""
    # Group trades by hour
    # Calculate: win%, PF, DD, pnl
    # Store in report_insights table

def add_performance_by_regime(trades, regimes):
    """Performance breakdown per regime."""
    # Filter by regime
    # Calculate metrics
    # Identify worst regimes

def add_suggested_blocks(trades):
    """Suggest windows to block based on performance."""
    # Find windows with PF < 1.0 and high DD
    # Suggest for TIME_FILTER_BLOCKED_WINDOWS
```

**Files to Update**:
- [ ] `src/reports/daily_report.py` - add hourly/regime breakdowns
- [ ] `src/reports/weekly_report.py` - add insights section

---

### 3. Supervised Training (Multi-Horizon)
**File**: `src/models/supervised.py` (V4)
**Goal**: Train with multi-horizon labels

```python
# src/training/dataset.py
from src.training.dataset import LabelGenerator

label_gen = LabelGenerator(
    horizons=settings.label_horizons,  # [5, 10, 20]
    mfe_weight=settings.label_mfe_weight,
    mae_weight=settings.label_mae_weight
)

labels = label_gen.generate_labels(trades, candles, symbol)

# Train model for each horizon
for horizon in settings.label_horizons:
    # Model predicts: prob_tp1[horizon], prob_tp2[horizon], expected_quality[horizon]
    train_by_horizon(labels, horizon)
```

**Files to Update**:
- [ ] `src/models/supervised.py` - add multi-horizon training

---

### 4. MetaBrain Penalties
**File**: `src/brains/meta_brain.py` (V3)
**Goal**: Adjust brain weights by hour/regime performance

```python
def apply_hour_penalty(brain_signals, current_hour):
    """Reduce weights during bad hours."""
    # Query bad_day_events table for hour
    # Calculate penalty factor (0.0 to 1.0)
    # Reduce brain scores: score *= penalty

def apply_regime_penalty(brain_signals, current_regime):
    """Reduce weights during poor regimes."""
    # Query report_insights for regime performance
    # Apply penalty if PF < 1.0
    # Reduce brain scores
```

**Files to Update**:
- [ ] `src/brains/meta_brain.py` - add hour/regime penalties

---

### 5. Dashboard Updates
**File**: `src/dashboard/api.py` (V5)
**Goal**: Add filter status and performance endpoints

```python
# New endpoints:
@app.get("/filters/status")
def get_filter_status():
    """Current filter state."""
    return {
        "bad_day_paused": filter.paused_until,
        "paused_reason": filter.last_pause_reason,
        "blocked_windows": time_filter.get_blocked_windows()
    }

@app.get("/performance/by_hour")
def performance_by_hour():
    """Hourly performance heatmap."""
    # Query report_insights table
    # Return matrix: [hour][metric]

@app.get("/performance/by_regime")
def performance_by_regime():
    """Regime-wise performance."""
    # Query report_insights
    # Return regime metrics
```

**Files to Update**:
- [ ] `src/dashboard/api.py` - add filter/performance endpoints

---

### 6. Live Runner Integration
**File**: `src/live/runner.py` (V4)
**Goal**: Apply filters in execution loop

```python
# Pseudo-code for runner.py:
from src.live import BadDayFilter, TimeFilter

bad_day_filter = BadDayFilter(
    enabled=settings.bad_day_enabled,
    first_n_trades=settings.bad_day_first_n_trades,
    max_daily_loss=settings.bad_day_max_loss,
    min_winrate=settings.bad_day_min_winrate,
    consecutive_losses_max=settings.bad_day_consecutive_max
)

time_filter = TimeFilter(
    enabled=settings.time_filter_enabled,
    blocked_windows=settings.time_filter_blocked_windows.split(","),
    allow_only_windows=settings.time_filter_allow_only.split(",") if settings.time_filter_allow_only else None
)

while trading_active:
    now = datetime.utcnow()
    
    # Check time filter first
    if time_filter.is_blocked(now):
        logger.info("Time filter: window blocked")
        continue
    
    # Get signal
    signal = meta_brain.decide(...)
    
    if signal.action != "HOLD":
        trade = execute(signal)
        
        # Check bad day filter after trade
        paused, reason = bad_day_filter.check(
            trade_pnl=trade.pnl,
            timestamp=now
        )
        
        if paused:
            logger.warning(f"Bad day filter: {reason}")
            # Update status in database
```

**Files to Update**:
- [ ] `src/live/runner.py` - integrate filters

---

## Database Queries Needed

### repo.py additions
```python
def insert_cost_event(timestamp, symbol, mode, spread, slip, comm, vol, details):
    """Record cost for learning."""
    query = """INSERT INTO cost_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
    execute(query, (timestamp, symbol, mode, spread, slip, comm, vol, details))

def insert_bad_day_event(timestamp, reason, pnl, trades, consec, paused_until, details):
    """Record bad day pause."""
    query = """INSERT INTO bad_day_events VALUES (?, ?, ?, ?, ?, ?, ?)"""
    execute(query, (timestamp, reason, pnl, trades, consec, paused_until, details))

def insert_labels(labels_list):
    """Bulk insert training labels."""
    for label in labels_list:
        query = """INSERT INTO labels VALUES (...)"""
        execute(query, label_values)

def get_performance_by_hour(symbol, days=7):
    """Get hourly performance metrics."""
    query = """SELECT HOUR(...), COUNT(*), WIN_RATE, PF FROM labels
               WHERE symbol = ? AND timestamp > datetime('now', '-7 days')
               GROUP BY HOUR(timestamp)"""
    return query_all(query, (symbol,))

def get_performance_by_regime(symbol, days=7):
    """Get regime performance metrics."""
    query = """SELECT regime, COUNT(*), WIN_RATE, PF FROM ...
               GROUP BY regime"""
    return query_all(query, (symbol,))
```

**Files to Update**:
- [ ] `src/db/repo.py` - add L1 query methods

---

## Execution Order

1. **fill_model.py** - Cost model integration (foundational)
2. **repo.py** - Database queries for L1
3. **supervised.py** - Multi-horizon training
4. **reports** - Regime/hour analysis
5. **meta_brain.py** - Hour/regime penalties
6. **dashboard/api.py** - New endpoints
7. **live/runner.py** - Filter application

---

## Testing Each Integration

```bash
# After each file update, run:
python -m pytest tests/test_*.py -v

# Specifically for integration:
python -m src.main backtest --from 2024-01-01 --to 2024-02-01
python -m src.main train --replay 3
python -m src.main live-sim --duration 24h
```

---

## Configuration Management

### .env Updates Needed
```ini
# Already in Phase 1:
WF_PURGE_CANDLES=50
WF_EMBARGO_CANDLES=50
COST_MODE=FIXO
COST_SPREAD_BASE=1.0
COST_SLIPPAGE_BASE=0.5
COST_SLIPPAGE_MAX=2.0
COST_COMMISSION=0.0
BAD_DAY_ENABLED=true
BAD_DAY_FIRST_N_TRADES=5
BAD_DAY_MAX_LOSS=-100.0
BAD_DAY_MIN_WINRATE=0.4
BAD_DAY_CONSECUTIVE_MAX=3
TIME_FILTER_ENABLED=false
TIME_FILTER_BLOCKED_WINDOWS=
TIME_FILTER_ALLOW_ONLY=
LABEL_HORIZONS=5,10,20
LABEL_MFE_WEIGHT=1.0
LABEL_MAE_WEIGHT=0.5

# Data files:
data/config/spread_by_hour.json  (for POR_HORARIO mode)
```

---

## Success Criteria

✅ Fill model uses CostModel
✅ Reports show hourly/regime breakdowns
✅ Supervised model trains on multi-horizon labels
✅ MetaBrain applies hour/regime penalties
✅ Dashboard shows filter status
✅ Live runner applies filters
✅ All tests pass
✅ Backtest results improve (more realistic)
✅ No breaking changes to V1-V5

---

## Rollback Plan

If issues arise:
1. L1 configs default to "safe" values (COST_MODE=FIXO, filters disabled)
2. Revert any one file without affecting others
3. Database has new tables but doesn't require them
4. All V1-V5 functionality remains unchanged

---

## Estimated Effort

| Task | Effort | Status |
|------|--------|--------|
| fill_model integration | 2-3h | ⏳ Pending |
| Reports enhancement | 3-4h | ⏳ Pending |
| Supervised multi-horizon | 3-4h | ⏳ Pending |
| MetaBrain penalties | 2h | ⏳ Pending |
| Dashboard endpoints | 1-2h | ⏳ Pending |
| Live runner filters | 2h | ⏳ Pending |
| Testing & validation | 2-3h | ⏳ Pending |
| **Total Phase 2** | **15-18h** | ⏳ **Pending** |

---

## Notes for Phase 2

- Phase 1 created all core L1 modules (complete, tested)
- Phase 2 is integration into existing V1-V5 components
- All new L1 features are additive (no breaking changes)
- Can integrate gradually (fill_model → reports → training → live)
- Database schema already updated (6 new tables)
- Tests provide integration examples

---

**Last Updated**: Post Phase 1
**Next Phase**: Phase 2 Integration
**Timeline**: Ready to begin immediately
