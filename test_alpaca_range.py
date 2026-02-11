"""Quick test: how far back does Alpaca 1-min data go?"""
import os
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
)

test_ranges = [
    ("2015-07-01", "2015-07-02"),
    ("2015-10-01", "2015-10-02"),
    ("2015-12-01", "2015-12-02"),
    ("2016-01-04", "2016-01-05"),
    ("2016-03-01", "2016-03-02"),
    ("2016-06-01", "2016-06-02"),
    ("2016-07-18", "2016-07-19"),  # ~SIP data start
]

for start_s, end_s in test_ranges:
    start = datetime.strptime(start_s, "%Y-%m-%d")
    end = datetime.strptime(end_s, "%Y-%m-%d")
    try:
        req = StockBarsRequest(
            symbol_or_symbols="TQQQ",
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(req)
        df = bars.df
        if df.empty:
            print(f"  {start_s}:  EMPTY (no data)")
        else:
            print(f"  {start_s}:  {len(df)} bars  ✓")
    except Exception as e:
        print(f"  {start_s}:  ERROR - {e}")
