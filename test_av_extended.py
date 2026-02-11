"""Test Alpha Vantage - basic intraday (no month param) + extended hours."""
import requests
import time

API_KEY = "NY4CZKKV0V2T4KT1"

# Test 1: Basic intraday without month (returns recent data only)
print("=== Test 1: Basic TIME_SERIES_INTRADAY (no month) ===")
resp = requests.get("https://www.alphavantage.co/query", params={
    "function": "TIME_SERIES_INTRADAY",
    "symbol": "TQQQ",
    "interval": "1min",
    "outputsize": "full",
    "apikey": API_KEY,
})
data = resp.json()
if "Time Series (1min)" in data:
    ts = data["Time Series (1min)"]
    dates = sorted(ts.keys())
    print(f"  {len(ts):,} bars  ({dates[0]} -> {dates[-1]})")
else:
    for k, v in data.items():
        print(f"  {k}: {str(v)[:100]}")

time.sleep(13)

# Test 2: Try TIME_SERIES_INTRADAY_EXTENDED (was free, may still be)
print("\n=== Test 2: TIME_SERIES_INTRADAY_EXTENDED ===")
for sl in ["year1month1", "year2month1"]:
    resp = requests.get("https://www.alphavantage.co/query", params={
        "function": "TIME_SERIES_INTRADAY_EXTENDED",
        "symbol": "TQQQ",
        "interval": "1min",
        "slice": sl,
        "apikey": API_KEY,
    })
    text = resp.text[:300]
    if "time,open" in text.lower() or "timestamp" in text.lower():
        lines = resp.text.strip().split("\n")
        print(f"  {sl}: {len(lines)-1} bars  ✓")
        print(f"    First: {lines[1][:60]}")
        print(f"    Last:  {lines[-1][:60]}")
    else:
        print(f"  {sl}: {text[:120]}")
    time.sleep(13)

print("\nDone.")
