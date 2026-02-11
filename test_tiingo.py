"""Test Tiingo IEX endpoint - free tier includes intraday historical data.
Free plan: 1000 requests/day, intraday with date ranges.
Sign up: https://api.tiingo.com (free, takes 30 sec)

Tiingo has TWO intraday sources:
1. IEX - free, but only from ~2017+
2. SIP - paid (full exchange data)
"""
import requests
import time

# No key yet - just test if the endpoint structure works
# User can get a free key at https://api.tiingo.com
API_KEY = ""  # placeholder

print("Tiingo requires a free API key.")
print("Sign up at: https://api.tiingo.com")
print("It takes 30 seconds, no credit card needed.")
print()
print("Tiingo IEX free tier:")
print("  - 1000 requests/day")
print("  - Date-range pagination for 1-min data")  
print("  - Historical IEX data from ~2017 onwards")
print("  - Supports TQQQ, SQQQ, QQQ")
print()
print("That would cover 2017-2018 (the gap between Alpaca 2016 and Databento 2018)")
print()

# Alternative: let me also check yfinance for 1-hour data (goes back further)
print("=" * 50)
print("ALTERNATIVE: yfinance 1-HOUR data (goes back 2+ years)")
print("=" * 50)
import yfinance as yf
for ticker in ["TQQQ"]:
    df = yf.download(ticker, start="2010-02-11", end="2010-03-01", interval="1h", progress=False)
    if not df.empty:
        print(f"  {ticker} 2010 1h: {len(df)} bars  ({df.index[0]} -> {df.index[-1]})  OK")
    else:
        print(f"  {ticker} 2010 1h: EMPTY")
    
    df = yf.download(ticker, start="2015-06-01", end="2015-07-01", interval="1h", progress=False)
    if not df.empty:
        print(f"  {ticker} 2015 1h: {len(df)} bars  ({df.index[0]} -> {df.index[-1]})  OK")
    else:
        print(f"  {ticker} 2015 1h: EMPTY")

    # Also check how far back daily goes with yfinance
    df = yf.download(ticker, start="2010-02-11", end="2010-03-01", interval="1d", progress=False)
    if not df.empty:
        print(f"  {ticker} 2010 1d: {len(df)} bars  ({df.index[0]} -> {df.index[-1]})  OK")
