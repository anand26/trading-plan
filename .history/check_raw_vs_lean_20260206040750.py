"""Compare raw Databento prices vs LEAN converted prices for SQQQ around split dates."""
import zstandard as zstd
import csv
import io
import zipfile
from pathlib import Path
from datetime import datetime

# ============================================================
# 1. Read RAW Databento .zst file (sample around split dates)
# ============================================================
zst_file = Path(r"C:\Users\anand\Documents\trading_plan\Data\databento\xnas-itch-20180501-20260114.ohlcv-1m.SQQQ.csv.zst")

print("=" * 80)
print("RAW DATABENTO DATA (from .zst)")
print("=" * 80)

# Key dates to check:
# Jan 12, 2023 - SQQQ 1:5 reverse split (pre-split ~$25, post-split ~$125)
# Jan 11, 2024 - SQQQ 1:5 reverse split (pre-split ~$13, post-split ~$65)  
# Nov 20, 2025 - recent date (should be ~$65-80 if raw)
check_dates = ["2023-01-11", "2023-01-12", "2023-01-13",
               "2024-01-11", "2024-01-12", "2024-01-16",
               "2025-11-20", "2025-11-21",
               "2026-01-06", "2026-01-07"]

dctx = zstd.ZstdDecompressor()
found_rows = {d: [] for d in check_dates}
header = None

with open(zst_file, "rb") as fh:
    reader = dctx.stream_reader(fh)
    text_stream = io.TextIOWrapper(reader, encoding="utf-8")
    csv_reader = csv.reader(text_stream)
    
    for i, row in enumerate(csv_reader):
        if i == 0:
            header = row
            print(f"Columns: {row}")
            continue
        
        # Get the timestamp/date from the row
        # Databento format: ts_event is usually first column (nanosecond unix timestamp)
        ts_str = row[0]  # ts_event
        
        # Convert nanosecond timestamp to date string
        try:
            ts_ns = int(ts_str)
            dt = datetime.utcfromtimestamp(ts_ns / 1e9)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        except:
            # Maybe it's already a date string
            date_str = ts_str[:10]
            time_str = ts_str[11:16] if len(ts_str) > 16 else ""
        
        # Capture first bar of each check date (market open ~14:30 UTC / 9:30 ET)
        if date_str in check_dates:
            if len(found_rows[date_str]) < 2:  # just first 2 bars
                found_rows[date_str].append((time_str, row))
        
        # Early exit once we have all dates
        if all(len(v) > 0 for v in found_rows.values()):
            # Check if we've passed all dates
            if date_str > "2026-01-08":
                break

print(f"\nHeader: {header}\n")

for date in check_dates:
    rows = found_rows[date]
    if rows:
        for time_str, row in rows[:1]:
            # Databento OHLCV columns vary, but typically:
            # open, high, low, close are in columns after ts_event
            # Prices in Databento are in fixed-point (divide by 1e9 for dollars)
            print(f"  {date} {time_str}: ", end="")
            # Print all values to see the format
            for j, val in enumerate(row):
                col_name = header[j] if header and j < len(header) else f"col{j}"
                if "open" in col_name.lower() or "high" in col_name.lower() or "low" in col_name.lower() or "close" in col_name.lower():
                    try:
                        raw_val = int(val)
                        dollar_val = raw_val / 1e9  # Databento fixed-point
                        print(f"{col_name}=${dollar_val:.4f} ", end="")
                    except:
                        print(f"{col_name}={val} ", end="")
            print()
    else:
        print(f"  {date}: NO DATA FOUND")

# ============================================================
# 2. Read LEAN converted data for same dates
# ============================================================
print("\n" + "=" * 80)
print("LEAN CONVERTED DATA (from .zip)")
print("=" * 80)

lean_base = Path(r"C:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute\sqqq")

for date in check_dates:
    dt = datetime.strptime(date, "%Y-%m-%d")
    zip_name = f"{dt.strftime('%Y%m%d')}_trade.zip"
    zip_path = lean_base / zip_name
    
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as f:
                lines = f.read().decode("utf-8").strip().split("\n")
                # LEAN minute format: Milliseconds,Open,High,Low,Close,Volume
                # Prices are × 10000
                first_line = lines[0]
                parts = first_line.split(",")
                ms = int(parts[0])
                o = int(parts[1]) / 10000
                h = int(parts[2]) / 10000
                l = int(parts[3]) / 10000
                c = int(parts[4]) / 10000
                v = int(parts[5])
                time_m = ms // 60000
                hour = time_m // 60
                minute = time_m % 60
                print(f"  {date} {hour:02d}:{minute:02d}: Open=${o:.4f}  High=${h:.4f}  Low=${l:.4f}  Close=${c:.4f}  Vol={v}")
    else:
        print(f"  {date}: ZIP NOT FOUND ({zip_path.name})")
