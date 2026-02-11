"""Test tvDatafeed: how far back do 5000 bars go at different intervals?

Bars per trading day (6.5h = 390 min):
  1-min:  390 bars/day → 5000 bars ≈ 12 days
  5-min:   78 bars/day → 5000 bars ≈ 64 days  (~2 months)
  15-min:  26 bars/day → 5000 bars ≈ 192 days (~9 months)
  30-min:  13 bars/day → 5000 bars ≈ 384 days (~1.5 years)
  1-hour:  ~7 bars/day → 5000 bars ≈ 714 days (~2.8 years)
  4-hour:  ~2 bars/day → 5000 bars ≈ 2500 days (~10 years!)
"""
import os
from dotenv import load_dotenv
load_dotenv()

from tvDatafeed import TvDatafeed, Interval

tv = TvDatafeed()  # no-auth is fine for this test

intervals = [
    ("5min",  Interval.in_5_minute),
    ("15min", Interval.in_15_minute),
    ("30min", Interval.in_30_minute),
    ("1hour", Interval.in_1_hour),
    ("4hour", Interval.in_4_hour),
]

print("TQQQ — 5000 bars at each interval:\n")

for label, interval in intervals:
    try:
        df = tv.get_hist(symbol="TQQQ", exchange="NASDAQ", interval=interval, n_bars=5000)
        if df is not None and not df.empty:
            df = df.reset_index()
            earliest = df["datetime"].min()
            latest = df["datetime"].max()
            print(f"  {label:6s}:  {len(df):,} bars  |  {earliest}  →  {latest}")
        else:
            print(f"  {label:6s}:  EMPTY")
    except Exception as e:
        print(f"  {label:6s}:  ERROR - {e}")
