"""Test: Stooq free historical data download (no API key needed).
Stooq provides 5-minute data for US stocks, downloadable as CSV.
"""
import requests
import io
import pandas as pd

# Stooq direct CSV download - no auth needed
# d=d (daily), d=5 (5min), d=h (hourly)
test_cases = [
    ("TQQQ.US", "2010-02-11", "2010-02-15"),
    ("TQQQ.US", "2015-06-01", "2015-06-05"),
]

for symbol, start, end in test_cases:
    s = start.replace("-", "")
    e = end.replace("-", "")
    url = f"https://stooq.com/q/d/l/?s={symbol}&d1={s}&d2={e}&i=5"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    
    if resp.status_code == 200 and len(resp.text) > 50:
        try:
            df = pd.read_csv(io.StringIO(resp.text))
            print(f"  {symbol} {start}:  {len(df)} bars  cols={list(df.columns)}  ✓")
            if not df.empty:
                print(f"    First: {df.iloc[0].to_dict()}")
                print(f"    Last:  {df.iloc[-1].to_dict()}")
        except Exception as ex:
            print(f"  {symbol} {start}:  Parse error: {ex}")
            print(f"    Raw: {resp.text[:200]}")
    else:
        print(f"  {symbol} {start}:  HTTP {resp.status_code}, len={len(resp.text)}")
        print(f"    Raw: {resp.text[:200]}")
