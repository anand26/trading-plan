"""Test Twelve Data - check what plans/data is available."""
import requests

API_KEY = "63fac2a524cf4344a7b310db2debf603"

# 1. Check API key usage / plan
print("=== API Key Status ===")
resp = requests.get(f"https://api.twelvedata.com/api_usage?apikey={API_KEY}")
print(resp.json())

# 2. Try recent data first (should definitely work)
print("\n=== Recent 1-min data ===")
resp = requests.get("https://api.twelvedata.com/time_series", params={
    "symbol": "TQQQ",
    "interval": "1min",
    "start_date": "2026-02-06 09:30:00",
    "end_date": "2026-02-06 16:00:00",
    "apikey": API_KEY,
    "outputsize": 10,
})
data = resp.json()
if "values" in data:
    print(f"  Got {len(data['values'])} bars ✓")
    print(f"  First: {data['values'][0]}")
elif "message" in data:
    print(f"  {data['message']}")
else:
    print(f"  {data}")

# 3. Try different years to find the cutoff
print("\n=== Year-by-year probe ===")
for year in [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2012, 2010]:
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
        first = data["values"][-1]["datetime"]
        print(f"  {year}:  {n} bars  (from {first})  ✓")
    elif "message" in data:
        msg = data["message"][:70]
        print(f"  {year}:  {msg}")
    elif "code" in data:
        print(f"  {year}:  code={data['code']} - {data.get('message', str(data)[:70])}")
    else:
        print(f"  {year}:  {str(data)[:80]}")

# 4. Check earliest available data
print("\n=== Earliest available (outputsize=5000, no date) ===")
resp = requests.get("https://api.twelvedata.com/time_series", params={
    "symbol": "TQQQ",
    "interval": "1min",
    "apikey": API_KEY,
    "outputsize": 5000,
    "order": "ASC",
})
data = resp.json()
if "values" in data:
    print(f"  Got {len(data['values'])} bars")
    print(f"  Earliest: {data['values'][0]['datetime']}")
    print(f"  Latest:   {data['values'][-1]['datetime']}")
