"""Analyze the exact transition point in Databento data and determine split factors"""
import zstandard as zstd
import io
import csv
from pathlib import Path

source_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\databento")

# Check SQQQ day by day around the transition
print("="*70)
print("SQQQ: Finding exact transition date")
print("="*70)

zst_file = list(source_dir.glob("*.SQQQ.csv.zst"))[0]

with open(zst_file, 'rb') as f:
    dctx = zstd.ZstdDecompressor()
    with dctx.stream_reader(f) as reader:
        text_stream = io.TextIOWrapper(reader, encoding='utf-8')
        csv_reader = csv.DictReader(text_stream)
        
        # Track last close price to detect the jump
        daily_last_close = {}
        daily_first_open = {}
        daily_instrument_ids = {}
        
        for row in csv_reader:
            ts = row['ts_event']
            date_str = ts[:10]
            close = float(row['close'])
            open_p = float(row['open'])
            iid = row.get('instrument_id', '')
            
            if date_str not in daily_first_open:
                daily_first_open[date_str] = open_p
                daily_instrument_ids[date_str] = set()
            daily_last_close[date_str] = close
            daily_instrument_ids[date_str].add(iid)

# Find jumps > 2x between consecutive days
print("\nSQQQ daily close prices (looking for jump):")
dates = sorted(daily_last_close.keys())
prev_close = None
prev_date = None

# Print around the known transition area and any other jumps
for i, d in enumerate(dates):
    close = daily_last_close[d]
    first_open = daily_first_open[d]
    
    if prev_close and prev_close > 0:
        ratio = first_open / prev_close
        if ratio > 2.0 or ratio < 0.5:
            print(f"\n  *** PRICE JUMP DETECTED ***")
            print(f"  {prev_date}: close=${prev_close:.2f}")
            print(f"  {d}: open=${first_open:.2f}  (ratio: {ratio:.2f}x, instrument_ids: {daily_instrument_ids[d]})")
            print(f"  Jump factor: {ratio:.4f}")
            
    prev_close = close
    prev_date = d

# Now check TQQQ
print("\n\n" + "="*70)
print("TQQQ: Finding exact transition date")
print("="*70)

zst_file = list(source_dir.glob("*.TQQQ.csv.zst"))[0]

with open(zst_file, 'rb') as f:
    dctx = zstd.ZstdDecompressor()
    with dctx.stream_reader(f) as reader:
        text_stream = io.TextIOWrapper(reader, encoding='utf-8')
        csv_reader = csv.DictReader(text_stream)
        
        daily_last_close = {}
        daily_first_open = {}
        daily_instrument_ids = {}
        
        for row in csv_reader:
            ts = row['ts_event']
            date_str = ts[:10]
            close = float(row['close'])
            open_p = float(row['open'])
            iid = row.get('instrument_id', '')
            
            if date_str not in daily_first_open:
                daily_first_open[date_str] = open_p
                daily_instrument_ids[date_str] = set()
            daily_last_close[date_str] = close
            daily_instrument_ids[date_str].add(iid)

print("\nTQQQ daily close prices (looking for jumps):")
dates = sorted(daily_last_close.keys())
prev_close = None
prev_date = None

for i, d in enumerate(dates):
    close = daily_last_close[d]
    first_open = daily_first_open[d]
    
    if prev_close and prev_close > 0:
        ratio = first_open / prev_close
        if ratio > 1.5 or ratio < 0.67:
            print(f"\n  *** PRICE JUMP DETECTED ***")
            print(f"  {prev_date}: close=${prev_close:.2f}")
            print(f"  {d}: open=${first_open:.2f}  (ratio: {ratio:.2f}x, instrument_ids: {daily_instrument_ids[d]})")
            print(f"  Jump factor: {ratio:.4f}")
    
    prev_close = close
    prev_date = d

# Also check QQQ for reference
print("\n\n" + "="*70)
print("QQQ: Checking for any jumps")
print("="*70)

zst_file = list(source_dir.glob("*.QQQ.csv.zst"))[0]

with open(zst_file, 'rb') as f:
    dctx = zstd.ZstdDecompressor()
    with dctx.stream_reader(f) as reader:
        text_stream = io.TextIOWrapper(reader, encoding='utf-8')
        csv_reader = csv.DictReader(text_stream)
        
        daily_last_close = {}
        daily_first_open = {}
        
        for row in csv_reader:
            ts = row['ts_event']
            date_str = ts[:10]
            close = float(row['close'])
            open_p = float(row['open'])
            
            if date_str not in daily_first_open:
                daily_first_open[date_str] = open_p
            daily_last_close[date_str] = close

print("\nQQQ daily prices (looking for jumps):")
dates = sorted(daily_last_close.keys())
prev_close = None
prev_date = None
jumps = 0

for d in dates:
    close = daily_last_close[d]
    first_open = daily_first_open[d]
    
    if prev_close and prev_close > 0:
        ratio = first_open / prev_close
        if ratio > 1.5 or ratio < 0.67:
            print(f"  JUMP: {prev_date} close=${prev_close:.2f} -> {d} open=${first_open:.2f} (ratio: {ratio:.2f}x)")
            jumps += 1
    
    prev_close = close
    prev_date = d

if jumps == 0:
    print("  No jumps detected - QQQ data appears consistent")
