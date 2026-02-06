# TQQQ/SQQQ Pairs Ratio Strategy v3.1

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
ratio   = TQQQ_close / SQQQ_close          (computed on 5-minute bars)
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
| 3 | **Cooldown** | ≥ 3 bars (15 min) since last trade |
| 4 | **Daily trade limit** | < 10 trades today |
| 5 | **No daily halt** | Daily loss hasn't exceeded limit |
| 6 | **Trend allows it** | Regime is not UNKNOWN, and direction matches trend |
| 7 | **Ratio history built** | ≥ zscore_lookback bars of ratio data |

### Buy TQQQ
- Z-score < **−1.5** (ratio is abnormally low → TQQQ is cheap)
- Trend regime is **Uptrend** or **Neutral**

### Buy SQQQ
- Z-score > **+1.5** (ratio is abnormally high → SQQQ is cheap)
- Trend regime is **Downtrend** or **Neutral**

---

## Exit Conditions (checked in priority order)

| Priority | Exit Type | Condition | Why |
|----------|-----------|-----------|-----|
| 1 | **Z-score normalized** | TQQQ: Z > −0.32 / SQQQ: Z < +0.32 | Mean reversion complete ✅ |
| 2 | **Z-score stop** | TQQQ: Z < −3.0 / SQQQ: Z > +3.0 | Spread diverging further 🛑 |
| 3 | **% Stop loss** | P&L < −2% from entry | Hard safety stop 🛑 |
| 4 | **Max hold time** | Exceeded N minutes (disabled when = 0) | Anti-stuck protection |
| 5 | **EOD close** | 3:50 PM ET (scheduled) | No overnight risk 🌙 |

---

## Risk Management

| Control | Detail |
|---------|--------|
| **Daily loss halt** | If cumulative daily P&L loss > 2% of NAV → stop all trading for the day |
| **Drawdown mode** | If equity drops > 25% from peak → position size cut by 50% until new equity high |
| **Vol scaling** | *(optional, off by default)* — uses QQQ 20-day ATR to reduce size in high-vol regimes |
| **Max daily trades** | 10/day cap to prevent overtrading |
| **Cooldown** | 15 min minimum between consecutive trades |
| **EOD flatten** | All positions liquidated at 3:50 PM — zero overnight exposure |

---

## Position Sizing

- **Base size**: 57% of portfolio (configurable via `position-size`)
- **Drawdown mode**: Base × 50% (configurable via `drawdown-position-scale`)
- **Vol scaling** *(when enabled)*: Further reduced based on QQQ ATR thresholds
- **Single position**: Only one position at a time (must be flat to enter)
- **No pyramiding**: Full size in, full size out

---

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `zscore-lookback` | 46 | Rolling window for Z-score (5-min bars) |
| `entry-zscore` | 1.5 | Enter when \|Z\| exceeds this |
| `exit-zscore` | 0.32 | Exit when \|Z\| drops below this |
| `stop-zscore` | 3.0 | Emergency exit if spread diverges |
| `position-size` | 0.57 | Base position size (% of NAV) |
| `stop-loss-pct` | 0.02 | Hard stop loss (2%) |
| `trend-filter-enabled` | true | Enable QQQ 50/200 SMA gate |
| `sma-fast-period` | 50 | Fast SMA period (days) |
| `sma-slow-period` | 200 | Slow SMA period (days) |
| `daily-loss-limit-pct` | 0.02 | Halt trading if daily loss > this |
| `max-drawdown-pct` | 0.25 | Enter drawdown mode above this |
| `enable-vol-scaling` | false | Enable ATR-based position scaling |
| `warmup-days` | 210 | Days to warm up indicators |

---

## Data Flow

```
QQQ Minute Data ──→ Daily Consolidator ──→ 50/200 SMA ──→ Trend Regime
                                                              │
TQQQ Minute ──→ 5-min Consolidator ──┐                       │
                                     ├──→ Ratio ──→ Z-score ──→ Entry/Exit
SQQQ Minute ──→ 5-min Consolidator ──┘                          Signals
                                                                  │
                                                              Position
                                                              Manager
                                                                  │
                                                          Alpaca Broker
```

---

## Version History

| Version | Changes |
|---------|---------|
| **v3.0** | Initial pairs Z-score strategy. No trend filter. |
| **v3.1** | Added: Raw data normalization fix, QQQ 50/200 SMA trend filter, daily drawdown circuit breaker, equity drawdown mode, configurable vol-scaling, pstdev fix for Pine Script parity. |
