"""Test: Alpha Vantage free tier - 1min data with month parameter.
Free tier: 25 calls/day. Each call = 1 full month of 1-min data.
2010-2016 = 72 months x 3 tickers = 216 calls = ~9 days of downloading.
"""
import requests

# Alpha Vantage free key - get one at https://www.alphavantage.co/support/#api-key
API_KEY = "demo"

# Test with demo key - limited to certain symbols
test_cases = [
    ("TQQQ", "2010-02"),
    ("TQQQ", "2015-06"),
    ("TQQQ", "2018-01"),
]

for symbol, month in test_cases:
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": "1min",
        "month": month,
        "outputsize": "full",
        "apikey": API_KEY,
    }
    resp = requests.get(url, params=params)
    data = resp.json()

    if "Time Series (1min)" in data:
        ts = data["Time Series (1min)"]
        dates = sorted(ts.keys())
        print(f"  {symbol} {month}:  {len(ts)} bars  ({dates[0]} -> {dates[-1]})  ✓")
    elif "Note" in data:
        print(f"  {symbol} {month}:  RATE LIMITED - {data['Note'][:60]}")
    elif "Information" in data:
        print(f"  {symbol} {month}:  {data['Information'][:80]}")
    elif "Error Message" in data:
        print(f"  {symbol} {month}:  ERROR - {data['Error Message'][:80]}")
    else:
        print(f"  {symbol} {month}:  {str(data)[:120]}")
