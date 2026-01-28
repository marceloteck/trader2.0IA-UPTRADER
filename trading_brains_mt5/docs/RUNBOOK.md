"""
RUNBOOK.md - Operations Guide for Trading Brains MT5 V5

This document provides troubleshooting procedures, error codes, and recovery steps.
"""

# RUNBOOK - Trading Brains MT5 V5

## Quick Reference: Common MT5 Return Codes

| Code | Name | Meaning | Action |
|------|------|---------|--------|
| 10009 | TRADE_RETCODE_DONE | Order executed successfully | None (expected) |
| 10010 | TRADE_RETCODE_DONE_PARTIAL | Partial execution | Monitor for rest |
| 10011 | TRADE_RETCODE_DENIED | Order denied | Check balance, margin, hours |
| 10012 | TRADE_RETCODE_EXPIRED | Order expired | Retry |
| 10013 | TRADE_RETCODE_INVALID | Invalid request | Check parameters |
| 10014 | TRADE_RETCODE_INVALID_VOLUME | Invalid volume | Check lot size |
| 10015 | TRADE_RETCODE_INVALID_PRICE | Invalid price | Check bid/ask |
| 10016 | TRADE_RETCODE_INVALID_STOPS | Invalid SL/TP | Adjust levels |
| 10017 | TRADE_RETCODE_TRADE_DISABLED | Trading disabled | Check market hours |
| 10018 | TRADE_RETCODE_MARKET_CLOSED | Market closed | Wait for market open |
| 10019 | TRADE_RETCODE_NO_MONEY | Insufficient funds | Check balance |
| 10020 | TRADE_RETCODE_PRICE_CHANGED | Price moved | Retry with new price |
| 10021 | TRADE_RETCODE_PRICE_OFF | Price outside limits | Adjust limits |
| 10022 | TRADE_RETCODE_INVALID_EXPIRATION | Bad expiration | Check time |
| 10023 | TRADE_RETCODE_ORDER_CHANGED | Order changed | Retry |
| 10024 | TRADE_RETCODE_TOO_MANY_REQUESTS | Rate limited | Back off and retry |
| 10025 | TRADE_RETCODE_NO_CHANGES | No changes in request | Remove duplicates |
| 10026 | TRADE_RETCODE_SERVER_DISABLES_AT | Server disabled AT | Use market orders |
| 10027 | TRADE_RETCODE_CLIENT_DISABLES_AT | Client disabled AT | Check settings |
| 10028 | TRADE_RETCODE_LOCKED | Position locked | Wait for release |
| 10029 | TRADE_RETCODE_FROZEN | Account frozen | Contact broker |
| 10030 | TRADE_RETCODE_ONLY_CLOSES | Only close allowed | Close positions first |
| 10031 | TRADE_RETCODE_HEDGE_PROHIBITED | Hedging prohibited | Use netting |
| 10032 | TRADE_RETCODE_SYMBOL_UNAVAIL | Symbol unavailable | Wait for data |

## Error Scenarios and Recovery

### 1. MT5 Connection Lost

**Symptoms:**
- "MT5 not connected" in logs
- Orders failing with TRADE_RETCODE_DENIED
- No price updates

**Steps:**
```bash
# 1. Check MT5 terminal manually
# 2. Run health check
RUN_HEALTHCHECK.bat

# 3. If health check fails:
# - Restart MT5 terminal
# - Restart Expert Advisors
# - Check symbol in Market Watch

# 4. Resume trading
RUN_LIVE_SIM.bat  # or RUN_PRODUCTION.bat
```

### 2. Stale Data (No New Candles)

**Symptoms:**
- Last candle unchanged for > STALE_DATA_MINUTES
- Indicators flat-lining
- Loop runs but no decisions

**Steps:**
```bash
# 1. Check MT5 Market Watch
# - Ensure symbol is in watch list
# - Verify trading hours are active

# 2. Check bars count
# - Open MT5 Data Window
# - Look at EURUSD H1 (or your symbol) - should show recent bars

# 3. Force reconnect
# - Close MT5 terminal
# - Delete "Terminal*.tab" from AppData\Roaming\MetaQuotes\Terminal\*\
# - Restart MT5

# 4. Resume
RUN_PRODUCTION.bat
```

### 3. Insufficient Margin/Balance

**Symptoms:**
- Orders fail with TRADE_RETCODE_NO_MONEY (10019)
- System enters PAUSE mode
- Risk Manager circuit breaker triggered

**Steps:**
```bash
# 1. Check account balance in MT5
# 2. Verify risk parameters in .env
# - Reduce RISK_PER_TRADE if needed
# 3. Deposit additional funds (if live account)
# 4. Resume:
RUN_LIVE_SIM.bat
```

### 4. Daily Loss Limit Hit

**Symptoms:**
- "Daily loss limit triggered" in logs
- No new orders placed
- System in PAUSE until next day

**Steps:**
```bash
# 1. This is INTENTIONAL safety behavior
# 2. Review daily report
# - RUN_MAINTENANCE.bat
# - Select option 5 (daily report)
# 3. Analyze why losses occurred
# 4. System resumes next trading day automatically
```

### 5. Database Corruption

**Symptoms:**
- SQLite3 errors in logs
- "database disk image malformed"
- Audit trail queries fail

**Steps:**
```bash
# 1. STOP trading immediately
# 2. Check integrity
RUN_MAINTENANCE.bat
# Select option 1

# 3. If corrupted:
# - Navigate to data/db/backups/
# - Find latest backup: trading_YYYYMMDD_HHMMSS.db
# - Copy to data/db/trading.db

# 4. Resume
RUN_PRODUCTION.bat
```

### 6. Position Not Closed on MT5

**Symptoms:**
- PositionTracker shows CLOSED but MT5 still open
- P&L mismatch
- Divergence detected in logs

**Steps:**
```bash
# 1. Check MT5 Positions manually
# 2. If position exists in MT5:
#   a. Close manually in MT5 Terminal
#   b. System will detect reconcile on next loop
#   c. Log entry to divergence_log.txt

# 3. If position gone from MT5:
#   a. System auto-closed (likely market movement)
#   b. PositionTracker reconcile will update state

# 4. Check audit trail
# - data/exports/reports/
# - Look for divergence records
```

### 7. System Watchdog Timeout

**Symptoms:**
- Loop hasn't updated in > WATCHDOG_TIMEOUT seconds
- Process not responding
- CPU usage high or zero

**Steps:**
```bash
# 1. This triggers automatic restart
# - Log entry: "Watchdog timeout - restarting"
# 2. Check logs for what caused hang
#   - data/logs/app.log (recent entries)
# 3. If happens frequently:
#   a. Increase WATCHDOG_TIMEOUT in settings.py
#   b. Check for infinite loops in brain code
#   c. Review MT5 lag (Check->Settings->Expert Advisors)
```

## Manual Operations

### Create Manual Backup

```bash
RUN_MAINTENANCE.bat
# Select option 2
# Or run: python -m src.main backup-db
```

### Generate Report

```bash
RUN_MAINTENANCE.bat
# Select option 5 (daily) or 6 (weekly)

# OR directly:
# python -m src.main daily-report
# python -m src.main weekly-report
```

### Check System Health

```bash
RUN_HEALTHCHECK.bat

# Checks:
# ✓ Python environment
# ✓ Database accessibility
# ✓ MT5 connection
# ✓ Symbol availability
# ✓ Configuration validity
```

### Pause/Resume Trading

**Pause (no new orders, but monitor positions):**
```bash
echo. > data/PAUSE.txt
# Delete file to resume
```

**Stop (hard exit):**
```bash
echo. > data/STOP.txt
# System exits cleanly, flushes DB
```

## Daily Operations Checklist

- [ ] 08:00 - Start system: `RUN_PRODUCTION.bat`
- [ ] 12:00 - Check watchdog status (in logs)
- [ ] 16:00 - Verify no stuck orders (dashboard or MT5)
- [ ] 20:00 - Review circuit breaker alerts (if any)
- [ ] 22:00 - Run maintenance: `RUN_MAINTENANCE.bat`
- [ ] 22:30 - Check daily report: `data/exports/reports/YYYY-MM-DD_summary.txt`

## Weekly Operations Checklist

- [ ] Monday - Review week metrics
- [ ] Generate weekly report: `RUN_MAINTENANCE.bat` → option 6
- [ ] Check database size: `data/db/` should not exceed 500 MB
- [ ] Verify backups exist: `data/db/backups/` should have 7+ backups
- [ ] Review error codes in logs
- [ ] Adjust risk parameters if needed

## Escalation Procedure

### Level 1: Auto-Recovery (System Handles)
- Watchdog timeout → Restart process
- Stale data → Retry bar fetch
- Single order failure → Retry with back-off
- MT5 disconnect → Auto-reconnect (up to 60 seconds)

### Level 2: Semi-Automatic (Log Alert + Pause)
- Database corruption → Log error, pause trading
- Daily loss limit → Pause until next day
- Margin exhaustion → Pause, wait for deposit
- Divergence detected → Log to DB, continue with monitoring

### Level 3: Manual Intervention Required
- Broker suspension of symbol
- System-wide MT5 failure (all symbols)
- Persistent corruption despite recovery
- Unusual market conditions (gap > 100 pips)

## Log Analysis

### Finding Errors in Real Time
```bash
# Watch live logs
tail -f data/logs/app.log | findstr "ERROR"

# Or on Windows (PowerShell)
Get-Content data/logs/app.log -Wait | Select-String "ERROR"
```

### Export Audit Trail for Failed Trade
```bash
# Via CLI
python -m src.main export-audit --from 2025-01-20 --to 2025-01-21

# Results in: data/exports/audit_YYYY-MM-DD.json
```

## Known Issues & Workarounds

### Issue: "stale data" warnings every 5 minutes
**Workaround:** Increase STALE_DATA_MINUTES in .env from 3 to 5

### Issue: Orders rejected with "invalid price"
**Workaround:** Increase FILL_MODEL_SPREAD_BASE to account for wider actual spreads

### Issue: Frequent reconnects to MT5
**Workaround:** Ensure MT5 Expert Advisors are enabled and Terminal is always on

## Performance Optimization

If system is slow:

1. **Reduce feature recalculation:**
   - Features cache should show > 80% hit rate
   - Check: Feature cache stats in dashboard

2. **Reduce indicator load:**
   - Only calculate MAs actually used
   - Disable unused timeframes

3. **Compress database:**
   ```bash
   RUN_MAINTENANCE.bat
   # Select option 3 (VACUUM)
   ```

4. **Archive old logs:**
   ```bash
   RUN_MAINTENANCE.bat
   # Select option 4 (rotate logs)
   ```

---

For further assistance, check:
- README.md - Architecture overview
- V4_QUICK_START.md - Configuration guide
- data/logs/app.log - Detailed system logs
- data/exports/reports/ - Daily/weekly analysis

