"""Get the closing prices on the day BEFORE each split for factor file reference prices."""
import zstandard as zstd
import io
import csv
from pathlib import Path

source_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\databento")

# ===== SQQQ =====
# Split dates (the day the split takes effect, price jumps on open):
# 2019-05-24, 2020-08-18, 2022-01-13, 2024-11-07, 2025-11-20
# We need the LAST TRADING DAY BEFORE each split
sqqq_split_dates = ['2019-05-24', '2020-08-18', '2022-01-13', '2024-11-07', '2025-11-20']

print("=" * 70)
print("SQQQ: Getting closing prices before each split")
print("=" * 70)

zst = list(source_dir.glob("*.SQQQ.csv.zst"))[0]
with open(zst, 'rb') as f:
    dctx = zstd.ZstdDecompressor()
    with dctx.stream_reader(f) as reader:
        text_stream = io.TextIOWrapper(reader, encoding='utf-8')
        csv_reader = csv.DictReader(text_stream)
        
        daily_close = {}
        daily_open = {}
        for row in csv_reader:
            d = row['ts_event'][:10]
            c = float(row['close'])
            o = float(row['open'])
            if d not in daily_open:
                daily_open[d] = o
            daily_close[d] = c

dates = sorted(daily_close.keys())
print(f"\nTotal trading days: {len(dates)}")
print(f"Date range: {dates[0]} to {dates[-1]}")

# For each split date, find the previous trading day's close
for split_date in sqqq_split_dates:
    # Find the last trading day before the split
    prev_dates = [d for d in dates if d < split_date]
    if prev_dates:
        prev_day = prev_dates[-1]
        prev_close = daily_close[prev_day]
        split_open = daily_open.get(split_date, 'N/A')
        if split_open != 'N/A':
            ratio = split_open / prev_close
        else:
            ratio = 0
        print(f"\n  Split on {split_date}:")
        print(f"    Prev day ({prev_day}) close: ${prev_close:.4f}")
        print(f"    Split day open: ${split_open:.4f}" if split_open != 'N/A' else "    Split day: no data")
        print(f"    Ratio: {ratio:.4f}x")
        print(f"    Factor file date: {prev_day.replace('-', '')}")

# ===== TQQQ =====
tqqq_split_dates = ['2018-05-24', '2021-01-21', '2022-01-13', '2025-11-20']

print("\n\n" + "=" * 70)
print("TQQQ: Getting closing prices before each split")
print("=" * 70)

zst = list(source_dir.glob("*.TQQQ.csv.zst"))[0]
with open(zst, 'rb') as f:
    dctx = zstd.ZstdDecompressor()
    with dctx.stream_reader(f) as reader:
        text_stream = io.TextIOWrapper(reader, encoding='utf-8')
        csv_reader = csv.DictReader(text_stream)
        
        daily_close = {}
        daily_open = {}
        for row in csv_reader:
            d = row['ts_event'][:10]
            c = float(row['close'])
            o = float(row['open'])
            if d not in daily_open:
                daily_open[d] = o
            daily_close[d] = c

dates = sorted(daily_close.keys())

for split_date in tqqq_split_dates:
    prev_dates = [d for d in dates if d < split_date]
    if prev_dates:
        prev_day = prev_dates[-1]
        prev_close = daily_close[prev_day]
        split_open = daily_open.get(split_date, 'N/A')
        if split_open != 'N/A':
            ratio = split_open / prev_close
        else:
            ratio = 0
        print(f"\n  Split on {split_date}:")
        print(f"    Prev day ({prev_day}) close: ${prev_close:.4f}")
        print(f"    Split day open: ${split_open:.4f}" if split_open != 'N/A' else "    Split day: no data")
        print(f"    Ratio: {ratio:.4f}x")
        print(f"    Factor file date: {prev_day.replace('-', '')}")
