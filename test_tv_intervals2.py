"""Test tvDatafeed with AUTH + QQQ (inception 1999) at 4h interval.
Also test if we can get MORE than 5000 bars.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from tvDatafeed import TvDatafeed, Interval

# Try with authentication for potentially more data
username = os.getenv("TRADINGVIEW_USERNAME")
password = os.getenv("TRADINGVIEW_PASSWORD")

print("=== Testing with AUTH ===\n")
tv_auth = TvDatafeed(username=username, password=password)

# Test TQQQ 4h with auth
for n_bars in [5000, 10000, 15000, 20000]:
    try:
        df = tv_auth.get_hist(symbol="TQQQ", exchange="NASDAQ", interval=Interval.in_4_hour, n_bars=n_bars)
        if df is not None and not df.empty:
            df = df.reset_index()
            earliest = df["datetime"].min()
            latest = df["datetime"].max()
            print(f"  TQQQ 4h ({n_bars:,} requested): {len(df):,} bars | {earliest} → {latest}")
        else:
            print(f"  TQQQ 4h ({n_bars:,} requested): EMPTY")
    except Exception as e:
        print(f"  TQQQ 4h ({n_bars:,} requested): ERROR - {e}")

print()

# Test QQQ — it started in 1999, much older
for label, symbol, exchange in [("QQQ", "QQQ", "NASDAQ"), ("SQQQ", "SQQQ", "NASDAQ")]:
    for interval_name, interval in [("4hour", Interval.in_4_hour), ("1hour", Interval.in_1_hour)]:
        try:
            df = tv_auth.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=5000)
            if df is not None and not df.empty:
                df = df.reset_index()
                earliest = df["datetime"].min()
                latest = df["datetime"].max()
                print(f"  {label} {interval_name} (5000): {len(df):,} bars | {earliest} → {latest}")
            else:
                print(f"  {label} {interval_name} (5000): EMPTY")
        except Exception as e:
            print(f"  {label} {interval_name} (5000): ERROR - {e}")

# Also test daily to confirm max bars for daily
print()
for symbol in ["TQQQ", "QQQ", "SQQQ"]:
    try:
        df = tv_auth.get_hist(symbol=symbol, exchange="NASDAQ", interval=Interval.in_daily, n_bars=20000)
        if df is not None and not df.empty:
            df = df.reset_index()
            earliest = df["datetime"].min()
            latest = df["datetime"].max()
            print(f"  {symbol} daily (20000): {len(df):,} bars | {earliest} → {latest}")
        else:
            print(f"  {symbol} daily (20000): EMPTY")
    except Exception as e:
        print(f"  {symbol} daily (20000): ERROR - {e}")
