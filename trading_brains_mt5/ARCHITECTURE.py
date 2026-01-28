"""
Trading Brains MT5 V2 - Architecture Overview
Visual representation of the system flow
"""

# ============================================================================
# SYSTEM ARCHITECTURE V2
# ============================================================================

"""
┌──────────────────────────────────────────────────────────────────────────┐
│                           TRADING BRAINS MT5 V2                          │
│                          Architecture Diagram                            │
└──────────────────────────────────────────────────────────────────────────┘

LAYER 1: DATA INPUT
─────────────────────────────────────────────────────────────────────────
    ┌─────────────────┐
    │   MetaTrader5   │
    │   (Live Data)   │
    │                 │
    │ M1/M5/H1 Candles│
    │ + tick_volume   │
    └────────┬────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING LAYER                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  • VWAP Calculation          • High/Low Analysis                        │
│  • Moving Averages (20, 34,  • Pivot Points                            │
│    89, 200)                  • Regime Classification                    │
│  • RSI (14)                  • Liquidity Levels                         │
│  • ATR (14)                  • Round Levels                             │
│                                                                          │
│  OUTPUT: features = {close, vwap, rsi, atr, ma_*, pivot_*, regime}    │
└────────┬─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     BRAIN LAYER (10 Independent)                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐  ┌──────────────────────┐                     │
│  │ WyckoffRangeBrain   │  │ WyckoffAdvancedBrain │                     │
│  │                     │  │                      │                     │
│  │ Accumulation/Dist   │  │ Spring/Upthrust      │                     │
│  │ Range detection     │  │ + Touch decay        │                     │
│  └─────────────────────┘  └──────────────────────┘                     │
│                                                                          │
│  ┌─────────────────────┐  ┌──────────────────────┐                     │
│  │ TrendPullbackBrain  │  │ GiftBrain            │                     │
│  │                     │  │                      │                     │
│  │ MA crossover        │  │ Specific pattern     │                     │
│  │ Pullback to MA20    │  │ detection            │                     │
│  └─────────────────────┘  └──────────────────────┘                     │
│                                                                          │
│  ┌─────────────────────┐  ┌──────────────────────┐                     │
│  │ MomentumBrain       │  │ Consolidation90pts   │                     │
│  │                     │  │                      │                     │
│  │ RSI + Momentum      │  │ 90pt range squeeze   │                     │
│  │ divergences         │  │ breakout             │                     │
│  └─────────────────────┘  └──────────────────────┘                     │
│                                                                          │
│  ╔═════════════════════════════════════════════════════════════════╗   │
│  ║ V2 NEW BRAINS                                                 ║   │
│  ╠═════════════════════════════════════════════════════════════════╣   │
│  ║ ┌─────────────────────┐  ┌──────────────────────────────────┐ ║   │
│  ║ │ ElliottProbBrain    │  │ GannMacroBrain (H1 Macro Filter)│ ║   │
│  ║ │                     │  │                                 │ ║   │
│  ║ │ • 5-wave impulse    │  │ • MA50 vs MA200                 │ ║   │
│  ║ │ • ABC correction    │  │ • Macro zones (not prices)      │ ║   │
│  ║ │ • Divergences       │  │ • Trend filtering               │ ║   │
│  ║ │ • Multi-candidate   │  │ • Applied by BossBrain          │ ║   │
│  ║ └─────────────────────┘  └──────────────────────────────────┘ ║   │
│  ║                                                               ║   │
│  ║ ┌─────────────────────────┐  ┌─────────────────────────────┐ ║   │
│  ║ │ ClusterProxyBrain       │  │ LiquidityBrain              │ ║   │
│  ║ │                         │  │                             │ ║   │
│  ║ │ • Tick volume spike     │  │ • VWAP consolidation        │ ║   │
│  ║ │ • Candle absorption     │  │ • High/low day              │ ║   │
│  ║ │ • Level detection       │  │ • Pivot points              │ ║   │
│  ║ │ • Touch counting        │  │ • Round levels              │ ║   │
│  ║ │ • Feeds Liquidity       │  │ • From Cluster Proxy        │ ║   │
│  ║ └─────────────────────────┘  └─────────────────────────────┘ ║   │
│  ╚═════════════════════════════════════════════════════════════════╝   │
│                                                                          │
│  Each Brain outputs: BrainSignal(action, entry, sl, tp1, tp2, ...)     │
└─────────────────────┬──────────────────────────────────────────────────┘
                      │
                      │ Signals with scores
                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          BOSSBRAIN DECISION ENGINE                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  STEP 1: REGIME-AWARE WEIGHTING                                        │
│  ─────────────────────────────────                                     │
│  Adjust each signal score based on regime:                            │
│                                                                          │
│      Regime          Key Brains                  Multiplier             │
│      ──────────────  ─────────────────────────  ──────────             │
│      RANGE           Wyckoff*                    1.2x                   │
│      TREND_UP        TrendPullback               1.2x                   │
│      TREND_DOWN      TrendPullback               1.2x                   │
│      HIGH_VOL        Momentum                    1.1x                   │
│                                                                          │
│  STEP 2: CONFLUENCE GATE                                               │
│  ────────────────────────                                              │
│  Only enter if:                                                        │
│  • 2+ independent brains agree on direction, OR                        │
│  • 1 brain scores >= 85% + macro filter favorable                      │
│                                                                          │
│  STEP 3: MACRO FILTER (Gann H1)                                        │
│  ───────────────────────────────                                       │
│  • BUY: Not in resistance zone                                          │
│  • SELL: Not in support zone                                            │
│                                                                          │
│  STEP 4: RISK/REWARD CHECK                                             │
│  ────────────────────────────                                          │
│  • Minimum RR ratio: 1.2:1                                              │
│  • Reject if (TP1 - Entry) / (Entry - SL) < 1.2                        │
│                                                                          │
│  STEP 5: SPREAD CHECK                                                  │
│  ───────────────────                                                   │
│  • Current spread <= spread_max                                         │
│                                                                          │
│  STEP 6: POSITION SIZING                                               │
│  ──────────────────────                                                │
│  • size = (risk_per_trade * account_balance) /                         │
│           (SL_distance * point_value)                                   │
│  • Adjust to MIN_LOT / LOT_STEP                                         │
│                                                                          │
│  STEP 7: TARGET SELECTION (Liquidity)                                  │
│  ──────────────────────────────────                                    │
│  • TP1 = nearest liquidity level                                        │
│  • TP2 = next liquidity level                                           │
│                                                                          │
│  OUTPUT: Decision(action, entry, sl, tp1, tp2, size, reason)          │
└─────────────┬────────────────────────────────────────────────────────────┘
              │
              │ BUY/SELL/HOLD
              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       EXECUTION & PERSISTENCE LAYER                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   BACKTEST   │  │  LIVE SIM    │  │  LIVE REAL   │  │ DASHBOARD  │ │
│  │              │  │              │  │              │  │            │ │
│  │ • Historic   │  │ • Paper      │  │ • Real $$    │  │ • Monitor  │ │
│  │   data       │  │   trading    │  │ • 2x confirm │  │ • Placar   │ │
│  │ • Spread/    │  │ • Real-time  │  │ • Kill switch│  │ • Regime   │ │
│  │   slippage   │  │   sim        │  │ • Limits     │  │ • Risk     │ │
│  │   dynamic    │  │ • Fill model │  │ • Logging    │  │ • Levels   │ │
│  │ • MFE/MAE    │  │   match BT   │  │ • Order track│  │            │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │
│                                                                          │
│  All paths → SQLite Database (13 tables)                               │
│      ├─ candles          ├─ levels                                     │
│      ├─ features         ├─ metrics_windows                            │
│      ├─ brain_signals    ├─ regimes_log                                │
│      ├─ decisions        ├─ model_calibration                          │
│      ├─ trades           ├─ models                                     │
│      ├─ training_state   └─ order_events                               │
│      └─ runs                                                            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

LAYER 2: TRAINING (Walk-Forward)
─────────────────────────────────
    ┌────────────────────────────────────────┐
    │ Walk-Forward Windows                   │
    │                                        │
    │ Window 1: [Train 30d] → [Test 10d]    │
    │ Window 2: [Train 30d] → [Test 10d]    │
    │ Window 3: [Train 30d] → [Test 10d]    │
    │ ...                                    │
    │                                        │
    │ For each window:                       │
    │ • Train supervised models              │
    │ • Calibrate thresholds by regime/hour  │
    │ • Evaluate on test data                │
    │ • Save metrics_windows                 │
    └────────────────────────────────────────┘

LAYER 3: DASHBOARD API
──────────────────────
    GET  /status           (Status geral)
    GET  /signals          (Latest signals)
    GET  /trades           (Latest trades)
    GET  /metrics/latest   (Latest decision)
    ──── V2 NEW ENDPOINTS ────
    GET  /brains/scoreboard    (Brains placar)
    GET  /regime/current       (Current regime)
    GET  /levels/current       (Detected levels)
    GET  /risk/status          (P&L + risk)
    POST /control/kill         (Kill switch)

LAYER 4: SECURITY
─────────────────
    ✅ Live trading OFF by default
    ✅ Double confirmation (ENABLE_LIVE_TRADING=true + KEY)
    ✅ Kill switch (data/STOP.txt)
    ✅ Daily loss limit
    ✅ Max trades/day limit
    ✅ Max consecutive losses limit
    ✅ Spread checks
    ✅ Risk/Reward checks
"""

# ============================================================================
# DATA FLOW EXAMPLE
# ============================================================================

"""
TIME: 14:32 (M1 candle closes)

1. MT5 provides new candle:
   {time: 14:32, open: 125.50, high: 125.75, low: 125.40, close: 125.60, volume: 1500}

2. Features calculated:
   {close: 125.60, vwap: 125.55, rsi: 52, atr: 0.80, ma20: 125.30, regime: "trend_up"}

3. Brain signals generated (parallel):
   WyckoffAdv:     BUY  entry=125.60, sl=125.00, tp1=126.20, score=0.75
   Elliott:        SELL entry=125.60, sl=125.90, tp1=124.80, score=0.45 (wait for better)
   TrendPullback:  BUY  entry=125.60, sl=125.10, tp1=126.40, score=0.82
   Momentum:       HOLD (no clear momentum)
   Liquidity:      NEUTRAL (consolidation level)
   GannMacro:      BUY (H1 MA50 > MA200, uptrend macro)
   ...others

4. BossBrain decision:
   • Regime-weight: trend_up → TrendPullback 1.2x = 0.82 * 1.2 = 0.984
   • Top scores: WyckoffAdv=0.75, TrendPullback=0.984
   • Confluence: 2 brains (WyckoffAdv + TrendPullback) agree on BUY ✅
   • Macro filter: Gann macro uptrend ✅
   • RR: (126.20 - 125.60) / (125.60 - 125.00) = 1.0 - FAIL! < 1.2
   → DECISION: HOLD (wait for better RR)

5. Next candle (14:33):
   New candle extends higher → RR improves
   • RR: (126.40 - 125.65) / (125.65 - 125.10) = 1.37 ✅
   → DECISION: BUY
   
   Entry:  125.65 (with spread)
   SL:     125.05
   TP1:    126.25 (Liquidity level)
   TP2:    126.50
   Size:   0.5 contracts (based on risk)

6. Execution:
   If Backtest: Simulated fill at entry
   If Live Sim: Paper fill at entry
   If Live Real: Real order to MT5 (with logging)

7. Trade tracking:
   opened_at: 14:33
   entry: 125.65
   mfe: 1.2 (moved to 126.85)
   Eventually closes...
   closed_at: 14:58
   exit: 126.25 (TP1 hit)
   pnl: +0.60 points
   → All logged to SQLite

8. Dashboard updates:
   /brains/scoreboard: Latest signals from each brain
   /regime/current: "trend_up"
   /risk/status: 1 trade today, +0.60 pnl, max today +0.60
   /levels/current: Support @ 125.10, Resistance @ 126.50
"""

# ============================================================================
# REGIME CLASSIFICATION RULES
# ============================================================================

"""
Regime = f(recent_data):

    slope = MA20.slope (last 5 candles)
    atr   = ATR (last 5 candles)
    atr_pct = atr / close

    IF atr_pct > 1.0% of close:
        → REGIME = "high_vol"
    ELIF slope > 0:
        → REGIME = "trend_up"
    ELIF slope < 0:
        → REGIME = "trend_down"
    ELSE:
        → REGIME = "range"

Usage in BossBrain:
    for each brain_signal:
        base_score = brain.score(signal, context)
        weight = weights[brain_name] * regime_multiplier
        weighted_score = base_score * weight
"""

# ============================================================================
# CONFIDENCE SCORING LOGIC
# ============================================================================

"""
Elliott Probabilistic:
    - Each candidate Elliott pattern gets confidence 0.5-0.7
    - More candidates = more confluência = higher final score
    - Final brain score = confidence * 70 + bonus

Wyckoff Advanced:
    - Spring/Upthrust detection = 0.6-0.75 base
    - Decay -0.1 per touch > 2
    - Final = max(0.2, 0.75 - (touches - 2) * 0.1)

Gann Macro:
    - Trend clear (MA50 > MA200) = 0.75
    - Range/unclear = 0.40
    - Used as FILTER, not primary signal

All others:
    - Domain-specific scoring
    - Typically 40-85 range
"""

print(__doc__)
