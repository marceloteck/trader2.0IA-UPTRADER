"""
V4_QUICK_START.md - Quick Start Guide for V4 Execution Engine
"""

# V4 Quick Start - Execution Engine

## 30-Second Overview
- **V4 = Unified execution layer** with realistic fills, risk management, and auditoria
- **SIM mode (default)**: Paper trading, safe for testing
- **REAL mode**: Live trading with 3 safety layers
- **Default**: Disabled - you must explicitly enable it

## Getting Started (5 minutes)

### 1. Check Current Config
```bash
cat .env | grep -E "LIVE_MODE|ENABLE_LIVE"
```

Expected output:
```
LIVE_MODE=SIM
ENABLE_LIVE_TRADING=false
```

### 2. Test Paper Trading
```bash
RUN_LIVE_SIM.bat
```
- Let it run for 8+ hours
- Check logs: `./data/logs/app.log`
- Verify fills are realistic (not always perfect)

### 3. Enable Real (3-LAYER SAFETY)

**Layer 1: Manual File**
```bash
mkdir ./data
echo. > ./data/LIVE_OK.txt
```
(This file MUST exist to enable REAL mode)

**Layer 2: .env Configuration**
```ini
LIVE_MODE=REAL
ENABLE_LIVE_TRADING=true
LIVE_CONFIRM_KEY=my_secret_key_12345
```

**Layer 3: System Validation**
```bash
RUN_HEALTHCHECK.bat
```

### 4. Run LIVE REAL
```bash
RUN_LIVE_REAL.bat
```
- System checks all 3 safety layers
- Confirms MT5 connection
- Starts trading with configured limits

## Risk Configuration

Edit `.env` with YOUR risk tolerance:

```ini
# ===== HARD LIMITS =====
DAILY_LOSS_LIMIT=500         # Stop if daily loss reaches -$500
DAILY_PROFIT_TARGET=1000     # Stop if gain reaches +$1000 (0=disabled)

# ===== TRADE FREQUENCY =====
MAX_TRADES_PER_DAY=10        # Max 10 trades per day
MAX_TRADES_PER_HOUR=2        # Max 2 trades per hour (prevents clustering)
COOLDOWN_SECONDS=180         # Wait 3 min between trades

# ===== AUTOMATIC DEGRADE =====
# If 3 consecutive losses, reduce position size
MAX_CONSEC_LOSSES=3
DEGRADE_STEPS=3              # Levels: 1.0x → 0.5x → 0.25x → 0.125x
DEGRADE_FACTOR=0.5           # (each level = previous × 0.5)
```

## Emergency Controls

Create files in `./data/` to control running system:

| File | Effect | Create | Remove |
|------|--------|--------|--------|
| `STOP.txt` | Stop completely | `echo . > ./data/STOP.txt` | Delete file |
| `PAUSE.txt` | Pause (monitor only) | `echo . > ./data/PAUSE.txt` | Delete file |
| `RESET_DAY.txt` | Reset daily counters | `echo . > ./data/RESET_DAY.txt` | Delete file |

## Monitoring & Diagnostics

### View Logs
```bash
# Last 100 lines
tail -100 ./data/logs/app.log

# Real-time
tail -f ./data/logs/app.log
```

### Replay Last 200 Trades
```bash
RUN_DIAG_REPLAY.bat
```
Outputs: `./data/logs/replay_report.json`

### Check System Health
```bash
RUN_HEALTHCHECK.bat
```
Verifies:
- MT5 connection
- Symbol availability
- Data freshness
- Configuration validity

## Database Audit

All trades logged to `./data/db/trading.db`:

```sql
-- See all orders
SELECT * FROM order_events ORDER BY timestamp DESC LIMIT 20;

-- See all risk events (circuit breakers)
SELECT * FROM risk_events ORDER BY timestamp DESC;

-- See MT5 events (connection, errors)
SELECT * FROM mt5_events ORDER BY timestamp DESC;

-- See decision trail (full audit)
SELECT sequence, decision, executed FROM audit_trail LIMIT 10;

-- See execution results
SELECT * FROM execution_results ORDER BY timestamp DESC LIMIT 20;
```

## Troubleshooting

### "MT5 not connected"
- [ ] Verify MetaTrader5 is open
- [ ] Check terminal status in Tools > Options
- [ ] Try RUN_HEALTHCHECK.bat
- [ ] Restart MT5 and try again

### "Max trades/hour reached"
- This is working as intended!
- System prevents overtrade clustering
- Wait for cooldown or adjust MAX_TRADES_PER_HOUR in .env

### "System paused - daily loss limit"
- Hard stop activated!
- Check your balance vs DAILY_LOSS_LIMIT setting
- Consider if you want to adjust the limit
- Read logs to understand what happened

### "Position degraded to 0.5x size"
- System detected consecutive losses
- Automatically reducing risk (working as intended)
- Will recover 1 level per day with good trades
- Read .env DEGRADE_* settings

### "LIVE_OK.txt not found"
- Create it: `echo. > ./data/LIVE_OK.txt`
- This file must exist to run REAL mode
- Manual confirmation of understanding risks

## Recommended Workflow

1. **Week 1-2: Test Phase**
   ```bash
   RUN_LIVE_SIM.bat          # Run 40+ hours in paper mode
   RUN_DIAG_REPLAY.bat       # Review decision quality
   RUN_HEALTHCHECK.bat       # Verify connectivity
   ```

2. **Week 3: Validation**
   - Backtest 2-3 months of history
   - Confirm backtest matches live-sim results
   - Review all risk settings in .env

3. **Week 4: Real Mode** (if everything looks good)
   ```bash
   echo. > ./data/LIVE_OK.txt           # Enable real mode
   # Update .env: LIVE_MODE=REAL
   RUN_LIVE_REAL.bat                   # Start with SMALL position size
   ```

## Key Differences: SIM vs REAL

| Feature | SIM | REAL |
|---------|-----|------|
| Money at risk | No | YES |
| Requires LIVE_OK.txt | No | YES |
| Fill quality | Simulated | Actual |
| Spread | Configurable | Market |
| Slippage | Configurable | Actual |
| Circuit breaker | Same | Same |
| Logging | Same | Same |
| Replay tools | Same | Same |

## Configuration Templates

### CONSERVATIVE (Recommended for starters)
```ini
LIVE_MODE=SIM              # Test in SIM first!
DAILY_LOSS_LIMIT=100
MAX_TRADES_PER_DAY=3
MAX_TRADES_PER_HOUR=1
COOLDOWN_SECONDS=300
DEGRADE_STEPS=3
DAILY_PROFIT_TARGET=200
```

### MODERATE (After validation)
```ini
LIVE_MODE=REAL
DAILY_LOSS_LIMIT=500
MAX_TRADES_PER_DAY=10
MAX_TRADES_PER_HOUR=2
COOLDOWN_SECONDS=180
DEGRADE_STEPS=2
DAILY_PROFIT_TARGET=1000
```

### AGGRESSIVE (Not recommended without experience)
```ini
LIVE_MODE=REAL
DAILY_LOSS_LIMIT=2000
MAX_TRADES_PER_DAY=20
MAX_TRADES_PER_HOUR=5
COOLDOWN_SECONDS=60
DEGRADE_STEPS=1
DAILY_PROFIT_TARGET=0
```

## Integration with V3

V4 execution layer works seamlessly with V3 learning:

```
V3 Components (Learning)    V4 Components (Execution)
───────────────────────────────────────────────────────
MetaBrain                   ExecutionEngine
│ Evaluates brains  ──────> │ Applies weights
│ Adjusts weights           │ Checks risk
│ Generates decision        │ Routes to MT5/SIM
│                           │ Logs audit trail
RegimeDetector              FillModel
│ Detects market regime  ──> │ Realistic fills
│ Adjusts strategy           │ Slippage simulation
                           
RLLearner                   RiskManager
│ Learns ENTER/SKIP  ──────> │ Circuit breakers
│ Q-values                   │ Position degrading
│ Policy entropy             │ Daily limits

SelfDiagnosis              PositionTracker
│ System health  ──────────> │ Position state
│ GREEN/YELLOW/RED           │ Reconciliation
```

## V4 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      BossBrain (V1/V2/V3)                   │
│              (Generates trading decision)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    ExecutionEngine (V4)                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. RiskManager: Check limits, circuit breakers       │  │
│  │ 2. FillModel: Estimate realistic fill price          │  │
│  │ 3. OrderRouter: Place order (SIM or MT5)             │  │
│  │ 4. PositionTracker: Update position state            │  │
│  │ 5. AuditSystem: Log all data                         │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
     ┌─────────────┐           ┌──────────────┐
     │  RouterSIM  │           │ RouterMT5    │
     │ (Paper)     │           │ (Live)       │
     └─────────────┘           └──────────────┘
```

## Important Notes

1. **V4 is ADDITIVE**: Doesn't break V1/V2/V3 functionality
2. **Default SAFE**: Starts in SIM mode, requires manual action for REAL
3. **Fully LOGGED**: Every decision, order, event is saved
4. **RECOVERABLE**: Replay tools for diagnostics
5. **CONFIGURABLE**: All limits adjustable via .env

## Support

- Documentation: See README.md V4 section
- Audit logs: `./data/db/trading.db`
- Error logs: `./data/logs/app.log`
- Checklist: `V4_SECURITY_CHECKLIST.txt`
- Examples: `.env.example` (copy to `.env`)

---

**Last Updated**: 2026-01-27
**Version**: V4.0 - Production Ready
**Status**: ✅ Ready for live trading (with proper setup)
