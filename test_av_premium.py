"""Quick test of Alpha Vantage premium key."""
import requests
import time

API_KEY = "GJU4TDYFABLUSRT0"
print("Testing Alpha Vantage PREMIUM key (75 calls/min)...\n")

tests = [
    ("QQQ",  "2010-02"),
    ("TQQQ", "2010-02"),
    ("SQQQ", "2010-02"),
    ("QQQ",  "2024-12"),
]

for symbol, month in tests:
    resp = requests.get("https://www.alphavantage.co/query", params={
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": "1min",
        "month": month,
        "outputsize": "full",
        "apikey": API_KEY,
    })
    data = resp.json()

    if "Time Series (1min)" in data:
        ts = data["Time Series (1min)"]
        dates = sorted(ts.keys())
        first_bar = ts[dates[0]]
        print(f"  {symbol} {month}:  {len(ts):>6,} bars  ({dates[0]} -> {dates[-1]})")
        o = first_bar["1. open"]
        h = first_bar["2. high"]
        l = first_bar["3. low"]
        c = first_bar["4. close"]
        v = first_bar["5. volume"]
        print(f"    Sample bar: O={o} H={h} L={l} C={c} V={v}")
    elif "Note" in data:
        print(f"  {symbol} {month}:  RATE LIMITED - {data['Note'][:60]}")
    elif "Information" in data:
        print(f"  {symbol} {month}:  INFO - {data['Information'][:80]}")
    elif "Error Message" in data:
        print(f"  {symbol} {month}:  ERROR - {data['Error Message'][:80]}")
    else:
        print(f"  {symbol} {month}:  UNEXPECTED - {str(data)[:150]}")

    time.sleep(1)

print("\nPremium key test complete.")
