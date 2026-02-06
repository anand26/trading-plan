# TQQQ/SQQQ Pairs Ratio Strategy v4.0

## What It Does

Trades the **price ratio** of TQQQ (3× Long Nasdaq) and SQQQ (3× Short Nasdaq) using **Z-score mean reversion**, gated by a **daily QQQ trend filter**.

It does **not** predict market direction. It bets on which ETF is *relatively cheap* at any given moment, expecting the ratio to revert to its rolling mean — but **only when the macro trend allows it**.

---

## Instruments

| Symbol | Role |
|--------|------|
| **TQQQ** | 3× Long QQQ — bought when ratio is low (TQQQ is cheap) |
| **SQQQ** | 3× Short QQQ — bought when ratio is high (SQQQ is cheap) |
| **QQQ** | Trend filter only — 50/200-day SMA determines regime |

All positions are **long-only** (never shorts either ETF). **Intraday only** — flat by end of day.

---

## Signal: Z-Score of Price Ratio

```
ratio   = TQQQ_close / SQQQ_close          (computed on configurable-period bars)
mean    = average of last N ratios          (N = zscore_lookback, default 46)
stdev   = population std dev of last N      (matches TradingView ta.stdev)
Z-score = (current_ratio - mean) / stdev
```

---

## Trend Filter (QQQ Daily SMA Gate)

QQQ minute data is consolidated to daily bars. 50-day and 200-day SMAs are computed.

| Regime | Condition | Allowed Entries |
|--------|-----------|-----------------|
| **Uptrend** | QQQ > SMA50 **and** QQQ > SMA200 | TQQQ only |
| **Downtrend** | QQQ < SMA50 **and** QQQ < SMA200 | SQQQ only |
| **Neutral** | QQQ between the two SMAs | Both TQQQ and SQQQ |
| **Unknown** | SMAs not ready (warmup) | No trades |

**Why?** Without this filter, the algo repeatedly buys TQQQ during crashes (like COVID 2020) and SQQQ during bull runs — generating strings of losses. This was the #1 source of the 38% max drawdown in 7-year backtests.

---

## Entry Conditions (ALL must be true)

| # | Gate | Detail |
|---|------|--------|
| 1 | **Flat** | No open position |
| 2 | **Trading hours** | 9:35 AM – 3:45 PM ET |
| 3 | **Cooldown** | ≥ `min_bars_between` bars (default 6 × bar period) since last trade |
| 4 | **Daily trade limit** | < 10 trades today |
| 5 | **No daily halt** | Daily loss hasn't exceeded limit |
| 6 | **Trend allows it** | Regime is not UNKNOWN, and direction matches trend |
| 7 | **Ratio history built** | ≥ zscore_lookback bars of ratio data |

### Buy TQQQ
- Z-score < **−2.0** (ratio is abnormally low → TQQQ is cheap)
- Trend regime is **Uptrend** or **Neutral**

### Buy SQQQ
- Z-score > **+2.0** (ratio is abnormally high → SQQQ is cheap)
- Trend regime is **Downtrend** or **Neutral**

---

## Exit Conditions (checked in priority order)

| Priority | Exit Type | Condition | Why |
|----------|-----------|-----------|-----|
| 1 | **% Stop loss** | P&L < −2% from entry | Hard safety stop 🛑 |
| 2 | **Z-score stop** | TQQQ: Z < −3.0 / SQQQ: Z > +3.0 | Spread diverging further 🛑 |
| 3 | **Take profit** | P&L ≥ `take_profit_pct` (if > 0) | Lock in gains at target 💰 |
| 4 | **Trailing stop** | Activated at `trailing_activation_pct` gain, then exits if price drops `trailing_stop_pct` from HWM | Let winners run, protect gains 📈 |
| 5 | **Z-score normalized** | TQQQ: Z > −0.32 / SQQQ: Z < +0.32 — **only if trailing stop is NOT active** | Mean reversion complete ✅ |
| 6 | **Max hold time** | Exceeded N minutes (disabled when = 0) | Anti-stuck protection |
| 7 | **EOD close** | 3:50 PM ET (scheduled) | No overnight risk 🌙 |

### Trailing Stop Mechanics (v4.0)

```
On each bar while in position:
  1. Update high_water_price = max(high_water_price, current_price)
  2. If NOT active AND pnl_pct >= trailing_activation_pct:
       → Activate trailing stop, log HWM
  3. If active AND (high_water_price - current_price) / high_water_price >= trailing_stop_pct:
       → EXIT (trailing stop hit)
  4. While trailing stop IS active:
       → Z-score normalization exit is SUPPRESSED (let winners run)
```

**Key insight:** Without the trailing stop, Z-score normalization exits winners at ~$236 average while losers average $387. The trailing stop keeps you in when the trade is running and only exits on a pullback from the high.

---

## Risk Management

| Control | Detail |
|---------|--------|
| **Daily loss halt** | If cumulative daily P&L loss > 2% of NAV → stop all trading for the day |
| **Drawdown mode** | If equity drops > 25% from peak → position size cut by 50% until new equity high |
| **Vol scaling** | *(optional, off by default)* — uses QQQ 20-day ATR% to reduce size in high-vol regimes. Thresholds: >2.5% ATR → 0.44×, >1.5% ATR → 0.70× |
| **Max daily trades** | 10/day cap to prevent overtrading |
| **Cooldown** | `min_bars_between` bars minimum between consecutive trades (default 6 bars = 30 min @ 5-min bars) |
| **EOD flatten** | All positions liquidated at 3:50 PM — zero overnight exposure |

---

## Position Sizing

- **Base size**: 57% of portfolio (configurable via `position-size`)
- **Drawdown mode**: Base × 50% (configurable via `drawdown-position-scale`)
- **Vol scaling** *(when enabled)*: Further reduced based on QQQ ATR% thresholds (fixed in v4.0 — was 30/20%, never triggered; now 2.5/1.5%)
- **Single position**: Only one position at a time (must be flat to enter)
- **No pyramiding**: Full size in, full size out

---

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Z-Score** | | |
| `zscore-lookback` | 46 | Rolling window for Z-score (in bar-period units) |
| `entry-zscore` | 2.0 | Enter when \|Z\| exceeds this *(was 1.5 in v3.1)* |
| `exit-zscore` | 0.32 | Exit when \|Z\| drops below this (if trailing stop not active) |
| `stop-zscore` | 3.0 | Emergency exit if spread diverges |
| **Timing** | | |
| `bar-period-minutes` | 5 | Consolidation bar period: 5, 15, or 30 min *(new in v4.0)* |
| `min-bars-between` | 6 | Minimum bars between trades *(was 3 in v3.1)* |
| `max-hold-minutes` | 0 | Max hold time in minutes (0 = no limit, intraday close) |
| **Position & Risk** | | |
| `position-size` | 0.57 | Base position size (% of NAV) |
| `stop-loss-pct` | 0.02 | Hard stop loss (2%) |
| **Profit Taking** | | |
| `take-profit-pct` | 0.0 | Take profit target, 0 = disabled *(new in v4.0)* |
| `trailing-activation-pct` | 0.01 | Activate trailing stop at this gain (1%) *(new in v4.0)* |
| `trailing-stop-pct` | 0.0 | Trail width from HWM, 0 = disabled *(new in v4.0)* |
| **Trend Filter** | | |
| `trend-filter-enabled` | true | Enable QQQ 50/200 SMA gate |
| `sma-fast-period` | 50 | Fast SMA period (days) |
| `sma-slow-period` | 200 | Slow SMA period (days) |
| **Risk Controls** | | |
| `daily-loss-limit-pct` | 0.02 | Halt trading if daily loss > this |
| `max-drawdown-pct` | 0.25 | Enter drawdown mode above this |
| `drawdown-position-scale` | 0.50 | Position scale in drawdown mode |
| **Vol Scaling** | | |
| `enable-vol-scaling` | false | Enable ATR-based position scaling |
| `vol-scale-high-thresh` | 2.5 | High-vol ATR% threshold *(was 30.0, never triggered)* |
| `vol-scale-med-thresh` | 1.5 | Med-vol ATR% threshold *(was 20.0, never triggered)* |
| `vol-scale-high-factor` | 0.44 | Position multiplier in high vol |
| `vol-scale-med-factor` | 0.70 | Position multiplier in med vol |
| **Other** | | |
| `warmup-days` | 210 | Days to warm up indicators |

---

## Data Flow

```
QQQ Minute Data ──→ Daily Consolidator ──→ 50/200 SMA ──→ Trend Regime
                                                              │
TQQQ Minute ──→ N-min Consolidator ──┐                       │
                (configurable)       ├──→ Ratio ──→ Z-score ──→ Entry/Exit
SQQQ Minute ──→ N-min Consolidator ──┘                          Signals
                                                                  │
                                                              Position
                                                              Manager
                                                             ┌────┴────┐
                                                        Trailing    Take
                                                          Stop    Profit
                                                             └────┬────┘
                                                          Alpaca Broker
```

---

## v5.0 Backtest Variations (32 runs)

### Summary by Category

| # | Category | Variations | What It Tests |
|---|----------|------------|---------------|
| 1 | **Baseline** | v5.0 defaults, v4.0 old defaults | Isolate impact of entry=2.0 + bars=6 |
| 2 | **Take Profit Only** | TP 2%, 3%, 5% | Does capping upside help or hurt? |
| 3 | **Trailing Stop Only** | 5 configurations: activate 0.5–2%, trail 0.3–1% | Find the right trail width for 3x ETFs |
| 4 | **TP + Trailing Combo** | TP 3%+trail 0.5%, TP 5%+trail 1% | Cap + trail — best of both? |
| 5 | **15-min Bars** | Baseline, +trail, +TP, +faster re-entry | Less noise, fewer trades, wider moves? |
| 6 | **30-min Bars** | Baseline, +trail, +TP+faster re-entry | Even fewer, larger signals |
| 7 | **Entry Threshold** | Z=1.5, 2.0, 2.5 (all with trail 0.5%) | Trade frequency vs edge per trade |
| 8 | **Re-entry Spacing** | bars=4, 6, 8, 10 (all with trail 0.5%) | Optimal cooldown between trades |
| 9 | **Vol Scaling ON** | 5-min + trail, 15-min + trail | Do fixed thresholds (2.5/1.5%) add value? |
| 10 | **Exit Z-score** | 0.25 (tight), 0.32 (base), 0.40 (wide) | When does trailing make exit-zscore irrelevant? |
| 11 | **Stop Loss Width** | 1.5%, 2%, 2.5% (all with trail 0.5%) | Tighter vs looser hard stop |
| 12 | **Lookback Sweep** | LB=48 (best from v4) + trail | Confirm lookback=48 advantage persists |
| 13 | **Best Combo Candidate** | LB=48 + 15min + TP3% + trail 1% | Kitchen sink — best guess |

### Full Backtest Grid

| Row | entry_Z | bars_between | bar_period | TP% | trail_act% | trail% | vol_scale | other | notes |
|-----|---------|-------------|-----------|-----|-----------|--------|-----------|-------|-------|
| 1 | 2.0 | 6 | 5 | — | — | — | OFF | | **v5.0 BASELINE** |
| 2 | 1.5 | 3 | 5 | — | — | — | OFF | | v4.0 old defaults (comparison) |
| 3 | 2.0 | 6 | 5 | 2% | — | — | OFF | | Take profit 2% |
| 4 | 2.0 | 6 | 5 | 3% | — | — | OFF | | Take profit 3% |
| 5 | 2.0 | 6 | 5 | 5% | — | — | OFF | | Take profit 5% |
| 6 | 2.0 | 6 | 5 | — | 0.5% | 0.3% | OFF | | Tight trail |
| 7 | 2.0 | 6 | 5 | — | 1% | 0.5% | OFF | | Medium trail |
| 8 | 2.0 | 6 | 5 | — | 1% | 0.7% | OFF | | Wider trail |
| 9 | 2.0 | 6 | 5 | — | 1.5% | 1% | OFF | | Wide trail |
| 10 | 2.0 | 6 | 5 | — | 2% | 1% | OFF | | Late activation trail |
| 11 | 2.0 | 6 | 5 | 3% | 1% | 0.5% | OFF | | **Combo: TP + trail** |
| 12 | 2.0 | 6 | 5 | 5% | 1.5% | 1% | OFF | | Combo: big TP + trail |
| 13 | 2.0 | 6 | **15** | — | — | — | OFF | | 15-min baseline |
| 14 | 2.0 | 6 | **15** | — | 1% | 0.5% | OFF | | 15-min + trail |
| 15 | 2.0 | 6 | **15** | 3% | — | — | OFF | | 15-min + TP |
| 16 | 2.0 | 4 | **15** | — | 1% | 0.5% | OFF | | 15-min + trail + fast re-entry |
| 17 | 2.0 | 6 | **30** | — | — | — | OFF | | 30-min baseline |
| 18 | 2.0 | 6 | **30** | — | 1% | 0.7% | OFF | | 30-min + trail |
| 19 | 2.0 | 4 | **30** | 3% | — | — | OFF | | 30-min + TP + fast re-entry |
| 20 | **1.5** | 6 | 5 | — | 1% | 0.5% | OFF | | Lower entry + trail |
| 21 | **2.5** | 6 | 5 | — | 1% | 0.5% | OFF | | Higher entry + trail |
| 22 | 2.0 | **4** | 5 | — | 1% | 0.5% | OFF | | Fast re-entry + trail |
| 23 | 2.0 | **8** | 5 | — | 1% | 0.5% | OFF | | Slow re-entry + trail |
| 24 | 2.0 | **10** | 5 | — | 1% | 0.5% | OFF | | Very slow re-entry + trail |
| 25 | 2.0 | 6 | 5 | — | 1% | 0.5% | **ON** | | Vol scaling ON |
| 26 | 2.0 | 6 | **15** | — | 1% | 0.5% | **ON** | | Vol scaling + 15-min |
| 27 | 2.0 | 6 | 5 | — | 1% | 0.5% | OFF | exit=0.25 | Tighter exit Z |
| 28 | 2.0 | 6 | 5 | — | 1% | 0.5% | OFF | exit=0.40 | Wider exit Z |
| 29 | 2.0 | 6 | 5 | — | 1% | 0.5% | OFF | stop=1.5% | Tighter hard stop |
| 30 | 2.0 | 6 | 5 | — | 1% | 0.5% | OFF | stop=2.5% | Wider hard stop |
| 31 | 2.0 | 6 | 5 | — | 1% | 0.5% | OFF | LB=48 | Best lookback from v4 |
| 32 | 2.0 | 6 | **15** | 3% | 1.5% | 1% | OFF | LB=48 | **BEST COMBO candidate** |

---

## Version History

| Version | Changes |
|---------|---------|
| **v3.0** | Initial pairs Z-score strategy. No trend filter. |
| **v3.1** | Added: Raw data normalization fix, QQQ 50/200 SMA trend filter, daily drawdown circuit breaker, equity drawdown mode, configurable vol-scaling, pstdev fix for Pine Script parity. |
| **v4.0** | **Structural overhaul:** (1) Fixed vol scaling thresholds 30/20% → 2.5/1.5% ATR (actually trigger now), (2) Added trailing stop + take profit exits with smart priority (trailing suppresses Z-normalization to let winners run), (3) Raised entry threshold 1.5 → 2.0 and min bars 3 → 6 to reduce trade frequency, (4) Configurable bar period (5/15/30 min). Hard stop promoted to exit priority #1. |
