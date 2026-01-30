# Level 5 Quick Reference

## Installation & Setup (5 minutes)

### 1. Update `.env` file

```bash
# Add these to your .env file:
OPERATOR_CAPITAL_BRL=10000
MARGIN_PER_CONTRACT_BRL=1000
MAX_CONTRACTS_CAP=10
REALAVANCAGEM_ENABLED=true
REALAVANCAGEM_MAX_EXTRA_CONTRACTS=1
SCALP_TP_POINTS=80
SCALP_SL_POINTS=40
SCALP_MAX_HOLD_SECONDS=180
RL_POLICY_ENABLED=true
RL_UPDATE_BATCH_SIZE=10
```

### 2. Update database

```python
from src.db.schema import ensure_tables
ensure_tables(db_path)  # Creates 6 new L5 tables
```

### 3. Initialize components

```python
from src.config.settings import Settings
from src.execution.capital_manager import CapitalManager
from src.execution.scalp_manager import ScalpManager
from src.execution.rl_gate import RLGate
from src.training.reinforcement_policy import RLPolicy
from src.training.online_update import OnlineUpdater

settings = Settings.load_settings()

capital_mgr = CapitalManager(
    operator_capital_brl=settings.operator_capital_brl,
    margin_per_contract_brl=settings.margin_per_contract_brl,
    max_contracts_cap=settings.max_contracts_cap,
    min_contracts=settings.min_contracts,
    realavancagem_enabled=settings.realavancagem_enabled,
    realavancagem_max_extra_contracts=settings.realavancagem_max_extra_contracts,
    realavancagem_mode=settings.realavancagem_mode,
)

scalp_mgr = ScalpManager(
    scalp_tp_points=settings.scalp_tp_points,
    scalp_sl_points=settings.scalp_sl_points,
    scalp_max_hold_seconds=settings.scalp_max_hold_seconds,
    contract_point_value=settings.contract_point_value,
    protect_profit_after_scalp=settings.protect_profit_after_scalp,
    protect_profit_cooldown_seconds=settings.protect_profit_cooldown_seconds,
)

rl_policy = RLPolicy()
rl_gate = RLGate(settings, settings.db_path, rl_policy, capital_mgr)
updater = OnlineUpdater(batch_size=settings.rl_update_batch_size)
```

---

## Usage in Trading Loop

### Simple Integration (5 lines)

```python
# 1. Get boss decision (existing)
boss_decision = boss.run(candles, context)

# 2. Apply RL gate (NEW)
decision, rl_action, realavanca_ok = rl_gate.apply_gate(
    boss_decision, regime, hour, confidence, disagreement, liquidity, symbol, price
)

# 3. Execute (existing, but now with RL-modified decision)
if decision.action != "HOLD":
    order = execute_order(decision)

# 4. If extra contracts, open scalp (NEW)
if realavanca_ok and extra_contracts > 0:
    scalp_mgr.open_scalp(symbol, side, entry_price, extra_contracts, now)

# 5. Update scalps every bar (NEW)
scalp_mgr.update_scalp(symbol, current_price, current_time)
```

### Full Example

```python
from datetime import datetime

# Trading loop
for bar in market_feed:
    # Original flow
    boss_decision = boss.run(bar.candles, bar.context)
    meta_decision = meta_brain.evaluate(...)
    
    # NEW: Calculate capital allocation
    capital_state = capital_mgr.calc_contracts(
        symbol=bar.symbol,
        regime=bar.regime,
        global_confidence=meta_decision.global_confidence,
        ensemble_disagreement=meta_decision.disagreement,
        liquidity_strength=bar.liquidity_strength,
        daily_profit_brl=calculate_daily_profit(),
    )
    
    # NEW: Apply RL gate
    decision, rl_action, realavanca_ok = rl_gate.apply_gate(
        boss_decision, bar.regime, bar.hour, 
        meta_decision.global_confidence, meta_decision.disagreement,
        bar.liquidity_strength, bar.symbol, bar.close,
    )
    
    # Skip if blocked
    if decision.action == "HOLD":
        continue
    
    # Execute main position
    order = execute_order(decision.symbol, decision.action, decision.size, 
                          decision.entry, decision.sl, decision.tp1)
    
    # NEW: If re-leverage approved, open scalp for extras
    if realavanca_ok and capital_state.extra_contracts > 0:
        scalp_mgr.open_scalp(
            bar.symbol, decision.action, bar.close, 
            capital_state.extra_contracts, datetime.now()
        )
    
    # NEW: Update scalps (every bar)
    scalp_mgr.update_scalp(bar.symbol, bar.close, bar.time)
```

---

## After Trade Closes

```python
def on_trade_closed(trade):
    # Get original state from entry
    state = RLState(regime, time_bucket, confidence, disagreement)
    
    # Add to updater
    updater.add_trade({
        "symbol": trade.symbol,
        "regime": regime,
        "state_hash": state.to_hash(),
        "action": rl_action_taken,
        "pnl": trade.pnl,
        "duration_seconds": (trade.close_time - trade.open_time).total_seconds(),
    })
    
    # If batch ready, update RL
    if updater.should_update():
        # Create snapshot first
        snapshot = updater.create_snapshot(
            regime=regime,
            policy_data=rl_policy.export_policy_table(regime),
            metrics={"batch_pnl": sum([t["pnl"] for t in updater.get_pending_trades()])},
        )
        
        # Update RL policy
        for trade_record in updater.get_pending_trades():
            reward = 0.8 if trade_record["pnl"] > 0 else 0.2
            rl_policy.update_from_trade(
                regime=trade_record["regime"],
                state_hash=trade_record["state_hash"],
                action=trade_record["action"],
                reward=reward,
            )
        
        # Clear buffer
        updater.clear_pending()
```

---

## Configuration Presets

### Conservative (Capital Protection)

```env
OPERATOR_CAPITAL_BRL=5000
MARGIN_PER_CONTRACT_BRL=1000
MAX_CONTRACTS_CAP=5
REALAVANCAGEM_ENABLED=false
RL_POLICY_ENABLED=true
```

→ Maximum 5 contracts, no re-leverage

### Balanced (Recommended)

```env
OPERATOR_CAPITAL_BRL=10000
MARGIN_PER_CONTRACT_BRL=1000
MAX_CONTRACTS_CAP=10
REALAVANCAGEM_ENABLED=true
REALAVANCAGEM_MIN_GLOBAL_CONF=0.70
RL_POLICY_ENABLED=true
```

→ 10 contracts base, 1 extra if conditions met, RL learning

### Aggressive (Growth)

```env
OPERATOR_CAPITAL_BRL=50000
MARGIN_PER_CONTRACT_BRL=500
MAX_CONTRACTS_CAP=20
REALAVANCAGEM_ENABLED=true
REALAVANCAGEM_MIN_GLOBAL_CONF=0.60
RL_POLICY_ENABLED=true
```

→ 20-100 contracts possible, frequent re-leverage

---

## Monitoring

### Capital Status

```python
stats = capital_mgr.export_stats()
print(f"Decisions: {stats['total_decisions']}")
print(f"Avg base: {stats['avg_base_contracts']:.1f}")
print(f"Re-leverage rate: {stats['realavancagem_frequency']:.1%}")
```

### Scalp Status

```python
stats = scalp_mgr.export_stats()
print(f"Total scalps: {stats['total_scalps']}")
print(f"Win rate: {stats['winrate']:.1%}")
print(f"Total PnL: {stats['total_pnl']:.2f}")
print(f"Avg hold: {stats['avg_hold_time_seconds']:.0f}s")
```

### RL Status

```python
stats = rl_policy.export_stats("TREND_UP")
print(f"Regime frozen: {stats['frozen']}")
print(f"Total updates: {stats['total_updates']}")

# Per action
for action in ["HOLD", "ENTER", "ENTER_CONSERVATIVE", "ENTER_WITH_REALAVANCAGEM"]:
    s = rl_policy.get_action_stats("TREND_UP", "example_state", action)
    print(f"  {action}: count={s['count']}, mean={s['mean_value']:.2f}")
```

---

## Common Issues & Fixes

### RL always returns HOLD

**Cause**: Policy not trained yet

**Fix**: 
```python
# Check training count
stats = rl_policy.get_action_stats(regime, state_hash, "ENTER")
if stats["count"] < 5:
    print("Still training RL policy, HOLD is expected")

# Wait for more trades or lower confidence threshold
```

### Contracts seem wrong

**Debug**:
```python
base = capital_mgr.calc_base_contracts()
# Should equal: floor(capital / margin), capped at max

expected = int(10000 / 1000)  # = 10
assert base <= capital_mgr.max_contracts_cap
```

### Scalps not opening

**Check**:
```python
# 1. Re-leverage must be approved
can_realavanca, reason = capital_mgr.can_realavancar(...)
print(f"Approved: {can_realavanca}, Reason: {reason}")

# 2. Must have extra contracts
print(f"Extra contracts: {capital_state.extra_contracts}")

# 3. Must pass RL gate
print(f"RL action: {rl_action}")
```

### Policy degrading

**Action**:
```python
# Check baseline
stats = rl_policy.export_stats(regime)
if stats["frozen"]:
    print("Regime frozen due to poor performance")
    # Unfreeze manually:
    rl_policy.unfreeze_regime(regime)

# Or rollback:
snapshot = updater.get_last_snapshot(regime)
updater.rollback_to_snapshot(snapshot.snapshot_id)
print("Rolled back to previous policy")
```

---

## Testing

```bash
# Run all tests
pytest tests/test_capital_manager.py tests/test_scalp_manager.py \
        tests/test_rl_policy.py tests/test_online_update.py \
        tests/test_integration_l5.py -v

# Run specific test
pytest tests/test_capital_manager.py::TestCapitalCalculation -v

# Run with coverage
pytest tests/test_*.py --cov=src/execution --cov=src/training -v
```

---

## Database Queries

### Check capital decisions

```sql
SELECT * FROM capital_state 
WHERE symbol = 'EURUSD' 
ORDER BY time DESC 
LIMIT 10;
```

### Check scalp events

```sql
SELECT event_type, COUNT(*) as count, SUM(pnl) as total_pnl
FROM scalp_events 
WHERE symbol = 'EURUSD' 
GROUP BY event_type;
```

### Check RL policy

```sql
SELECT action, COUNT(*) as count, ROUND(AVG(mean_value), 3) as avg_value
FROM rl_policy 
WHERE regime = 'TREND_UP' 
GROUP BY action;
```

### Check RL events

```sql
SELECT action, COUNT(*) as count, ROUND(AVG(reward), 3) as avg_reward
FROM rl_events 
WHERE regime = 'TREND_UP' AND time > datetime('now', '-1 day')
GROUP BY action;
```

---

## API Summary

```python
# Capital Manager
capital_mgr.calc_base_contracts() -> int
capital_mgr.can_realavancar(...) -> (bool, str)
capital_mgr.calc_contracts(...) -> CapitalState
capital_mgr.export_stats() -> Dict

# Scalp Manager
scalp_mgr.open_scalp(...)
scalp_mgr.update_scalp(symbol, price, time) -> bool
scalp_mgr.get_active_scalp(symbol) -> ScalpSetup
scalp_mgr.is_in_cooldown(symbol) -> bool
scalp_mgr.export_stats() -> Dict

# RL Policy
rl_policy.select_action(regime, state) -> str
rl_policy.update_from_trade(...) 
rl_policy.freeze_regime(regime)
rl_policy.export_stats(regime) -> Dict

# RL Gate
rl_gate.apply_gate(...) -> (Decision, str, bool)
rl_gate.update_from_trade(...)

# Online Updater
updater.add_trade(trade)
updater.should_update() -> bool
updater.create_snapshot(...)
updater.clear_pending()
updater.rollback_to_snapshot(snapshot_id)
```

---

## Where to Find More Info

- **Full Documentation**: `LEVEL5.md` (3000+ lines)
- **Implementation Summary**: `LEVEL5_SUMMARY.md`
- **Test Examples**: `tests/test_*.py` (115+ test cases)
- **Source Code**: `src/execution/`, `src/training/`

---

## Quick Decision Tree

```
Is RL_POLICY_ENABLED=true?
├─ NO → Run like Level 4 (nothing changes)
└─ YES
   ├─ BossBrain generates signal
   ├─ RL Gate: should we trade?
   │  ├─ NO → HOLD
   │  └─ YES → continue
   ├─ Capital Manager: how many contracts?
   │  ├─ base_contracts = floor(capital/margin)
   │  └─ Can realavancagem? (8 checks)
   │     ├─ YES → extra_contracts = 1
   │     └─ NO → extra_contracts = 0
   ├─ RL Policy: which action?
   │  ├─ HOLD
   │  ├─ ENTER (base only)
   │  ├─ ENTER_CONSERVATIVE (reduced)
   │  └─ ENTER_WITH_REALAVANCAGEM (base + extra)
   ├─ Execute position (size = base_contracts)
   ├─ If extra approved: Scalp Manager opens quick TP/SL
   └─ After close: Online Updater → Update RL → Snapshot
```

---

## Disable Level 5 (Fallback to L4)

If you need to quickly disable L5:

```env
RL_POLICY_ENABLED=false
REALAVANCAGEM_ENABLED=false
```

System will behave exactly like Level 4. No other changes needed.

---

**LEVEL 5 READY FOR PRODUCTION** ✅

Questions? See LEVEL5.md for detailed docs.
