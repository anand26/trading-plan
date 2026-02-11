# LEAN Data Provenance & Factor File Reference
## Last verified: 2026-02-09

---

## Data Source

**ALL minute data** for QQQ, TQQQ, SQQQ comes from **Alpha Vantage** intraday API.

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `function` | `TIME_SERIES_INTRADAY` | 1-min OHLCV |
| `adjusted` | `false` | **RAW as-traded prices** — splits ARE visible as price jumps |
| `extended_hours` | `false` | RTH only (9:30 AM – 4:00 PM ET) |
| `outputsize` | `full` | All bars for the month |
| `month` | `YYYY-MM` | Fetched month-by-month |
| API Key | Premium (75 calls/min) | `GJU4TDYFABLUSRT0` |

### Key Fact: `adjusted=false` IS Truly Raw
Despite the confusing name, Alpha Vantage `adjusted=false` returns **as-traded prices**
with splits visible. This was verified on 2026-02-09:

```
TQQQ 20120510→20120511: 101.48 → 50.67  ratio=2.00 (1:2 reverse split ✓)
TQQQ 20180523→20180524: 166.44 → 55.35  ratio=3.01 (1:3 reverse split ✓)
SQQQ 20120510→20120511:  12.29 → 49.21  ratio=0.25 (1:4 reverse split ✓)
```

### Previous Data Source (Databento) — REMOVED
Databento raw data was used from 2018-05 to 2026-01 but was **deleted on 2026-02-09**
and replaced with Alpha Vantage data to ensure a single consistent data source.
The Databento data included extended hours (pre/post market) bars which AV does not.

---

## Data Coverage

| Symbol | First Date | Last Date | Files | Source |
|--------|-----------|-----------|-------|--------|
| QQQ    | 20000103  | 20260209  | ~6,564 | Alpha Vantage |
| TQQQ   | 20100211  | 20260209  | ~4,023 | Alpha Vantage |
| SQQQ   | 20100211  | 20260209  | ~4,023 | Alpha Vantage |

**Location:** `quantconnect-lean/Data/equity/usa/minute/{symbol}/`

---

## LEAN Minute Data Format

```
File:   {YYYYMMDD}_trade.zip
Inside: {YYYYMMDD}_{symbol}_minute_trade.csv
Format: ms_since_midnight,Open*10000,High*10000,Low*10000,Close*10000,Volume
```

- No header row
- Prices multiplied by 10,000 and stored as integers
- Time is milliseconds since midnight (Eastern Time)
- Example: `34200000,1660000,1665000,1658000,1662500,150000` = 9:30 AM, O=166.00, H=166.50, L=165.80, C=166.25, V=150000

---

## Factor File Format

**Location:** `quantconnect-lean/Data/equity/usa/factor_files/{symbol}.csv`

```
date,price_factor,split_factor,reference_price
```

From LEAN source (`CorporateFactorRow.cs`):
- `PriceScaleFactor = price_factor × split_factor`
- `raw_price × PriceScaleFactor = fully_adjusted_price`
- `reference_price` = raw close on the factor file date
- `reference_price × split_factor` ≈ adjusted reference (verified to match)
- File is ordered chronologically (earliest first)
- Last row is a sentinel: `20501231,1,1,0` (far future, factors = 1.0)

### How Splits Are Encoded
The `split_factor` is **cumulative from present backwards**:
- At `20501231` (sentinel): sf=1.0 (present day, no adjustment needed)
- At each earlier split date: sf = sf_next × (1/split_ratio)

Example for TQQQ:
```
20501231: sf=1.0      (present)
20251119: sf=0.5      (before 2:1 reverse split → sf = 1.0 × 0.5)
20220112: sf=0.25     (before 2:1 reverse split → sf = 0.5 × 0.5)
20210120: sf=0.125    (before 2:1 reverse split → sf = 0.25 × 0.5)
20180523: sf=0.04167  (before 3:1 reverse split → sf = 0.125 × 0.333)
```

The ratio between consecutive rows gives the actual split:
- `sf[row] / sf[next_row]` = split ratio (0.5 = 2:1 reverse, 0.333 = 3:1 reverse)

### How Dividends Are Encoded (QQQ only)
The `price_factor` starts < 1.0 at the earliest date and approaches 1.0 at the sentinel.
Each dividend event adjusts pf:
- `pf[row] = pf[next_row] × (Close - Dividend) / Close`

TQQQ and SQQQ do not pay dividends, so `price_factor = 1.0` for all rows.

---

## Current Factor Files (verified 2026-02-09)

### TQQQ (10 rows) — No dividends, 8 reverse splits
```
20100211,1,0.0026041666666666665,0.2163
20110224,1,0.0026041666666666665,0.4322    (no split, just a row)
20120510,1,0.005208333333333333,0.5283     (1:2 reverse on 20120511)
20140123,1,0.010416666666666666,1.3097     (1:2 reverse on 20140124)
20170111,1,0.020833333333333332,2.9496     (1:2 reverse on 20170112)
20180523,1,0.041666666666666664,6.9321     (1:3 reverse on 20180524)
20210120,1,0.125,24.745                    (1:2 reverse on 20210121)
20220112,1,0.25,38.17                      (1:2 reverse on 20220113)
20251119,1,0.5,50.025                      (1:2 reverse on 20251120)
20501231,1,1,0                             (sentinel)
```

### SQQQ (10 rows) — No dividends, 8 reverse splits
```
20100211,1,160000.0,12316800.0
20120510,1,160000.0,1968000.0              (1:4 reverse on 20120511)
20140123,1,40000.0,560800.0                (1:4 reverse on 20140124)
20170111,1,10000.0,116900.0                (1:4 reverse on 20170112)
20190523,1,2500.0,25800.0                  (1:4 reverse on 20190524)
20200817,1,625.0,3300.0                    (1:5 reverse on 20200818)
20220112,1,125.0,792.5                     (1:5 reverse on 20220113)
20241106,1,25.0,166.25                     (1:5 reverse on 20241107)
20251119,1,5.0,75.6                        (1:5 reverse on 20251120)
20501231,1,1,0                             (sentinel)
```

### QQQ (69 rows) — Dividends + 1 split
- `price_factor`: ranges from 0.8703 (1999) to 1.0 (sentinel) — dividend adjustments
- `split_factor`: 0.5 (before 2003-12-23 reverse split) → 1.0 (after)
- `reference_price`: raw close on that date (verified to match AV data)

---

## Verification Scripts

| Script | Purpose |
|--------|---------|
| `verify_av_data.py` | Post-download inventory, split jump check, sample prices |
| `verify_factor_match.py` | Validates every factor file row against actual raw price data |
| `verify_factor_files.py` | Earlier verification (checks split boundaries) |

---

## Updating Data

To download new data (e.g., extend to 2026-03+):

```bash
python download_alphavantage_data.py --start 2026-02 --end 2026-03
```

The script has resume support (`.av_download_progress.json`). To re-download:
```bash
python download_alphavantage_data.py --reset-progress --start 2026-02 --end 2026-03
```

## Updating Factor Files

When a new split occurs for TQQQ or SQQQ:
1. Add a new row BEFORE the sentinel row
2. Date = last trading day before split takes effect
3. `price_factor` = 1.0 (no dividends)
4. `split_factor` = previous_sf × (1 / split_ratio)
   - For 2:1 reverse: new_sf = old_sf × 0.5
   - For 5:1 reverse: new_sf = old_sf × 0.2
5. `reference_price` = raw_close × new_split_factor

When a new QQQ dividend occurs:
1. Add a new row before the sentinel
2. Date = previous trading day before ex-dividend date
3. `split_factor` = same as previous (1.0 unless new split)
4. `price_factor` = previous_pf × (Close - Dividend) / Close
5. `reference_price` = raw close on that date
