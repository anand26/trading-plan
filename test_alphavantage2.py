"""Test Alpha Vantage 1-min data with month parameter."""
import requests
import time

API_KEY = "NY4CZKKV0V2T4KT1"

print("Testing TQQQ 1-min data by month (Alpha Vantage)...")
print("(12s between calls, free tier = 25/day, 5/min)\n")

for month in ["2010-02", "2010-06", "2012-01", "2014-06", "2015-12", "2017-06"]:
    resp = requests.get("https://www.alphavantage.co/query", params={
        "function": "TIME_SERIES_INTRADAY",
        "symbol": "TQQQ",
        "interval": "1min",
        "month": month,
        "outputsize": "full",
        "apikey": API_KEY,
    })
    data = resp.json()

    if "Time Series (1min)" in data:
        ts = data["Time Series (1min)"]
        dates = sorted(ts.keys())
        print(f"  {month}:  {len(ts):,} bars  ({dates[0]} -> {dates[-1]})  ✓")
    elif "Note" in data:
        print(f"  {month}:  RATE LIMITED - {data['Note'][:60]}")
    elif "Information" in data:
        print(f"  {month}:  {data['Information'][:80]}")
    elif "Error Message" in data:
        print(f"  {month}:  ERROR - {data['Error Message'][:80]}")
    else:
        print(f"  {month}:  {str(data)[:120]}")

    time.sleep(13)

print("\nDone.")
