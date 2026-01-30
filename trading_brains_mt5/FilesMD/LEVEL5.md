# Level 5: Reinforcement Learning + Capital Management + Controlled Re-Leverage

## Overview

**Level 5** is the apex implementation layer that adds intelligent, adaptive position sizing based on operator capital combined with reinforcement learning policies that discover which trading actions work best in each market regime. This level enables:

1. **Capital-aware position sizing** - Contracts are calculated dynamically based on operator's BRL capital and margin requirements
2. **Regime-aware RL policies** - Separate Thompson Sampling policies per regime learn which actions (HOLD, ENTER, ENTER_CONSERVATIVE, ENTER_WITH_REALAVANCAGEM) work best
3. **Controlled re-leveraging** - Extra contracts beyond base position can be opened only if 8 validation layers pass
4. **Scalp engine for extras** - Quick TP/SL system for leveraged contracts with automatic profit protection
5. **Safe online learning** - Incremental policy updates with batching, snapshots, and rollback capability

### Key Innovation

**Separation of concerns**: Capital manager handles contracts, RL policy handles decision quality, scalp manager handles quick exits. Online updater manages safe, incremental learning from real trade outcomes.

---

## Architecture

### Component Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         Trading Engine (Main)                      │
└────────────────────────────────────────────────────────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        ┌───────▼──────┐   ┌─────▼──────┐  ┌────▼─────────┐
        │  BossBrain   │   │ Meta-Brain │  │  Risk-Limits │
        │  (Signals)   │   │ (Weights)  │  │  (Daily Loss) │
        └───────┬──────┘   └─────┬──────┘  └────┬─────────┘
                │                │             │
                └────────────────┼─────────────┘
                                 │
                          ┌──────▼───────┐
                          │   RL Gate    │ ◄─ NEW L5
                          │ (Select Act) │
                          └──────┬───────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
         ┌──────▼──────┐  ┌──────▼──────┐  ┌────▼────────┐
         │   Capital   │  │  Scalp Mgr  │  │ Liquidity   │
         │   Manager   │  │ (Quick Exit)│  │ Levels      │
         └──────┬──────┘  └──────┬──────┘  └────┬────────┘
                │                │             │
                └────────────────┼─────────────┘
                                 │
                          ┌──────▼──────────┐
                          │   Order Exec    │
                          │ (size, TP, SL)  │
                          └──────┬──────────┘
                                 │
                          ┌──────▼──────────┐
                          │   MT5 Orders    │
                          │ (Live Execution)│
                          └─────────────────┘
```

### Module Interaction

1. **BossBrain** generates trading signal (EURUSD BUY at 1.0850)
2. **RL Gate** receives signal + regime/confidence/liquidity
3. **Capital Manager** calculates contracts (base=10, extra eligible=1)
4. **RL Policy** selects action:
   - `HOLD` → Reject entry
   - `ENTER` → Base contracts only (10)
   - `ENTER_CONSERVATIVE` → Reduced (7-8)
   - `ENTER_WITH_REALAVANCAGEM` → Base + Extra (11) if validated
5. **Scalp Manager** (if extra) opens quick TP/SL for those extras
6. **Online Updater** batches outcomes and updates RL policy

---

## Configuration Parameters

All L5 parameters are in `settings.py`. Add these to your `.env` file:

### Capital Management

```python
# Operator's actual BRL balance
OPERATOR_CAPITAL_BRL=10000.0

# Margin required per contract (BRL)
MARGIN_PER_CONTRACT_BRL=1000.0

# Hard cap on maximum contracts
MAX_CONTRACTS_CAP=10

# Minimum contracts to enforce
MIN_CONTRACTS=1
```

**Formula**: `base_contracts = floor(OPERATOR_CAPITAL_BRL / MARGIN_PER_CONTRACT_BRL)`, capped at `MAX_CONTRACTS_CAP`

Example:
- Capital: 10,000 BRL
- Margin per: 1,000 BRL
- Max cap: 10
- Result: 10 contracts base

### Re-Leverage Configuration

```python
# Enable/disable extra leveraged contracts
REALAVANCAGEM_ENABLED=true

# Maximum extra contracts on top of base
REALAVANCAGEM_MAX_EXTRA_CONTRACTS=1

# Mode: SCALP_ONLY (quick TP/SL only) or HYBRID
REALAVANCAGEM_MODE=SCALP_ONLY

# Require daily profit before allowing extras
REALAVANCAGEM_REQUIRE_PROFIT_TODAY=true
REALAVANCAGEM_MIN_PROFIT_TODAY_BRL=50.0

# Minimum ensemble confidence to allow re-leverage
REALAVANCAGEM_MIN_GLOBAL_CONF=0.70

# Regimes that allow re-leverage (comma-separated)
REALAVANCAGEM_ALLOWED_REGIMES=TREND_UP,TREND_DOWN

# Regimes that forbid re-leverage
REALAVANCAGEM_FORBIDDEN_MODES=TRANSITION,CHAOTIC
```

**8-Layer Validation** (all must pass):
1. Feature enabled
2. Regime not in forbidden list
3. Regime in allowed whitelist
4. Transition not active
5. Global confidence >= min threshold
6. Daily profit >= minimum (if required)
7. Liquidity strength >= 0.50
8. Ensemble disagreement <= 0.40

### Scalp Configuration

```python
# Take-profit distance in points (not pips)
SCALP_TP_POINTS=80

# Stop-loss distance in points
SCALP_SL_POINTS=40

# Maximum hold time for scalp (seconds)
SCALP_MAX_HOLD_SECONDS=180

# Close remaining position after profit to protect
PROTECT_PROFIT_AFTER_SCALP=true

# Cooldown after successful scalp (seconds)
PROTECT_PROFIT_COOLDOWN_SECONDS=300

# Point value for P&L calculation
CONTRACT_POINT_VALUE=1.0
```

### RL Policy Configuration

```python
# Enable/disable RL policy gating
RL_POLICY_ENABLED=true

# Thompson Sampling or QLearning (currently only Thompson)
RL_POLICY_MODE=THOMPSON_SAMPLING

# Batch size for updates
RL_UPDATE_BATCH_SIZE=10

# Threshold for auto-freezing regime (15% degradation)
RL_FREEZE_THRESHOLD=0.15
```

---

## Core Modules

### 1. Capital Manager (`src/execution/capital_manager.py`)

Manages operator capital and calculates allowed contract sizes.

#### Main Class

```python
class CapitalManager:
    def __init__(self, operator_capital_brl, margin_per_contract_brl, 
                 max_contracts_cap, min_contracts, realavancagem_enabled, ...):
        """Initialize capital manager"""
    
    def calc_base_contracts(self) -> int:
        """Calculate base contracts from capital"""
        # base = floor(capital / margin), capped at max
        # Returns: 1-10 (or as configured)
    
    def can_realavancar(self, regime, global_confidence, ensemble_disagreement, 
                        liquidity_strength, daily_profit_brl, transition_active) -> (bool, str):
        """Validate re-leverage permission"""
        # Returns: (approved, reason)
        # Performs 8-layer validation
    
    def calc_contracts(self, symbol, regime, global_confidence, 
                       ensemble_disagreement, liquidity_strength, 
                       daily_profit_brl) -> CapitalState:
        """Calculate final contract distribution"""
        # Returns: CapitalState with base, extra, final, reason
    
    def get_last_state(self) -> Optional[CapitalState]:
        """Get most recent capital state"""
    
    def get_history(self, limit=100) -> List[CapitalState]:
        """Get recent capital decisions"""
    
    def export_stats(self) -> Dict:
        """Export statistics"""
        # Returns: {total_decisions, avg_base, max_final, ...}
```

#### Example Usage

```python
from src.execution.capital_manager import CapitalManager
from src.config.settings import Settings

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

# Calculate contracts
state = capital_mgr.calc_contracts(
    symbol="EURUSD",
    regime="TREND_UP",
    global_confidence=0.80,
    ensemble_disagreement=0.10,
    liquidity_strength=0.60,
    daily_profit_brl=100.0
)

print(f"Base: {state.base_contracts}, Extra: {state.extra_contracts}, "
      f"Final: {state.final_contracts}")
# Output: Base: 10, Extra: 1, Final: 11 (if all validations pass)
```

---

### 2. Scalp Manager (`src/execution/scalp_manager.py`)

Manages quick exits for leveraged extra contracts with separate TP/SL.

#### Main Classes

```python
@dataclass
class ScalpSetup:
    """Configuration for a scalp trade"""
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    scalp_tp_points: int
    scalp_sl_points: int
    max_hold_seconds: int
    extra_contracts: int
    opened_at: datetime
    
    def calc_tp_price(self) -> float:
        """Calculate TP price from points"""
        # BUY: entry + points
        # SELL: entry - points
    
    def calc_sl_price(self) -> float:
        """Calculate SL price from points"""
        # BUY: entry - points
        # SELL: entry + points

@dataclass
class ScalpEvent:
    """Record of scalp event"""
    time: datetime
    symbol: str
    event_type: str  # OPENED, TP_HIT, SL_HIT, TIMEOUT
    setup: ScalpSetup
    current_price: float
    pnl: float
    hold_time_seconds: int
    reason: str

class ScalpManager:
    def open_scalp(self, symbol, side, entry_price, extra_contracts, opened_at):
        """Open new scalp"""
        # Creates ScalpSetup and records OPENED event
    
    def update_scalp(self, symbol, current_price, current_time) -> bool:
        """Update scalp status"""
        # Checks TP, SL, timeout
        # Returns: True if closed, False if still open
    
    def get_active_scalp(self, symbol) -> Optional[ScalpSetup]:
        """Get current active scalp for symbol"""
    
    def is_in_cooldown(self, symbol) -> bool:
        """Check if symbol is in post-win cooldown"""
    
    def get_cooldown_remaining_seconds(self, symbol, current_time) -> float:
        """Get cooldown countdown"""
    
    def get_events(self, symbol=None, event_type=None, limit=100) -> List[ScalpEvent]:
        """Query scalp events"""
    
    def export_stats(self) -> Dict:
        """Export statistics"""
        # {total_scalps, wins, losses, winrate, avg_hold, total_pnl, ...}
```

#### Example Usage

```python
from src.execution.scalp_manager import ScalpManager
from datetime import datetime

scalp_mgr = ScalpManager(
    scalp_tp_points=80,
    scalp_sl_points=40,
    scalp_max_hold_seconds=180,
    contract_point_value=1.0,
    protect_profit_after_scalp=True,
    protect_profit_cooldown_seconds=300,
)

# Open scalp when extra contract is approved
now = datetime.now()
scalp_mgr.open_scalp(
    symbol="EURUSD",
    side="BUY",
    entry_price=1.0850,
    extra_contracts=1,
    opened_at=now
)

# Update on each bar
closed = scalp_mgr.update_scalp(
    symbol="EURUSD",
    current_price=1.0930,  # Hit TP at +80 points
    current_time=now
)

if closed:
    events = scalp_mgr.get_events(symbol="EURUSD")
    tp_event = events[-1]
    print(f"Scalp closed: {tp_event.event_type}, PnL: {tp_event.pnl}")
    # Output: Scalp closed: TP_HIT, PnL: 80.0
```

---

### 3. RL Policy (`src/training/reinforcement_policy.py`)

Thompson Sampling per regime to learn which trading actions work best.

#### Main Classes

```python
@dataclass
class RLState:
    """Discretized state for RL"""
    regime: str  # TREND_UP, TREND_DOWN, RANGE, etc
    time_bucket: str  # HH:00 format
    confidence_level: str  # LOW, MEDIUM, HIGH
    disagreement_level: str  # LOW, MEDIUM, HIGH
    
    def to_hash(self) -> str:
        """Generate deterministic state hash"""

@dataclass
class ActionValue:
    """Thompson Beta distribution for action value"""
    alpha: float
    beta: float
    count: int = 0
    total_reward: float = 0.0
    
    def sample(self) -> float:
        """Sample from Beta(alpha, beta)"""
        # Range: [0, 1]
    
    def mean(self) -> float:
        """Get mean of Beta distribution"""
        # = alpha / (alpha + beta)

class RLPolicy:
    def select_action(self, regime, state: RLState) -> str:
        """Select action via Thompson Sampling"""
        # Returns: HOLD, ENTER, ENTER_CONSERVATIVE, ENTER_WITH_REALAVANCAGEM
        # Uses Thompson Sampling: samples from each action's Beta, picks best
    
    def update_from_trade(self, regime, state_hash, action, reward, metadata=None):
        """Update action value based on trade outcome"""
        # reward: 0-1 (1=win, 0=loss)
        # Updates alpha (if reward > 0.5) or beta (if reward < 0.5)
    
    def freeze_regime(self, regime, reason=""):
        """Freeze regime from updating"""
        # Prevents learning from degraded performance
    
    def unfreeze_regime(self, regime):
        """Unfreeze regime and reset baseline"""
    
    def get_action_stats(self, regime, state_hash, action) -> Dict:
        """Get action statistics"""
        # {count, total_reward, mean_value, ...}
    
    def export_policy_table(self, regime) -> Dict:
        """Export entire policy for regime"""
        # JSON-serializable format
    
    def import_policy_table(self, regime, policy_data):
        """Import policy from external source"""
    
    def log_event(self, regime, state_hash, action, reward, reason=""):
        """Log RL decision event"""
    
    def get_events(self, regime=None, limit=100) -> List[Dict]:
        """Query RL events"""
    
    def export_stats(self, regime) -> Dict:
        """Export statistics for regime"""
```

#### Thompson Sampling Explanation

Thompson Sampling is a Bayesian approach to exploration/exploitation:

1. **Prior**: Beta(1, 1) = uniform distribution (uninformed)
2. **Learning**: Each trade outcome updates the distribution
   - Win → increase alpha (shift toward 1)
   - Loss → increase beta (shift toward 0)
3. **Selection**: Sample from each action's Beta, pick the one with highest sample
   - Encourages exploration early (high uncertainty)
   - Encourages exploitation later (high certainty)

```python
# Example: Action "ENTER" in TREND_UP
# Initially: Beta(1, 1) - could be good or bad

# After 3 wins: Beta(4, 1) - looks good, more likely to be selected
# After 3 losses: Beta(1, 4) - looks bad, less likely to be selected

# Thompson Sampling ensures diversity even with skewed distributions
# (sometimes samples from the low-probability "ENTER" even if alpha < beta)
```

#### Example Usage

```python
from src.training.reinforcement_policy import RLPolicy, RLState

rl_policy = RLPolicy(
    thompson_alpha_prior=1.0,
    thompson_beta_prior=1.0,
    freeze_threshold=0.15,
)

# Select action for trading decision
state = RLState(
    regime="TREND_UP",
    time_bucket="14:00",
    confidence_level="HIGH",
    disagreement_level="LOW",
)

action = rl_policy.select_action("TREND_UP", state)
print(f"RL recommends: {action}")
# Early training: mostly random (HOLD, ENTER, etc equally likely)
# After learning: might be ENTER_WITH_REALAVANCAGEM 70% of the time

# After trade closes, update
rl_policy.update_from_trade(
    regime="TREND_UP",
    state_hash=state.to_hash(),
    action=action,
    reward=0.8,  # Won the trade
)

# Get statistics
stats = rl_policy.get_action_stats("TREND_UP", state.to_hash(), action)
print(f"Action '{action}': count={stats['count']}, "
      f"mean_value={stats['mean_value']:.2f}")
# Output: Action 'ENTER': count=42, mean_value=0.62
```

---

### 4. RL Gate (`src/execution/rl_gate.py`)

Applies RL policy to BossBrain decisions, acting as a confidence filter.

#### Main Class

```python
class RLGate:
    def __init__(self, settings, db_path, rl_policy, capital_manager):
        """Initialize RL gate"""
    
    def apply_gate(self, boss_decision, regime, hour, global_confidence, 
                   ensemble_disagreement, liquidity_strength, symbol, 
                   current_price) -> (Decision, str, bool):
        """Apply RL gate to boss decision"""
        # Returns:
        #   - Modified Decision (action, size, TP, SL modified per RL)
        #   - RL action taken (HOLD, ENTER, ENTER_CONSERVATIVE, ENTER_WITH_REALAVANCAGEM)
        #   - Whether re-leverage was approved (bool)
    
    def update_from_trade(self, symbol, regime, state_hash, rl_action, 
                          trade_pnl, trade_duration_seconds):
        """Update RL policy after trade closes"""
```

#### Integration Point

RL Gate sits between BossBrain and execution:

```
BossBrain Decision (BUY @ 1.0850, size=10)
              ↓
         RL Gate
         Apply policy selection
         Modify decision/size
              ↓
Modified Decision (action, size, TP, SL, metadata)
              ↓
         Execute order
```

---

### 5. Online Updater (`src/training/online_update.py`)

Manages safe, incremental policy updates with batching and snapshots.

#### Main Classes

```python
@dataclass
class PolicySnapshot:
    """Snapshot of policy state"""
    snapshot_id: str
    regime: str
    time: datetime
    policy_data: str  # JSON string of RL policy table
    metrics: Dict  # Performance metrics at snapshot time
    note: Optional[str] = None

class OnlineUpdater:
    def __init__(self, batch_size=10, snapshot_interval=20, keep_snapshots=5):
        """Initialize online updater"""
    
    def add_trade(self, trade: Dict):
        """Add closed trade to pending buffer"""
        # trade: {regime, state_hash, action, reward, pnl, ...}
    
    def should_update(self) -> bool:
        """Check if batch is full"""
        # Returns: True if pending_count >= batch_size
    
    def get_pending_trades(self, regime=None, limit=None) -> List[Dict]:
        """Query pending trades"""
        # Optionally filter by regime
    
    def clear_pending(self):
        """Clear pending buffer after processing"""
    
    def create_snapshot(self, regime, policy_data, metrics, note="") -> PolicySnapshot:
        """Create snapshot of policy"""
        # Keeps only keep_snapshots most recent
    
    def get_last_snapshot(self, regime) -> Optional[PolicySnapshot]:
        """Get most recent snapshot"""
    
    def rollback_to_snapshot(self, snapshot_id) -> Optional[PolicySnapshot]:
        """Restore policy from snapshot"""
    
    def get_snapshots(self, regime, limit=None) -> List[PolicySnapshot]:
        """Query snapshot history"""
    
    def export_state(self) -> Dict:
        """Export current state"""
```

#### Batch Processing Workflow

```
Trade closes → add_trade() → pending_trades buffer
                                ↓
                    Accumulate N trades
                                ↓
                    should_update() → True
                                ↓
        Batch ready! Create snapshot of current policy
                                ↓
        Extract rewards from N trades
                                ↓
        Update RL policy for each trade
                                ↓
        clear_pending()
```

#### Example Usage

```python
from src.training.online_update import OnlineUpdater

updater = OnlineUpdater(batch_size=10, snapshot_interval=20, keep_snapshots=5)

# After each trade closes
updater.add_trade({
    "symbol": "EURUSD",
    "regime": "TREND_UP",
    "state_hash": state_hash,
    "action": rl_action,
    "pnl": 100.0,
    "duration_seconds": 300,
})

# Check if batch is ready
if updater.should_update():
    # Get all pending trades
    trades = updater.get_pending_trades()
    
    # Create snapshot before updating
    snapshot = updater.create_snapshot(
        regime="TREND_UP",
        policy_data=rl_policy.export_policy_table("TREND_UP"),
        metrics={"trade_count": len(trades)},
        note="Before policy update batch 42"
    )
    
    # Update RL policy
    for trade in trades:
        rl_policy.update_from_trade(
            regime=trade["regime"],
            state_hash=trade["state_hash"],
            action=trade["action"],
            reward=0.8 if trade["pnl"] > 0 else 0.2,
        )
    
    # Clear buffer for next batch
    updater.clear_pending()
    
    # If performance degrades, rollback
    if average_reward < 0.4:
        updater.rollback_to_snapshot(snapshot.snapshot_id)
        print("Performance degraded, rolled back to previous policy")
```

---

## Database Schema

### New L5 Tables

```sql
-- Capital decisions
CREATE TABLE capital_state (
    id INTEGER PRIMARY KEY,
    time TEXT,
    symbol TEXT,
    operator_capital_brl REAL,
    margin_per_contract_brl REAL,
    max_contracts_cap INTEGER,
    base_contracts INTEGER,
    extra_contracts INTEGER,
    final_contracts INTEGER,
    reason TEXT,
    detail_json TEXT
);

-- Scalp events
CREATE TABLE scalp_events (
    id INTEGER PRIMARY KEY,
    time TEXT,
    symbol TEXT,
    event_type TEXT,  -- OPENED, TP_HIT, SL_HIT, TIMEOUT
    side TEXT,
    entry_price REAL,
    exit_price REAL,
    extra_contracts INTEGER,
    pnl REAL,
    hold_time_seconds INTEGER,
    reason TEXT,
    detail_json TEXT
);

-- RL policy values
CREATE TABLE rl_policy (
    id INTEGER PRIMARY KEY,
    regime TEXT,
    state_hash TEXT,
    action TEXT,
    alpha REAL,
    beta REAL,
    count INTEGER,
    total_reward REAL,
    mean_value REAL,
    updated_at TEXT,
    UNIQUE(regime, state_hash, action)
);

-- RL events
CREATE TABLE rl_events (
    id INTEGER PRIMARY KEY,
    time TEXT,
    symbol TEXT,
    regime TEXT,
    state_hash TEXT,
    action TEXT,
    reward REAL,
    reason TEXT,
    frozen INTEGER,
    detail_json TEXT
);

-- Policy snapshots
CREATE TABLE policy_snapshots (
    id INTEGER PRIMARY KEY,
    snapshot_id TEXT UNIQUE,
    regime TEXT,
    time TEXT,
    policy_data TEXT,  -- JSON export
    metrics_json TEXT,
    note TEXT
);

-- RL reports
CREATE TABLE rl_report_log (
    id INTEGER PRIMARY KEY,
    report_date TEXT,
    symbol TEXT,
    total_rl_events INTEGER,
    actions_enter_count INTEGER,
    actions_hold_count INTEGER,
    actions_conservative_count INTEGER,
    actions_realavancagem_count INTEGER,
    blocked_by_rl_count INTEGER,
    avg_reward REAL,
    regimes_frozen_count INTEGER,
    total_realavancagem_triggered INTEGER,
    realavancagem_success_rate REAL,
    total_scalps INTEGER,
    scalp_winrate REAL,
    scalp_total_pnl REAL,
    performance_trend REAL,
    detail_json TEXT
);
```

### Repository Functions

```python
# Insert capital state
repo.insert_capital_state(db_path, time, symbol, capital_state)

# Insert scalp event
repo.insert_scalp_event(db_path, time, symbol, event)

# Upsert RL policy value
repo.upsert_rl_policy(db_path, regime, state_hash, action, policy_values)

# Insert RL event
repo.insert_rl_event(db_path, time, symbol, event)

# Create policy snapshot
repo.create_policy_snapshot(db_path, snapshot_id, regime, time, policy_data, metrics)

# Fetch RL policy table
policy = repo.fetch_rl_policy_table(db_path, regime)

# Insert RL report
repo.insert_rl_report(db_path, report_date, symbol, report_data)
```

---

## Integration with Existing Levels

### With Level 4 (Liquidity Zones)

RL Gate uses liquidity strength to validate re-leverage:

```python
# In RL Gate
liquidity_strength = get_liquidity_strength_from_l4()
can_realavanca, _ = capital_mgr.can_realavancar(
    ...
    liquidity_strength=liquidity_strength,  # From L4
    ...
)
```

### With Level 3 (Regime Transitions)

RL policies are frozen during transitions:

```python
# Forbidden in these modes
REALAVANCAGEM_FORBIDDEN_MODES=TRANSITION,CHAOTIC

# Capital manager blocks re-leverage
can_realavanca, reason = capital_mgr.can_realavancar(
    ...
    transition_active=regime_detector.is_transitioning(),  # From L3
    ...
)
```

### With Levels 1-2 (Core Ensemble)

Meta-Brain weights are used as global_confidence:

```python
# In runner.py
meta_decision = meta_brain.evaluate(regime, hour, vol, brain_scores)
global_confidence = meta_decision.global_confidence

# Pass to RL Gate
modified_decision = rl_gate.apply_gate(
    boss_decision,
    ...
    global_confidence=global_confidence,  # From L1/L2
    ...
)
```

---

## Configuration Guide

### Conservative Setup (Capital Protection)

```env
# Smaller capital
OPERATOR_CAPITAL_BRL=5000

# Higher margin per contract
MARGIN_PER_CONTRACT_BRL=1000

# Lower contract cap
MAX_CONTRACTS_CAP=5

# Disable re-leverage
REALAVANCAGEM_ENABLED=false

# High confidence requirement
REALAVANCAGEM_MIN_GLOBAL_CONF=0.80

# No re-leverage during profit requirement
REALAVANCAGEM_REQUIRE_PROFIT_TODAY=true
REALAVANCAGEM_MIN_PROFIT_TODAY_BRL=100
```

Result: Very conservative, 5 contracts max, no extras

### Aggressive Setup (Growth Mode)

```env
# Large capital
OPERATOR_CAPITAL_BRL=50000

# Lower margin per contract
MARGIN_PER_CONTRACT_BRL=500

# High contract cap
MAX_CONTRACTS_CAP=20

# Enable re-leverage
REALAVANCAGEM_ENABLED=true

# Lower confidence requirement
REALAVANCAGEM_MIN_GLOBAL_CONF=0.60

# Flexible profit requirement
REALAVANCAGEM_REQUIRE_PROFIT_TODAY=false

# Allow extra scalps frequently
REALAVANCAGEM_ALLOWED_REGIMES=TREND_UP,TREND_DOWN,RANGE
```

Result: Aggressive, 20-100 contracts possible, extras allowed frequently

### Balanced Setup (Recommended)

```env
# Moderate capital
OPERATOR_CAPITAL_BRL=10000

# Standard margin
MARGIN_PER_CONTRACT_BRL=1000

# Reasonable cap
MAX_CONTRACTS_CAP=10

# Selective re-leverage
REALAVANCAGEM_ENABLED=true
REALAVANCAGEM_MAX_EXTRA_CONTRACTS=1

# Moderate confidence
REALAVANCAGEM_MIN_GLOBAL_CONF=0.70

# Require some profit
REALAVANCAGEM_REQUIRE_PROFIT_TODAY=true
REALAVANCAGEM_MIN_PROFIT_TODAY_BRL=50

# Trend-only re-leverage
REALAVANCAGEM_ALLOWED_REGIMES=TREND_UP,TREND_DOWN

# Scalp settings for quick exits
SCALP_TP_POINTS=80
SCALP_SL_POINTS=40
SCALP_MAX_HOLD_SECONDS=180
```

Result: Balanced risk/reward, controlled leverage, learning-based decisions

---

## Monitoring & Debugging

### Capital Manager Metrics

```python
stats = capital_mgr.export_stats()
print(f"Total decisions: {stats['total_decisions']}")
print(f"Average base contracts: {stats['avg_base_contracts']:.2f}")
print(f"Max final contracts: {stats['max_final_contracts']}")
print(f"Re-leverage frequency: {stats['realavancagem_frequency']:.1%}")
```

### Scalp Manager Metrics

```python
stats = scalp_mgr.export_stats()
print(f"Total scalps: {stats['total_scalps']}")
print(f"Win rate: {stats['winrate']:.1%}")
print(f"Total PnL: {stats['total_pnl']:.2f}")
print(f"Average hold time: {stats['avg_hold_time_seconds']:.0f}s")
```

### RL Policy Metrics

```python
stats = rl_policy.export_stats("TREND_UP")
print(f"Total updates: {stats['total_updates']}")
print(f"Frozen: {stats['frozen']}")

for action in ["HOLD", "ENTER", "ENTER_CONSERVATIVE", "ENTER_WITH_REALAVANCAGEM"]:
    action_stats = rl_policy.get_action_stats("TREND_UP", "example_state", action)
    print(f"  {action}: count={action_stats['count']}, "
          f"mean={action_stats['mean_value']:.2f}")
```

### Online Updater Metrics

```python
state = updater.export_state()
print(f"Total trades logged: {state['total_trades']}")
print(f"Pending trades: {state['pending_trades_count']}")
print(f"Snapshots: {state['snapshot_count']}")
print(f"Batch ready: {updater.should_update()}")
```

---

## Troubleshooting

### Problem: RL always returns HOLD

**Cause**: Policy not initialized, or confidence too low

**Solution**:
```python
# Check current stats
stats = rl_policy.get_action_stats(regime, state_hash, "ENTER")
if stats["count"] == 0:
    print("RL policy not trained yet. HOLD until sufficient data.")

# Or check confidence
if global_confidence < settings.realavancagem_min_global_conf:
    print(f"Confidence {global_confidence:.1%} below threshold")
```

### Problem: Capital calculator seems wrong

**Debug**:
```python
print(f"Capital: {capital_mgr.operator_capital_brl}")
print(f"Margin per: {capital_mgr.margin_per_contract_brl}")

base = capital_mgr.calc_base_contracts()
print(f"Base contracts: {base}")

print(f"Max cap: {capital_mgr.max_contracts_cap}")
print(f"Min contracts: {capital_mgr.min_contracts}")

# Formula: base = floor(capital / margin), capped
expected = min(capital_mgr.max_contracts_cap, 
               max(capital_mgr.min_contracts,
                   int(capital_mgr.operator_capital_brl / capital_mgr.margin_per_contract_brl)))
print(f"Expected: {expected}, Got: {base}")
```

### Problem: Scalps closing too early

**Debug**:
```python
setup = scalp_mgr.get_active_scalp(symbol)
if setup:
    tp = setup.calc_tp_price()
    sl = setup.calc_sl_price()
    print(f"TP: {tp}, SL: {sl}, Current: {current_price}")
    print(f"TP distance: {abs(current_price - tp)}")
    print(f"SL distance: {abs(current_price - sl)}")
```

### Problem: Policy not learning

**Check**:
1. Batch size: `updater.should_update()` must return True
2. Reward calculation: must be 0-1, normalized correctly
3. State hash consistency: same state must produce same hash
4. Regime not frozen: `rl_policy.export_stats(regime)['frozen']`

---

## Testing

Run comprehensive tests:

```bash
# Capital Manager tests
pytest tests/test_capital_manager.py -v

# Scalp Manager tests
pytest tests/test_scalp_manager.py -v

# RL Policy tests
pytest tests/test_rl_policy.py -v

# Online Updater tests
pytest tests/test_online_update.py -v

# Integration tests
pytest tests/test_integration_l5.py -v

# All Level 5 tests
pytest tests/test_*_l5.py tests/test_capital*.py tests/test_scalp*.py tests/test_rl*.py tests/test_online*.py -v
```

---

## Performance Tuning

### Increasing Re-Leverage Frequency

Lower validation thresholds:

```env
REALAVANCAGEM_MIN_GLOBAL_CONF=0.60  # Down from 0.70
REALAVANCAGEM_MIN_PROFIT_TODAY_BRL=20  # Down from 50
REALAVANCAGEM_ALLOWED_REGIMES=TREND_UP,TREND_DOWN,RANGE  # Add RANGE
```

### Decreasing Re-Leverage Frequency

Raise validation thresholds:

```env
REALAVANCAGEM_MIN_GLOBAL_CONF=0.80  # Up from 0.70
REALAVANCAGEM_MIN_PROFIT_TODAY_BRL=150  # Up from 50
REALAVANCAGEM_ALLOWED_REGIMES=TREND_UP,TREND_DOWN  # Strict
```

### Faster RL Learning

Smaller batch size:

```env
RL_UPDATE_BATCH_SIZE=5  # Update more frequently
```

### More Conservative RL

Larger batch size:

```env
RL_UPDATE_BATCH_SIZE=20  # Update less frequently, more stable
```

### Aggressive Scalp Exits

Smaller distances:

```env
SCALP_TP_POINTS=40  # Quick wins
SCALP_SL_POINTS=20  # Quick losses
```

### Patient Scalp Exits

Larger distances:

```env
SCALP_TP_POINTS=150  # Give more room
SCALP_SL_POINTS=80   # Larger stops
```

---

## API Reference

### Capital Manager API

```python
# Get current contract allocation
contracts = capital_mgr.calc_contracts(symbol, regime, conf, disagree, liquidity, daily_profit)
print(contracts.final_contracts)

# Check if can add extras
approved, reason = capital_mgr.can_realavancar(regime, conf, disagree, liquidity, profit, transition)
if approved:
    # Open extra scalp
```

### Scalp Manager API

```python
# Open scalp when extra contracts available
scalp_mgr.open_scalp(symbol, side, entry_price, extra_contracts, opened_at)

# Update every bar
scalp_mgr.update_scalp(symbol, current_price, current_time)

# Check if protected by cooldown
if scalp_mgr.is_in_cooldown(symbol):
    # Skip new trade (profit protection active)
```

### RL Policy API

```python
# Get action before trading
action = rl_policy.select_action(regime, state)

# Update after trade closes
rl_policy.update_from_trade(regime, state_hash, action, reward)

# Export for analysis
policy = rl_policy.export_policy_table(regime)
```

### RL Gate API

```python
# Modify boss decision per RL
modified, rl_action, realavanca_ok = rl_gate.apply_gate(
    boss_decision, regime, hour, conf, disagree, liquidity, symbol, price
)

# Update after trade
rl_gate.update_from_trade(symbol, regime, state_hash, rl_action, pnl, duration)
```

### Online Updater API

```python
# Buffer trade
updater.add_trade(trade_dict)

# Check if ready
if updater.should_update():
    # Create snapshot
    snap = updater.create_snapshot(regime, policy_data, metrics)
    # Update RL
    rl_policy.update_from_trade(...)
    # Clear buffer
    updater.clear_pending()
```

---

## Examples

### Full Trading Loop with Level 5

```python
from src.brains.brain_hub import BossBrain
from src.brains.meta_brain import MetaBrain
from src.execution.capital_manager import CapitalManager
from src.execution.scalp_manager import ScalpManager
from src.execution.rl_gate import RLGate
from src.training.reinforcement_policy import RLPolicy, RLState
from src.training.online_update import OnlineUpdater
from src.config.settings import Settings
from src.db import repo
from datetime import datetime

# Initialize
settings = Settings.load_settings()
boss = BossBrain()
meta = MetaBrain(settings, settings.db_path)
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
updater = OnlineUpdater(
    batch_size=settings.rl_update_batch_size,
    snapshot_interval=settings.rl_update_batch_size * 2,
)

# Trading loop
for bar in market_feed:
    # 1. BossBrain generates signal
    boss_decision = boss.run(bar.candles, bar.context)
    
    # 2. MetaBrain evaluates context
    meta_decision = meta.evaluate(
        bar.regime, bar.hour, bar.volatility, bar.brain_scores, bar.recent_trades
    )
    
    # 3. Capital Manager calculates contracts
    daily_profit = calculate_daily_profit()
    capital_state = capital_mgr.calc_contracts(
        symbol=bar.symbol,
        regime=bar.regime,
        global_confidence=meta_decision.global_confidence,
        ensemble_disagreement=meta_decision.disagreement,
        liquidity_strength=bar.liquidity_strength,
        daily_profit_brl=daily_profit,
    )
    
    # 4. RL Gate applies policy
    modified_decision, rl_action, realavanca_ok = rl_gate.apply_gate(
        boss_decision=boss_decision,
        regime=bar.regime,
        hour=bar.hour,
        global_confidence=meta_decision.global_confidence,
        ensemble_disagreement=meta_decision.disagreement,
        liquidity_strength=bar.liquidity_strength,
        symbol=bar.symbol,
        current_price=bar.close,
    )
    
    # 5. Skip if RL blocked
    if modified_decision.action == "HOLD":
        continue
    
    # 6. Execute order
    order = send_order(
        symbol=bar.symbol,
        side=modified_decision.action,
        size=modified_decision.size,
        entry=bar.close,
        sl=modified_decision.sl,
        tp=modified_decision.tp1,
    )
    
    # 7. If extra contracts approved, open scalp
    if realavanca_ok and capital_state.extra_contracts > 0:
        scalp_mgr.open_scalp(
            symbol=bar.symbol,
            side=modified_decision.action,
            entry_price=bar.close,
            extra_contracts=capital_state.extra_contracts,
            opened_at=datetime.now(),
        )
    
    # 8. Update scalps on each bar
    scalp_mgr.update_scalp(bar.symbol, bar.close, bar.time)

# After trade closes
def on_trade_close(trade):
    # Calculate PnL and duration
    pnl = trade.close_price - trade.entry_price  # Simplified
    duration = (trade.close_time - trade.open_time).total_seconds()
    
    # Get RL state from original entry
    state = RLState(regime, time_bucket, confidence_level, disagreement_level)
    
    # Add to online updater
    updater.add_trade({
        "symbol": trade.symbol,
        "regime": regime,
        "state_hash": state.to_hash(),
        "action": rl_action_taken,
        "pnl": pnl,
        "duration_seconds": duration,
    })
    
    # If batch ready, update RL policy
    if updater.should_update():
        snap = updater.create_snapshot(
            regime=regime,
            policy_data=rl_policy.export_policy_table(regime),
            metrics={"batch_pnl": sum([t["pnl"] for t in updater.get_pending_trades()])},
        )
        
        for trade_record in updater.get_pending_trades():
            reward = 0.8 if trade_record["pnl"] > 0 else 0.2
            rl_policy.update_from_trade(
                regime=trade_record["regime"],
                state_hash=trade_record["state_hash"],
                action=trade_record["action"],
                reward=reward,
            )
        
        updater.clear_pending()
```

---

## Migration Guide

### From Level 4 to Level 5

1. **Add configuration** (`.env` file)
   ```env
   OPERATOR_CAPITAL_BRL=10000
   MARGIN_PER_CONTRACT_BRL=1000
   # ... etc
   ```

2. **Update database schema**
   ```bash
   python -c "from src.db.schema import ensure_tables; ensure_tables('trading.db')"
   ```

3. **Initialize components** in your runner
   ```python
   capital_mgr = CapitalManager(...)
   rl_policy = RLPolicy()
   rl_gate = RLGate(settings, db_path, rl_policy, capital_mgr)
   ```

4. **Apply RL gate to boss decision** (existing flow unchanged)
   ```python
   # Old: decision = boss.run(...)
   # New: 
   boss_decision = boss.run(...)
   decision, rl_action, _ = rl_gate.apply_gate(boss_decision, ...)
   ```

5. **Backward compatible**: If disabled, acts like L4
   ```env
   RL_POLICY_ENABLED=false
   REALAVANCAGEM_ENABLED=false
   # Runs exactly like Level 4
   ```

---

## Summary

**Level 5** adds three powerful layers on top of L1-L4:

1. **Capital Management**: Position sizing based on operator capital and margin
2. **Reinforcement Learning**: Thompson Sampling per regime discovers optimal trading actions
3. **Controlled Re-Leverage**: Extra contracts only with strict validation + fast scalp exits

**Key benefits**:
- Adaptive to operator's capital
- Learns regime-specific strategies
- Safe re-leveraging with quick exits
- Incremental learning with rollback

**Status**: ✅ Production-ready, fully tested, backward compatible with Levels 1-4
