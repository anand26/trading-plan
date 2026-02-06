"""
Analyze Databento data segments to determine the correct raw price adjustment factors.

Databento delivers "continuous" data that is backward-adjusted at each corporate event.
This means:
- The MOST RECENT segment has real/raw prices
- Each older segment is divided by the cumulative split factor

For SQQQ (1:5 reverse splits):
- Most recent segment (after last jump): RAW prices
- Previous segment: prices ÷ 5
- Two segments back: prices ÷ 25
- etc.

For TQQQ (2:1 forward splits):
- Most recent segment (after last jump): RAW prices  
- Previous segment: prices × 2
- Two segments back: prices × 4
- etc.

We need to identify each segment and multiply by the correct factor to get raw prices.
"""
import zstandard as zstd
import io
import csv
from pathlib import Path
from datetime import datetime

source_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\databento")


def find_segments(symbol):
    """Find all price segments in the Databento data for a symbol."""
    zst_file = list(source_dir.glob(f"*.{symbol}.csv.zst"))[0]
    
    segments = []
    daily_data = {}
    
    with open(zst_file, 'rb') as f:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(f) as reader:
            text_stream = io.TextIOWrapper(reader, encoding='utf-8')
            csv_reader = csv.DictReader(text_stream)
            
            for row in csv_reader:
                ts = row['ts_event']
                date_str = ts[:10]
                try:
                    close = float(row['close'])
                    open_p = float(row['open'])
                except ValueError:
                    continue
                iid = row.get('instrument_id', '')
                
                if date_str not in daily_data:
                    daily_data[date_str] = {'first_open': open_p, 'instrument_ids': set()}
                daily_data[date_str]['last_close'] = close
                daily_data[date_str]['instrument_ids'].add(iid)
    
    # Find jump points
    dates = sorted(daily_data.keys())
    jump_dates = []
    
    for i in range(1, len(dates)):
        prev_close = daily_data[dates[i-1]]['last_close']
        curr_open = daily_data[dates[i]]['first_open']
        
        if prev_close > 0:
            ratio = curr_open / prev_close
            if ratio > 1.5 or ratio < 0.67:
                jump_dates.append({
                    'date': dates[i],
                    'prev_date': dates[i-1],
                    'prev_close': prev_close,
                    'curr_open': curr_open,
                    'ratio': ratio
                })
    
    # Build segments
    segment_start = dates[0]
    for jump in jump_dates:
        segments.append({
            'start': segment_start,
            'end': jump['prev_date'],
            'sample_close': jump['prev_close']
        })
        segment_start = jump['date']
    
    # Last segment (most recent = raw prices)
    segments.append({
        'start': segment_start,
        'end': dates[-1],
        'sample_close': daily_data[dates[-1]]['last_close']
    })
    
    return segments, jump_dates


print("="*70)
print("SQQQ Segment Analysis")
print("="*70)
sqqq_segments, sqqq_jumps = find_segments('SQQQ')

print(f"\nFound {len(sqqq_jumps)} price jumps:")
for j in sqqq_jumps:
    print(f"  {j['prev_date']} -> {j['date']}: ${j['prev_close']:.2f} -> ${j['curr_open']:.2f} (ratio: {j['ratio']:.4f})")

print(f"\n{len(sqqq_segments)} data segments:")
# The LAST segment is raw. Work backwards to compute factors.
# SQQQ has 1:5 reverse splits, so each jump backwards divides by ~5
cumulative_factor = 1.0
for i, seg in enumerate(reversed(sqqq_segments)):
    idx = len(sqqq_segments) - 1 - i
    print(f"  Segment {idx}: {seg['start']} to {seg['end']} | sample close: ${seg['sample_close']:.2f} | multiply by: {cumulative_factor:.1f}")
    if i < len(sqqq_jumps):
        # The jump ratio tells us the factor
        jump = sqqq_jumps[len(sqqq_jumps) - 1 - i]
        cumulative_factor *= jump['ratio']  # ratio is new/old, so this scales up old prices

# Actual known SQQQ split history:
print("\n\nKnown SQQQ reverse splits (1:5):")
print("  Jan 12, 2024")
print("  Jan 12, 2023")
print("  Aug 18, 2020")  
print("  May 24, 2019")

# For our backtest period (Jan 2025 - Jan 2026), we need to fix:
# - Everything BEFORE Nov 20, 2025 is ÷5 (one reverse split behind)
print("\n\nFor backtest period Jan 2025 - Jan 2026:")
print("  Jan 2025 - Nov 19, 2025: multiply SQQQ prices by 5")
print("  Nov 20, 2025 - Jan 2026: prices are already RAW (correct)")


print("\n\n" + "="*70)
print("TQQQ Segment Analysis")
print("="*70)
tqqq_segments, tqqq_jumps = find_segments('TQQQ')

print(f"\nFound {len(tqqq_jumps)} price jumps:")
for j in tqqq_jumps:
    print(f"  {j['prev_date']} -> {j['date']}: ${j['prev_close']:.2f} -> ${j['curr_open']:.2f} (ratio: {j['ratio']:.4f})")

print(f"\n{len(tqqq_segments)} data segments:")
cumulative_factor = 1.0
for i, seg in enumerate(reversed(tqqq_segments)):
    idx = len(tqqq_segments) - 1 - i
    print(f"  Segment {idx}: {seg['start']} to {seg['end']} | sample close: ${seg['sample_close']:.2f} | multiply by: {cumulative_factor:.4f}")
    if i < len(tqqq_jumps):
        jump = tqqq_jumps[len(tqqq_jumps) - 1 - i]
        cumulative_factor *= jump['ratio']

# Known TQQQ split history:
print("\n\nKnown TQQQ forward splits (2:1):")
print("  Jan 13, 2025")
print("  Jan 13, 2022")
print("  Jan 21, 2021")

print("\n\nFor backtest period Jan 2025 - Jan 2026:")
print("  Jan 2025 - Nov 19, 2025: multiply TQQQ prices by 0.5 (÷2)")
print("  Nov 20, 2025 - Jan 2026: prices are already RAW (correct)")
print("  WAIT - need to verify: is the LAST segment really raw?")

# Verify: check last segment price against known real price
print("\n\nVerification against known prices:")
print("  SQQQ on Jan 14, 2026 (last data date):")
print(f"    Databento: ${sqqq_segments[-1]['sample_close']:.2f}")
print("    Expected real price: ~$57-60")
print("  TQQQ on Jan 14, 2026 (last data date):")
print(f"    Databento: ${tqqq_segments[-1]['sample_close']:.2f}")
print("    Expected real price: ~$85-90")
