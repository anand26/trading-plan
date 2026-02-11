"""Test: how far back does Twelve Data free tier go for 1-min?"""
import requests

# Twelve Data free API key (get one at https://twelvedata.com - takes 30 sec)
# For now, test without key to see what errors we get
API_KEY = "63fac2a524cf4344a7b310db2debf603"

test_dates = [
    ("2010-02-11", "2010-02-12"),  # TQQQ inception
    ("2012-01-03", "2012-01-04"),
    ("2015-01-05", "2015-01-06"),
    ("2016-01-04", "2016-01-05"),
    ("2018-01-02", "2018-01-03"),
]

for start, end in test_dates:
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "TQQQ",
        "interval": "1min",
        "start_date": f"{start} 09:30:00",
        "end_date": f"{end} 16:00:00",
        "apikey": API_KEY,
        "format": "JSON",
        "outputsize": 5000,
    }
    resp = requests.get(url, params=params)
    data = resp.json()

    if "values" in data:
        rows = len(data["values"])
        first = data["values"][-1]["datetime"]  # oldest is last
        last = data["values"][0]["datetime"]     # newest is first
        print(f"  {start}:  {rows} bars  ({first} -> {last})  ✓")
    elif "message" in data:
        print(f"  {start}:  {data['message'][:80]}")
    else:
        print(f"  {start}:  {data.get('status', 'unknown')} - {str(data)[:100]}")
