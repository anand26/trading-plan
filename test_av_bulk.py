"""Quick test: AlphaVantage intraday with month= param and CSV format.
Testing with free key NY4CZKKV0V2T4KT1
"""
import requests
import time

API_KEY = "NY4CZKKV0V2T4KT1"

# Test 3 different months spanning the range we need
test_cases = [
    ("TQQQ", "2010-03", "5min"),   # near inception
    ("TQQQ", "2015-06", "5min"),   # mid-range
    ("TQQQ", "2017-01", "5min"),   # recent-ish
]

print("Testing AlphaVantage intraday with month= parameter (CSV format)\n")

for symbol, month, interval in test_cases:
    url = (
        f"https://www.alphavantage.co/query?"
        f"function=TIME_SERIES_INTRADAY&symbol={symbol}"
        f"&interval={interval}&month={month}"
        f"&outputsize=full&adjusted=true"
        f"&apikey={API_KEY}&datatype=csv"
    )
    
    try:
        r = requests.get(url, timeout=30)
        text = r.text[:500]
        
        if r.status_code == 200 and "timestamp" in text[:200]:
            lines = r.text.strip().split("\n")
            print(f"  {symbol} {month} {interval}:  {len(lines)-1:,} bars  ✓")
            print(f"    Header: {lines[0]}")
            print(f"    First:  {lines[1]}")
            print(f"    Last:   {lines[-1]}")
        elif "premium" in text.lower():
            print(f"  {symbol} {month} {interval}:  PREMIUM REQUIRED")
            print(f"    {text[:150]}")
        elif "call frequency" in text.lower() or "rate limit" in text.lower():
            print(f"  {symbol} {month} {interval}:  RATE LIMITED")
            print(f"    {text[:150]}")
        else:
            print(f"  {symbol} {month} {interval}:  UNEXPECTED")
            print(f"    Status: {r.status_code}")
            print(f"    Body:   {text[:200]}")
    except Exception as e:
        print(f"  {symbol} {month} {interval}:  ERROR - {e}")
    
    print()
    time.sleep(13)  # respect rate limit

print("Done.")
