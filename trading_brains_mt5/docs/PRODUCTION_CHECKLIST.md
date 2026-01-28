"""
PRODUCTION_CHECKLIST.md - Pre-Live and Operational Checklists
"""

# Production Checklist - Trading Brains MT5 V5

## PRE-DEPLOYMENT CHECKLIST (Before Going Live)

### Environment Setup
- [ ] Python 3.9+ installed and in PATH
- [ ] Virtual environment created (`venv/`)
- [ ] All requirements installed: `pip install -r requirements.txt`
- [ ] `.env` file created (use SETUP_WIZARD.bat)
- [ ] Database initialized: `python -m src.main init-db`

### MT5 Configuration
- [ ] MT5 terminal installed and running
- [ ] Account connected (live or demo)
- [ ] Symbol in Market Watch (EURUSD or your symbol)
- [ ] Trading hours verified (check Symbol Properties)
- [ ] Expert Advisors enabled in terminal
- [ ] No existing advisors interfering

### System Validation
- [ ] Health check passes: `RUN_HEALTHCHECK.bat`
- [ ] All tests pass: `RUN_TESTS.bat`
- [ ] Database integrity OK: `RUN_MAINTENANCE.bat` → option 1

### Risk Configuration
- [ ] Read and understand V4_SECURITY_CHECKLIST.txt
- [ ] RISK_PER_TRADE reasonable (1-2%)
- [ ] DAILY_LOSS_LIMIT reasonable (2-5%)
- [ ] MAX_TRADES_PER_DAY reasonable (10-20)
- [ ] Backup .env (save copy)

### Backtest Validation
- [ ] Backtest runs without error: `python -m src.main backtest`
- [ ] Backtest results logical (Sharpe > 0.5, DD < 30%)
- [ ] Walk-forward test passes: `python -m src.main walk-forward`
- [ ] Audit trail captured properly

### Paper Trading (MANDATORY - Min 8 hours)
- [ ] Paper trading duration: > 8 hours
- [ ] Watchdog heartbeat observed (logs show activity)
- [ ] Orders placed and filled correctly
- [ ] SL/TP levels working as expected
- [ ] Daily report generates successfully
- [ ] No errors or warnings in logs
- [ ] No divergence detected (position reconciliation OK)

### Final Review
- [ ] All documentation read
- [ ] Runbook procedures understood
- [ ] Emergency procedures reviewed (STOP.txt, PAUSE.txt)
- [ ] Backup procedure tested
- [ ] Restore procedure tested
- [ ] Management briefed on system behavior

---

## LIVE TRADING INITIATION CHECKLIST

### Activation Steps
- [ ] Create `data/LIVE_OK.txt` (manual confirmation)
  ```bash
  # On Windows:
  mkdir data
  echo. > data\LIVE_OK.txt
  ```
- [ ] Update `.env`: `LIVE_MODE=REAL`
- [ ] Verify live credentials in MT5 terminal
- [ ] Account has minimum funding (e.g., $1000+)
- [ ] Verify broker allows automated trading
- [ ] Read and accept risk disclaimer (below)

### Pre-Live Final Checks (Day Before)
- [ ] Run health check: `RUN_HEALTHCHECK.bat`
- [ ] Verify DB integrity: `RUN_MAINTENANCE.bat` → option 1
- [ ] Create backup: `RUN_MAINTENANCE.bat` → option 2
- [ ] Reset logs: Clear old log files
- [ ] Verify internet connection stability
- [ ] Test killswitch (STOP.txt creation)

### First Trading Session
- [ ] Start with reduced position size (50% of normal)
- [ ] Monitor first 30 minutes actively
- [ ] Verify orders place correctly in MT5
- [ ] Check fills match expected prices
- [ ] Monitor margin levels
- [ ] Verify SL/TP levels in MT5
- [ ] Check P&L tracking accuracy

### Ongoing Daily Checklist
- [ ] System started: `RUN_PRODUCTION.bat`
- [ ] No errors in logs within first hour
- [ ] At least one trade placed successfully
- [ ] Monitor during lunch/low liquidity hours
- [ ] Mid-day check: Watchdog running, positions OK
- [ ] Pre-close check: Review open positions
- [ ] EOD: Run maintenance, generate report
- [ ] Archive logs (weekly)

### Weekly Operational Checklist
- [ ] Weekly report generated and reviewed
- [ ] Total win rate > 45% (or target)
- [ ] Max consecutive losses < 3
- [ ] No database corruption
- [ ] All backups present
- [ ] No unusual error codes
- [ ] Risk parameters appropriate
- [ ] Margin utilization < 30%

### Post-Drawdown Protocol (If DD > 10%)

**Immediate Actions:**
- [ ] Review daily report that day
- [ ] Identify losing pattern
- [ ] Check circuit breaker status
  ```bash
  RUN_HEALTHCHECK.bat
  # Look for RISK_EVENT entries
  ```

**Analysis:**
- [ ] Review last 20 trades (audit trail)
- [ ] Check if regime changed
- [ ] Verify MT5 spreads increased
- [ ] Review brain scores distribution

**Decision:**
- [ ] Continue as-is (if all OK)
- [ ] Reduce position size temporarily
- [ ] Pause trading for manual review
- [ ] Adjust risk parameters

---

## DAILY OPERATIONS GUIDE

### Morning (Pre-Market)
```
08:00 - Start system
RUN_PRODUCTION.bat

08:05 - Initial verification
RUN_HEALTHCHECK.bat
# Should see: ✅ All systems OK

08:10 - Monitor first trades
# Watch logs: data/logs/app.log
# Should see order confirmations within 1-2 minutes
```

### Midday (Active Trading)
```
12:00 - Status check
# Review: data/logs/app.log
# Check for: ERROR, WARNING
# Expected: TRADE, RISK_EVENT (normal operation)

13:00 - Margin check
# MT5 Terminal: Account tab
# Should see: Margin usage < 30%

14:30 - No manual intervention needed
# System handles: SL/TP adjustments, circuit breakers
```

### Afternoon (Pre-Close)
```
16:00 - Peak hours status
# Verify: No stuck orders
# Check: Open position count reasonable

17:00 - Review approaching close
# MT5: Check overnight gaps (if applicable)
```

### Evening (Post-Market)
```
22:00 - End-of-day report
RUN_MAINTENANCE.bat
# Select: Option 5 (daily report)

22:30 - Review daily metrics
# Read: data/exports/reports/YYYY-MM-DD_summary.txt
# Look for: Total P&L, win rate, largest loss

23:00 - System readiness for next day
# Verify: No errors, watchdog OK
# Plan: Any adjustments needed?
```

---

## EMERGENCY PROCEDURES

### System Not Responding (Watchdog Timeout)

**Action:**
```bash
# 1. Kill any hanging Python processes
taskkill /F /IM python.exe

# 2. Restart
RUN_PRODUCTION.bat

# 3. Monitor logs
tail -f data/logs/app.log
```

### Orders Stuck in MT5

**Action:**
```bash
# 1. Create PAUSE file (prevents new orders)
echo. > data\PAUSE.txt

# 2. Manually close stuck orders in MT5 Terminal

# 3. Check PositionTracker state
python -c "from src.execution.position_tracker import PositionTracker; pt = PositionTracker('data/db/trading.db'); print(pt.get_all_positions())"

# 4. Delete PAUSE file to resume
del data\PAUSE.txt
```

### Database Corrupted

**Action:**
```bash
# 1. Stop trading immediately
echo. > data\STOP.txt

# 2. Restore from backup
RUN_MAINTENANCE.bat
# Select: Option 1 (integrity check)
# If fails, restore latest backup manually:
#   Copy data\db\backups\trading_LATEST.db -> data\db\trading.db

# 3. Restart
RUN_PRODUCTION.bat
```

### MT5 Connection Lost (> 60 seconds)

**Action:**
```bash
# 1. System will pause trading (safety)

# 2. Restart MT5 terminal

# 3. System auto-reconnects (wait up to 60s)

# 4. If still disconnected:
RUN_HEALTHCHECK.bat
# Debug output will show issue
```

### Account Margin Call

**Action:**
```bash
# 1. System triggers PAUSE automatically

# 2. Options:
#   a. Deposit funds to account
#   b. Reduce RISK_PER_TRADE in .env
#   c. Pause trading until manual review

# 3. Resume after fixing
RUN_PRODUCTION.bat
```

---

## SIGN-OFF AND ACKNOWLEDGMENT

By starting live trading, you acknowledge:

1. **Risk Understanding**
   - [ ] I understand trading risks and automated systems can fail
   - [ ] I accept potential loss of capital
   - [ ] I have read all risk documentation

2. **System Knowledge**
   - [ ] I understand each circuit breaker and its purpose
   - [ ] I know how to pause/stop the system
   - [ ] I understand the audit trail and can read logs

3. **Operational Readiness**
   - [ ] I am available to monitor system during trading hours
   - [ ] I have reliable internet connection
   - [ ] I have backup internet (phone hotspot, etc.)
   - [ ] I have tested all emergency procedures

4. **Financial Responsibility**
   - [ ] Account funding is from funds I can afford to lose
   - [ ] I am not using borrowed money
   - [ ] I understand leverage and margin calls
   - [ ] I have a business plan (not gambling)

### Authorization

I certify that I have completed all checklists and am prepared to operate this system in live mode.

**Operator Name:** _________________________________

**Date:** _________________________________

**Time:** _________________________________

**Signature:** _________________________________

---

## REFERENCE DOCUMENTS

- [README.md](../README.md) - System architecture
- [RUNBOOK.md](RUNBOOK.md) - Troubleshooting guide
- [V4_QUICK_START.md](../V4_QUICK_START.md) - Quick reference
- [V4_IMPLEMENTATION_COMPLETE.txt](../V4_IMPLEMENTATION_COMPLETE.txt) - Component details

## Support

For issues, consult:
1. RUNBOOK.md (error codes and recovery)
2. System logs: `data/logs/app.log`
3. Database audit trail: `data/db/trading.db` (SQL viewer)
4. Dashboard: `http://localhost:8000` (if running)

---

**V5 Production Ready** ✅
**Last Updated:** 2026-01-27
**Status:** STABLE

