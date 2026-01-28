# Level 1 Quick Reference

## 🚀 Instant Usage

### Cost Model
```python
from src.costs import CostModel

# Create model
model = CostModel(
    mode="POR_HORARIO",
    spread_base=1.0,
    slippage_base=0.5
)

# Get costs for a trade
spread, slip, comm = model.get_costs(
    symbol="EURUSD",
    hour=14,
    atr=0.0045,
    volatility=1.2
)

# Use in fill: entry_price + spread, exit at bid (exit_price - spread)
entry_slipped = entry + (spread + slip) * 0.0001
```

### Bad Day Filter
```python
from src.live import BadDayFilter

filter = BadDayFilter(
    enabled=True,
    first_n_trades=5,
    max_daily_loss=-100.0,
    min_winrate=0.40
)

paused, reason = filter.check(trade_pnl=-50.0)
if paused:
    print(f"PAUSE: {reason}")  # e.g., "LOSS_LIMIT:-120.5"
```

### Time Filter
```python
from src.live import TimeFilter

filter = TimeFilter(
    enabled=True,
    blocked_windows=["09:00-09:15", "17:50-18:10"]
)

if filter.is_blocked(datetime.utcnow()):
    skip_trading = True
```

### Label Generation
```python
from src.training.dataset import LabelGenerator

gen = LabelGenerator(
    horizons=[5, 10, 20],
    mfe_weight=1.0,
    mae_weight=0.5
)

labels = gen.generate_labels(
    trades=[{"side": "BUY", "entry_price": 1.0500, "tp1": 1.0600, ...}],
    candles=[{"timestamp": ..., "o": ..., "h": ..., "l": ..., "c": ...}],
    symbol="EURUSD"
)

# Access multi-horizon results
for label in labels:
    print(f"5-candle: TP1={label.tp1_hit[5]}, MFE={label.mfe[5]}, Quality={label.quality_score[5]}")
```

### Walk-Forward with Anti-Leak
```python
from src.backtest.walk_forward import split_walk_forward

for train, test in split_walk_forward(
    df,
    train_size=1000,
    test_size=250,
    purge_candles=50,
    embargo_candles=50
):
    model.fit(train)
    metrics = model.evaluate(test)  # No lookahead bias!
```

## ⚙️ Configuration Quick Start

### Minimal .env (Safe Defaults)
```ini
# Anti-leak (backtest)
WF_PURGE_CANDLES=50
WF_EMBARGO_CANDLES=50

# Realistic costs (backtest)
COST_MODE=FIXO
COST_SPREAD_BASE=1.0
COST_SLIPPAGE_BASE=0.5

# Filters (disabled by default)
BAD_DAY_ENABLED=false
TIME_FILTER_ENABLED=false

# Training labels
LABEL_HORIZONS=5,10,20
```

### Production .env (Recommended)
```ini
# Anti-leak
WF_PURGE_CANDLES=50
WF_EMBARGO_CANDLES=50

# Realistic costs
COST_MODE=POR_HORARIO
COST_SPREAD_BASE=1.0
COST_SLIPPAGE_BASE=0.5
COST_SLIPPAGE_MAX=2.0
COST_COMMISSION=0.0

# Smart filters
BAD_DAY_ENABLED=true
BAD_DAY_FIRST_N_TRADES=5
BAD_DAY_MAX_LOSS=-100.0
BAD_DAY_MIN_WINRATE=0.40
BAD_DAY_CONSECUTIVE_MAX=3

TIME_FILTER_ENABLED=true
TIME_FILTER_BLOCKED_WINDOWS=09:00-09:15,17:50-18:10,22:00-23:00

# Training
LABEL_HORIZONS=5,10,20
LABEL_MFE_WEIGHT=1.0
LABEL_MAE_WEIGHT=0.5
```

## 📊 Database Quick Reference

### Tables Added
| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `wf_splits` | Walk-forward tracking | run_id, split_id, purge_candles, embargo_candles |
| `cost_events` | Cost history | timestamp, mode, spread, slippage, volatility |
| `bad_day_events` | Pause events | timestamp, reason, daily_pnl, paused_until |
| `time_filter_hits` | Filter triggers | timestamp, action (BLOCKED/ALLOWED), window |
| `labels` | Training labels | timestamp, horizon, tp1_hit, mfe, mae, quality_score |
| `report_insights` | Performance analysis | report_date, insight_type, metric_name, metric_value |

### Query Examples
```python
from src.db.repo import (
    insert_cost_event, insert_bad_day_event,
    get_performance_by_hour, get_performance_by_regime
)

# Log costs
insert_cost_event(
    timestamp=time.time(),
    symbol="EURUSD",
    mode="POR_HORARIO",
    spread=1.0,
    slip=0.5,
    comm=0.0,
    vol=1.2,
    details="{"
)

# Get hourly performance
hourly_perf = get_performance_by_hour("EURUSD", days=7)
# Returns: [(9, 10, 0.80, 2.5), (14, 25, 0.92, 3.1), ...]
#          (hour, trade_count, win_rate, profit_factor)

# Get regime performance
regime_perf = get_performance_by_regime("EURUSD", days=7)
```

## 🧪 Testing Quick Commands

```bash
# Test everything
pytest tests/test_cost_model.py tests/test_bad_day_filter.py tests/test_time_filter.py tests/test_labels_multi_horizon.py tests/test_walk_forward_purge_embargo.py -v

# Test specific component
pytest tests/test_walk_forward_purge_embargo.py::test_walk_forward_purge -v

# Run with output
pytest tests/test_bad_day_filter.py -v -s
```

## 📦 Module Imports

```python
# Cost model
from src.costs import CostModel, CostSnapshot

# Live filters
from src.live import BadDayFilter, TimeFilter, DailyStats

# Training
from src.training.dataset import LabelGenerator, TradeLabel

# Walk-forward
from src.backtest.walk_forward import split_walk_forward

# Config
from src.config import settings
print(f"COST_MODE={settings.cost_mode}")
print(f"BAD_DAY_MAX_LOSS={settings.bad_day_max_loss}")
```

## 🎯 Common Patterns

### Backtest with L1
```python
from src.backtest.walk_forward import split_walk_forward
from src.costs import CostModel
from src.training.dataset import LabelGenerator

cost_model = CostModel(mode=settings.cost_mode, ...)
label_gen = LabelGenerator(horizons=settings.label_horizons)

for train, test in split_walk_forward(
    df, 1000, 250,
    purge_candles=settings.wf_purge_candles,
    embargo_candles=settings.wf_embargo_candles
):
    # Train
    model.fit(train)
    
    # Test (with realistic costs)
    predictions = model.predict(test)
    
    # Generate labels for next iteration
    labels = label_gen.generate_labels(trades, test, "EURUSD")
```

### Live Trading with Filters
```python
from src.live import BadDayFilter, TimeFilter

bad_day = BadDayFilter(
    enabled=settings.bad_day_enabled,
    max_daily_loss=settings.bad_day_max_loss
)
time_filter = TimeFilter(
    enabled=settings.time_filter_enabled,
    blocked_windows=settings.time_filter_blocked_windows.split(",")
)

while running:
    # Check filters
    if time_filter.is_blocked(datetime.utcnow()):
        continue
    
    # Trade
    signal = brain.decide(features)
    trade = execute(signal)
    
    # Update bad day filter
    paused, reason = bad_day.check(trade.pnl, datetime.utcnow())
    if paused:
        break
```

### Training with Multi-Horizon Labels
```python
from src.training.dataset import LabelGenerator

gen = LabelGenerator(
    horizons=[5, 10, 20],
    mfe_weight=1.0,
    mae_weight=0.5
)

# Generate labels
labels = gen.generate_labels(trades, candles, "EURUSD")

# Train per horizon
for horizon in [5, 10, 20]:
    X = features
    y = [label.quality_score[horizon] for label in labels]
    
    model.fit(X, y)
    
    # Statistics
    stats = gen.get_stats(labels, horizon)
    print(f"H{horizon}: TP1_rate={stats['tp1_hit_rate']:.2%}, Qual={stats['avg_quality']:.2f}")
```

## 🔍 Debugging

### Check Filter Status
```python
from src.live import BadDayFilter, TimeFilter

bad_day = BadDayFilter(...)
time_filter = TimeFilter(...)

# Get current state
stats = bad_day.get_stats()
print(f"Trades: {stats.trades_count}, PnL: {stats.pnl:.2f}, Paused: {stats.paused}")

# Get windows
windows = time_filter.get_blocked_windows()
print(f"Blocked: {windows}")
```

### Verify Database
```python
import sqlite3
conn = sqlite3.connect("data/db/trading.db")
cursor = conn.cursor()

# Check L1 tables
cursor.execute("SELECT COUNT(*) FROM cost_events")
print(f"Cost events: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM labels")
print(f"Labels: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM bad_day_events")
print(f"Bad day events: {cursor.fetchone()[0]}")
```

### Check Configuration
```python
from src.config import settings

print(f"=== L1 Configuration ===")
print(f"Anti-Leak: purge={settings.wf_purge_candles}, embargo={settings.wf_embargo_candles}")
print(f"Cost Mode: {settings.cost_mode}")
print(f"Bad Day Filter: {settings.bad_day_enabled}")
print(f"Time Filter: {settings.time_filter_enabled}")
print(f"Label Horizons: {settings.label_horizons}")
```

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| Purge/embargo not working | Check `WF_PURGE_CANDLES` and `WF_EMBARGO_CANDLES` settings |
| CostModel returns None | Ensure `data/config/spread_by_hour.json` exists for POR_HORARIO mode |
| BadDayFilter always paused | Verify `BAD_DAY_MAX_LOSS` is negative (e.g., -100.0) |
| TimeFilter blocking all trades | Check `TIME_FILTER_BLOCKED_WINDOWS` format: "HH:MM-HH:MM" |
| Labels not generated | Ensure trade and candle timestamps match |
| Database schema error | Run `python -m src.db.schema` to recreate tables |

## 📚 Files to Know

| File | Purpose |
|------|---------|
| `src/costs/cost_model.py` | Cost modeling (3 modes) |
| `src/live/bad_day_filter.py` | Bad day detection |
| `src/live/time_filter.py` | Time-based blocking |
| `src/training/dataset.py` | Label generation |
| `src/backtest/walk_forward.py` | Anti-leak splits |
| `src/config/settings.py` | L1 configuration |
| `src/db/schema.py` | Database schema (6 new tables) |
| `tests/test_*.py` | 30+ unit tests |
| `LEVEL1.md` | Complete documentation |
| `PHASE2_INTEGRATION_GUIDE.md` | Integration checklist |

---

**Quick Links**:
- 📖 Full docs: `LEVEL1.md`
- 🔗 Integration: `PHASE2_INTEGRATION_GUIDE.md`
- ✅ Status: `IMPLEMENTATION_L1_PHASE1.md`
- 🧪 Tests: `tests/test_*.py`
