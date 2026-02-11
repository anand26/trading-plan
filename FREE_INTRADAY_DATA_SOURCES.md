# Free Historical Intraday Stock Data Sources — Comprehensive Research Report

> **Goal**: Find FREE sources of 1-min, 5-min, or 10-min OHLCV data for US stocks (TQQQ, SQQQ, etc.) going back to 2010–2016 for backtesting.
>
> **TL;DR**: There are only **two practical free options** that can get you deep historical intraday data: **AlphaVantage** (with `month=` parameter, back to 2000) and **Alpaca** (free tier, 7+ years of IEX data). Everything else is severely limited.

---

## 🏆 TIER 1 — ACTUALLY WORKS FOR DEEP HISTORY (FREE)

### 1. AlphaVantage — `month=` Parameter (⭐ BEST FREE OPTION)

| Detail | Value |
|---|---|
| **Library** | `alpha_vantage` (pip) or raw `requests` |
| **Intervals** | 1min, 5min, 15min, 30min, 60min |
| **History Depth** | **20+ years** — back to January 2000 |
| **Free API Key** | Yes — https://www.alphavantage.co/support/#api-key |
| **Rate Limit (Free)** | 25 requests/day (was 5/min, recently changed) |
| **Premium Note** | Intraday is now labeled "Premium" but the `month=` param may still work with free key for some queries |

**The Key Trick**: Use the `month=YYYY-MM` parameter to pull one full month of intraday data per request:

```python
import requests
import time

API_KEY = 'YOUR_FREE_KEY'
symbol = 'TQQQ'

# Loop month-by-month from 2010 to present
for year in range(2010, 2025):
    for month in range(1, 13):
        url = (
            f'https://www.alphavantage.co/query?'
            f'function=TIME_SERIES_INTRADAY&symbol={symbol}'
            f'&interval=5min&month={year}-{month:02d}'
            f'&outputsize=full&apikey={API_KEY}&datatype=csv'
        )
        r = requests.get(url)
        if r.status_code == 200 and 'timestamp' in r.text[:100]:
            with open(f'data/{symbol}_{year}_{month:02d}_5min.csv', 'w') as f:
                f.write(r.text)
            print(f'✅ {symbol} {year}-{month:02d}: downloaded')
        else:
            print(f'❌ {symbol} {year}-{month:02d}: failed')
        time.sleep(12)  # Respect rate limits (5/min for free key)
```

**Using the Python wrapper**:
```python
from alpha_vantage.timeseries import TimeSeries
ts = TimeSeries(key='YOUR_API_KEY', output_format='pandas')
# Pull Jan 2014 30-min intraday data
data, meta = ts.get_intraday('TQQQ', interval='5min', month='2014-01', outputsize='full')
```

**⚠️ CRITICAL LIMITATION**: 
- Free tier is now **25 API calls per day** (used to be 5/min)
- At 25/day, downloading 15 years × 12 months = 180 calls = **~7 days of waiting**
- Intraday endpoint is now marked "Premium Trending" — free key access may be restricted
- Premium plans start at $49.99/month (75 req/min) — worth it for the data depth
- **Test it first** with your free key before committing

---

### 2. Alpaca Markets — Free Tier (⭐ EXCELLENT PRACTICAL OPTION)

| Detail | Value |
|---|---|
| **Library** | `alpaca-py` (pip) |
| **Intervals** | 1min, 5min, 15min, 30min, 1hour, 1day |
| **History Depth** | **7+ years** of historical data |
| **Free API Key** | Yes — sign up at https://app.alpaca.markets/signup |
| **Rate Limit (Free)** | 200 API calls/min |
| **Data Source (Free)** | IEX exchange only (not all exchanges) |

**Auto-pagination** built into the SDK — just set date range and it handles the rest:

```python
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from datetime import datetime

client = StockHistoricalDataClient(
    api_key='YOUR_KEY',
    secret_key='YOUR_SECRET'
)

# Download 1-minute data for TQQQ - auto-paginates!
request = StockBarsRequest(
    symbol_or_symbols=['TQQQ'],
    timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Minute),
    start=datetime(2018, 1, 1),
    end=datetime(2024, 12, 31)
)
bars = client.get_stock_bars(request)
df = bars.df
print(f'Downloaded {len(df)} bars')
df.to_csv('tqqq_1min_2018_2024.csv')
```

**⚠️ LIMITATIONS**:
- Free tier = **IEX exchange data only** (not consolidated SIP feed)
  - IEX is ~2-3% of total market volume → you'll see lower volume numbers
  - OHLC prices may differ slightly from consolidated feed
  - For backtesting a scalping strategy, this matters!
- 7+ years back = roughly **~2018 to present** (not 2010)
- 200 req/min rate limit (generous)
- Requires Alpaca account (free, no funding required)
- $99/month "Algo Trader Plus" plan unlocks all US exchanges (SIP feed)

**You already have this in your workspace!** See your existing `download_alpaca_data.py` and `test_alpaca.py`.

---

## 🥈 TIER 2 — LIMITED BUT USEFUL (FREE)

### 3. TradingView via `tvdatafeed` (Scraper)

| Detail | Value |
|---|---|
| **Library** | `tvdatafeed` v2.1.0 |
| **Intervals** | 1min, 5min, 15min, 30min, 1hour, daily+ |
| **History per call** | **5,000 bars maximum** |
| **For 1-min** | ~12.8 trading days |
| **For 5-min** | ~64 trading days |
| **Auth** | Optional TradingView credentials (gets more data) |

```python
from tvDatafeed import TvDatafeed, Interval
tv = TvDatafeed()  # or TvDatafeed(username, password)
data = tv.get_hist('TQQQ', 'NASDAQ', interval=Interval.in_5_minute, n_bars=5000)
```

**⚠️ LIMITATIONS**:
- Max 5,000 bars regardless → very shallow history for intraday
- Scraping TradingView's WebSocket = grey area (ToS violations possible)
- Unreliable — can break when TradingView changes their backend
- **NOT suitable for getting 2010-2016 intraday data**

---

### 4. Finnhub — `stock_candles()` API

| Detail | Value |
|---|---|
| **Library** | `finnhub-python` v2.4.27 |
| **Intervals** | 1, 5, 15, 30, 60, D (minutes) |
| **Free Rate Limit** | 60 API calls/minute |
| **History (Free)** | ~1 year of intraday data |

```python
import finnhub
client = finnhub.Client(api_key="YOUR_FREE_KEY")
import time
# Resolution: '1', '5', '15', '30', '60', 'D'
candles = client.stock_candles('TQQQ', '5', 
    int(time.mktime(time.strptime('2024-01-01', '%Y-%m-%d'))),
    int(time.mktime(time.strptime('2024-06-01', '%Y-%m-%d')))
)
```

**⚠️ LIMITATIONS**:
- Free tier: only ~1 year of intraday candle history
- Older data returns empty results
- **NOT suitable for getting 2010-2016 data**

---

### 5. Yahoo Finance via `yfinance`

| Detail | Value |
|---|---|
| **Library** | `yfinance` |
| **Intervals** | 1m, 2m, 5m, 15m, 30m, 60m, 90m |
| **1-min history** | **8 days max** (hardcoded) |
| **5-min history** | **60 days max** (hardcoded) |
| **15/30-min** | **60 days max** |
| **1-hour** | **730 days max** |
| **Auth** | None needed |

```python
import yfinance as yf
data = yf.download('TQQQ', period='60d', interval='5m')
```

**⚠️ WHY THIS DOESN'T WORK**:
These are **Yahoo server-side limits**, hardcoded in yfinance source code. Cannot be worked around:
- `1m` → max 691,200 seconds (8 days)
- `2m/5m/15m/30m/90m` → max 5,184,000 seconds (60 days)
- `1h` → max 63,072,000 seconds (730 days)
- **Absolutely NOT suitable for historical data**

---

## 🚫 TIER 3 — NOT FREE / NOT PRACTICAL

### 6. Databento — PAID SERVICE

| Detail | Value |
|---|---|
| **Library** | `databento` |
| **Quality** | Excellent — tick-level, all exchanges |
| **Cost** | Pay-per-use (every API call incurs cost) |

Has `get_cost()` and `get_billable_size()` methods in their API — confirms it's a paid metered service. **Not free.**

### 7. Polygon.io — PAID (mostly)

| Detail | Value |
|---|---|
| **Free tier** | Extremely limited (2-year history, 5 calls/min) |
| **Paid plans** | Start at $29/month (Starter) |
| **Full history** | Requires $199/month (Business) or higher |

The Polygon website now redirects to "Massive.com" — they appear to be rebranding. Free tier is essentially useless for deep intraday history.

### 8. Tiingo — PAID for Intraday

| Detail | Value |
|---|---|
| **Daily data** | Free (20+ years) |
| **Intraday (IEX)** | Requires paid plan |

You already tested this (`test_tiingo.py` failed with exit code 1). Free tier doesn't include intraday.

### 9. Interactive Brokers (TWS API)

| Detail | Value |
|---|---|
| **Library** | `ib_insync` or `ibapi` |
| **History** | Up to ~1 year of 1-min data |
| **Requirement** | Active IB account (funded) |

Not truly "free" — requires brokerage account. Also limited to ~1 year of 1-min bars per request with pacing limits.

### 10. Stooq

| Detail | Value |
|---|---|
| **Library** | `pandas_datareader` (stooq source) |
| **Intraday** | Not available — daily/weekly/monthly only |

You have `test_stooq.py` in your workspace but this is daily data only.

---

## 📊 COMPARISON MATRIX

| Source | Free? | 1-min | 5-min | Depth (Intraday) | Rate Limit | Quality |
|---|---|---|---|---|---|---|
| **AlphaVantage** | ✅ Free key | ✅ | ✅ | **20+ years** (2000+) | 25/day (free) | ⭐⭐⭐⭐ |
| **Alpaca** | ✅ Free acct | ✅ | ✅ | **7+ years** (~2018+) | 200/min | ⭐⭐⭐ (IEX only) |
| **tvdatafeed** | ✅ | ✅ | ✅ | ~13–64 days | N/A (scraper) | ⭐⭐ |
| **Finnhub** | ✅ Free key | ✅ | ✅ | ~1 year | 60/min | ⭐⭐⭐ |
| **yfinance** | ✅ | ✅ | ✅ | 8–60 days | Varies | ⭐⭐ |
| **Databento** | ❌ Paid | ✅ | ✅ | Full history | Unlimited | ⭐⭐⭐⭐⭐ |
| **Polygon** | ❌ Mostly | ✅ | ✅ | Full history | 5/min (free) | ⭐⭐⭐⭐⭐ |
| **Tiingo** | ❌ Intraday | ✅ | ✅ | Varies | Varies | ⭐⭐⭐⭐ |

---

## 🎯 RECOMMENDATION FOR YOUR USE CASE

You need **TQQQ/SQQQ 1-min or 5-min data back to 2010** for backtesting your scalping algorithm.

### Strategy 1: AlphaVantage Month-by-Month Download (BEST)

1. Get a free API key from AlphaVantage
2. Test if intraday endpoint still works with free key (it's now labeled "Premium")
3. If yes: loop month-by-month from 2010-01 to present using `month=YYYY-MM`
4. If free key is blocked: get $49.99/mo Premium plan for 1 month, bulk download everything, cancel
5. At 75 req/min (premium), you can download **15 years × 12 months = 180 months in ~3 minutes**

### Strategy 2: Alpaca Free Tier (GOOD FOR 2018+)

1. Sign up for free Alpaca account (no funding needed)
2. Use `alpaca-py` SDK with auto-pagination
3. Download 7+ years of 1-min data (IEX source)
4. Caveat: IEX-only data has lower volume coverage

### Strategy 3: Combine Multiple Sources

1. **2010-2018**: AlphaVantage (month parameter)
2. **2018-present**: Alpaca free tier
3. Cross-validate overlapping period (2018) between sources

### Strategy 4: Your Existing `download_massive_data.py`

You already successfully ran `download_massive_data.py --start 2010-02-10 --end 2018-07-01`. Check what data source it uses — if it already has the data you need, you might not need anything else!

---

## 💡 PRACTICAL SCRIPT: AlphaVantage Bulk Downloader

```python
"""
bulk_download_alphavantage.py
Downloads full intraday history using AlphaVantage month parameter.
Free tier: 25 requests/day → takes ~7 days for 15 years
Premium ($49.99/mo): 75 req/min → takes ~3 minutes for 15 years
"""
import requests
import time
import os
from datetime import datetime

API_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', 'demo')
SYMBOL = 'TQQQ'
INTERVAL = '5min'  # 1min, 5min, 15min, 30min, 60min
OUTPUT_DIR = 'Data/alphavantage'
RATE_LIMIT_SECONDS = 12  # Free: 12s between calls. Premium: 1s

os.makedirs(OUTPUT_DIR, exist_ok=True)

start_year, start_month = 2010, 2  # TQQQ inception: Feb 2010
end_year, end_month = datetime.now().year, datetime.now().month

total = 0
errors = 0

year, month = start_year, start_month
while (year, month) <= (end_year, end_month):
    filename = f'{OUTPUT_DIR}/{SYMBOL}_{year}_{month:02d}_{INTERVAL}.csv'
    
    if os.path.exists(filename) and os.path.getsize(filename) > 100:
        print(f'⏭️  {SYMBOL} {year}-{month:02d}: already exists, skipping')
    else:
        url = (
            f'https://www.alphavantage.co/query?'
            f'function=TIME_SERIES_INTRADAY&symbol={SYMBOL}'
            f'&interval={INTERVAL}&month={year}-{month:02d}'
            f'&outputsize=full&adjusted=true'
            f'&apikey={API_KEY}&datatype=csv'
        )
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and 'timestamp' in r.text[:200]:
                with open(filename, 'w') as f:
                    f.write(r.text)
                lines = r.text.count('\n')
                print(f'✅ {SYMBOL} {year}-{month:02d}: {lines} bars')
                total += lines
            else:
                print(f'❌ {SYMBOL} {year}-{month:02d}: {r.text[:100]}')
                errors += 1
        except Exception as e:
            print(f'❌ {SYMBOL} {year}-{month:02d}: {e}')
            errors += 1
        
        time.sleep(RATE_LIMIT_SECONDS)
    
    # Advance to next month
    month += 1
    if month > 12:
        month = 1
        year += 1

print(f'\n📊 Done! Total bars: {total}, Errors: {errors}')
```

---

*Report generated: June 2025*
*Sources: GitHub repos (ranaroussi/yfinance, rongardF/tvdatafeed, Finnhub-Stock-API/finnhub-python, alpacahq/alpaca-py, databento/databento-python, RomelTorres/alpha_vantage), AlphaVantage official docs, Alpaca pricing page*
