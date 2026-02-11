"""Focused test: Twelve Data year-by-year with rate limiting."""
import requests
import time

API_KEY = "63fac2a524cf4344a7b310db2debf603"

print("Testing TQQQ 1-min data availability by year...")
print("(8s pause between calls to respect rate limit)\n")

for year in [2010, 2012, 2014, 2016, 2018]:
    resp = requests.get("https://api.twelvedata.com/time_series", params={
        "symbol": "TQQQ",
        "interval": "1min",
        "start_date": f"{year}-06-15 09:30:00",
        "end_date": f"{year}-06-15 16:00:00",
        "apikey": API_KEY,
        "outputsize": 5,
    })
    data = resp.json()
    if "values" in data:
        n = len(data["values"])
        oldest = data["values"][-1]["datetime"]
        print(f"  {year}:  {n} bars  (from {oldest})  OK")
    else:
        msg = data.get("message", str(data))[:80]
        print(f"  {year}:  {msg}")
    time.sleep(9)

print("\nDone.")
