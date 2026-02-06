"""
Convert Databento zstd-compressed CSV data to LEAN format.

Databento format:
- zstd compressed CSV files
- Columns: ts_event,rtype,publisher_id,instrument_id,open,high,low,close,volume,symbol
- ts_event format: 2018-05-01T08:04:00.000000000Z

LEAN minute data format:
- One ZIP file per day: {YYYYMMDD}_trade.zip
- Inside ZIP: {YYYYMMDD}_{symbol}_minute_trade.csv
- CSV format: milliseconds_since_midnight,open*10000,high*10000,low*10000,close*10000,volume
- No headers

SPLIT DE-ADJUSTMENT:
Databento retroactively reprocesses historical OHLCV data, which bakes
corporate action adjustments (splits) into the bars. Since we need RAW
(unadjusted) prices for LEAN with DataNormalizationMode.Raw, we must
reverse these adjustments.

The approach: detect price discontinuities (jumps) between consecutive
trading days. Each jump corresponds to a split boundary. The LAST segment
(most recent data) is already at raw prices (captured in real-time, never
reprocessed). We work backwards from the last segment, multiplying by the
inverse of each jump to undo the adjustment.

Known splits baked into Databento data (as of Jan 2026 download):
  SQQQ: 1:5 reverse splits on 2019-05-24, 2020-08-18, 2022-01-13,
        2024-11-07, 2025-11-20 (data ÷5 before each date)
  TQQQ: 2:1 forward splits on 2018-05-24, 2021-01-21, 2022-01-13,
        2025-11-20 (data ×2 before each date, so ÷2 to correct)
  QQQ:  No splits detected
"""

import os
import csv
import zipfile
import zstandard as zstd
import io
from datetime import datetime, date as date_type
from pathlib import Path
from collections import defaultdict


# ── Split correction table ──────────────────────────────────────────────
# Each entry: (date_str, correction_factor)
# "Before this date, multiply all OHLC prices by this factor"
# Factors are cumulative and applied from most-recent to oldest.
#
# These were determined by running find_price_jumps.py on the Databento
# source data and cross-referencing against Alpaca raw prices.
#
# SQQQ had 1:5 reverse splits. Databento divided pre-split prices by 5.
# To get raw prices back, we multiply by 5 for each split boundary.
#
# TQQQ had 2:1 forward splits. Databento multiplied pre-split prices by 2.
# To get raw prices back, we divide by 2 for each split boundary.
SPLIT_CORRECTIONS = {
    'SQQQ': [
        # (transition_date, factor_to_undo_one_split)
        # Listed newest-first. Each date is where the jump occurs.
        # Before 2025-11-20: prices are ÷5 → multiply by 5
        ('2025-11-20', 5.0),
        # Before 2024-11-07: another ÷5 on top → multiply by 5 more
        ('2024-11-07', 5.0),
        # Before 2022-01-13: another ÷5 on top
        ('2022-01-13', 5.0),
        # Before 2020-08-18: another ÷5 on top
        ('2020-08-18', 5.0),
        # Before 2019-05-24: another ÷5 on top
        ('2019-05-24', 5.0),
    ],
    'TQQQ': [
        # Before 2025-11-20: prices are ×2 → divide by 2
        ('2025-11-20', 0.5),
        # Before 2022-01-13: another ×2 on top → divide by 2 more
        ('2022-01-13', 0.5),
        # Before 2021-01-21: another ×2 on top
        ('2021-01-21', 0.5),
        # Before 2018-05-24: another ×2 on top  (but our data starts 2018-05-01)
        ('2018-05-24', 0.5),
    ],
    # QQQ: no splits detected
}


def build_correction_ranges(symbol: str) -> list:
    """Build a list of (start_date, end_date, cumulative_factor) ranges.
    
    Returns sorted list of (date_start, date_end, factor) where factor
    is the cumulative multiplier to apply to OHLC prices in that range.
    Dates are inclusive on start, exclusive on end.
    The last range has end_date = None (no upper bound).
    """
    corrections = SPLIT_CORRECTIONS.get(symbol.upper(), [])
    if not corrections:
        return []  # No corrections needed
    
    # Sort by date ascending
    sorted_corrections = sorted(corrections, key=lambda x: x[0])
    
    ranges = []
    cumulative_factor = 1.0
    
    # Build cumulative factors from oldest to newest
    # All splits compound: if there are 3 splits of 5x each before the
    # most recent data, the oldest segment needs 5*5*5 = 125x correction
    factors_by_date = []
    for date_str, factor in sorted_corrections:
        factors_by_date.append((date_str, factor))
    
    # The LAST segment (after the newest transition date) has factor 1.0
    # (already raw prices). Working backwards, each earlier segment needs
    # one more factor applied.
    #
    # Example for SQQQ with transitions at D1, D2, D3 (oldest to newest):
    #   After D3: factor = 1.0 (raw)
    #   D2 to D3: factor = 5.0 (one split to undo)
    #   D1 to D2: factor = 5.0 * 5.0 = 25.0 (two splits)
    #   Before D1: factor = 5.0 * 5.0 * 5.0 = 125.0 (three splits)
    
    # Compute cumulative factors from newest to oldest
    transition_dates = [d for d, _ in factors_by_date]  # ascending order
    transition_factors = [f for _, f in factors_by_date]  # ascending order
    
    # Build ranges from newest to oldest
    cum = 1.0
    range_specs = []  # Will be built in reverse
    
    # After the last transition: factor 1.0 (no correction)
    # We don't need to store this — it's the default
    
    # For each transition going backwards (newest first)
    for i in range(len(transition_dates) - 1, -1, -1):
        cum *= transition_factors[i]
        if i > 0:
            range_specs.append((transition_dates[i - 1], transition_dates[i], cum))
        else:
            range_specs.append((None, transition_dates[i], cum))
    
    # Sort by date for easy lookup
    range_specs.sort(key=lambda x: x[1])
    
    return range_specs


def get_price_correction_factor(symbol: str, date_str: str, correction_ranges: list) -> float:
    """Get the price correction factor for a given symbol and date.
    
    Returns the multiplier to apply to OHLC prices.
    Returns 1.0 if no correction is needed.
    """
    if not correction_ranges:
        return 1.0
    
    for start_date, end_date, factor in correction_ranges:
        # Range is [start_date, end_date)
        if start_date is None:
            if date_str < end_date:
                return factor
        else:
            if start_date <= date_str < end_date:
                return factor
    
    return 1.0  # After the last transition — already raw


def parse_databento_timestamp(ts_str: str) -> tuple:
    """Parse databento timestamp and return (date, milliseconds_since_midnight)."""
    # Format: 2018-05-01T08:04:00.000000000Z
    # Remove nanoseconds and Z suffix
    ts_str = ts_str.replace('Z', '')
    
    # Split at the decimal point to handle nanoseconds
    if '.' in ts_str:
        ts_str = ts_str.split('.')[0]
    
    dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
    
    # Calculate milliseconds since midnight
    ms_since_midnight = (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000
    
    return dt.date(), ms_since_midnight


def decompress_and_read_zst(zst_path: str) -> list:
    """Decompress zstd file and read CSV data."""
    rows = []
    
    with open(zst_path, 'rb') as f:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(f) as reader:
            text_stream = io.TextIOWrapper(reader, encoding='utf-8')
            csv_reader = csv.DictReader(text_stream)
            
            for row in csv_reader:
                rows.append(row)
    
    return rows


def convert_databento_to_lean(input_zst: str, output_dir: str, symbol: str):
    """Convert a databento zstd CSV file to LEAN format ZIP files.
    
    Applies split de-adjustment to produce raw (unadjusted) prices.
    """
    symbol_lower = symbol.lower()
    symbol_upper = symbol.upper()
    
    # Build correction ranges for this symbol
    correction_ranges = build_correction_ranges(symbol_upper)
    if correction_ranges:
        print(f"  Split correction ranges for {symbol_upper}:")
        for start, end, factor in correction_ranges:
            start_label = start if start else "DATA_START"
            print(f"    {start_label} to {end}: multiply by {factor:.1f}")
        print(f"    After {correction_ranges[-1][1]}: no correction (raw prices)")
    else:
        print(f"  No split corrections needed for {symbol_upper}")
    
    # Group data by date
    data_by_date = defaultdict(list)
    
    print(f"  Decompressing and reading {input_zst}...")
    
    rows = decompress_and_read_zst(input_zst)
    print(f"  Read {len(rows)} rows")
    
    corrected_count = 0
    skipped_count = 0
    
    for row in rows:
        try:
            # Parse timestamp
            date, ms_since_midnight = parse_databento_timestamp(row['ts_event'])
            date_str = date.strftime("%Y-%m-%d")
            
            # Get raw prices from Databento
            raw_open = float(row['open'])
            raw_high = float(row['high'])
            raw_low = float(row['low'])
            raw_close = float(row['close'])
            volume = int(float(row['volume']))
            
            # Skip rows with empty/zero prices
            if raw_open == 0 and raw_close == 0:
                skipped_count += 1
                continue
            
            # Apply split de-adjustment
            factor = get_price_correction_factor(symbol_upper, date_str, correction_ranges)
            
            if factor != 1.0:
                raw_open *= factor
                raw_high *= factor
                raw_low *= factor
                raw_close *= factor
                corrected_count += 1
            
            # Convert prices to scaled integers (multiply by 10000 for LEAN)
            open_price = int(round(raw_open * 10000))
            high_price = int(round(raw_high * 10000))
            low_price = int(round(raw_low * 10000))
            close_price = int(round(raw_close * 10000))
            
            # Store as LEAN format line
            lean_line = f"{ms_since_midnight},{open_price},{high_price},{low_price},{close_price},{volume}"
            data_by_date[date].append((ms_since_midnight, lean_line))
            
        except (KeyError, ValueError) as e:
            print(f"  Skipping row due to error: {e}")
            continue
    
    if corrected_count > 0:
        print(f"  Applied split correction to {corrected_count:,} bars")
    if skipped_count > 0:
        print(f"  Skipped {skipped_count:,} bars with zero prices")
    
    # Create output directory for symbol
    symbol_dir = Path(output_dir) / symbol_lower
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"  Converting {len(data_by_date)} trading days to LEAN format...")
    
    # Create ZIP file for each date
    files_created = 0
    for date, rows in sorted(data_by_date.items()):
        # Sort by milliseconds since midnight
        rows.sort(key=lambda x: x[0])
        
        date_str = date.strftime("%Y%m%d")
        zip_name = f"{date_str}_trade.zip"
        csv_name = f"{date_str}_{symbol_lower}_minute_trade.csv"
        
        zip_path = symbol_dir / zip_name
        
        # Write CSV inside ZIP
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            csv_content = '\n'.join(line for _, line in rows)
            zf.writestr(csv_name, csv_content)
        
        files_created += 1
    
    print(f"  Created {files_created} zip files for {symbol}")
    return len(data_by_date)


def main():
    # Source data location - Databento zstd compressed files
    source_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\databento")
    
    # LEAN data output location
    output_dir = Path(r"c:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute")
    
    # File pattern: xnas-itch-20180501-20260114.ohlcv-1m.{SYMBOL}.csv.zst
    symbols = ['TQQQ', 'SQQQ', 'QQQ']
    
    print("=" * 70)
    print("Databento to LEAN Data Format Converter")
    print("=" * 70)
    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print("=" * 70)
    
    total_days = 0
    
    for symbol in symbols:
        # Look for zstd compressed CSV files
        zst_files = list(source_dir.glob(f"*.{symbol}.csv.zst"))
        
        if not zst_files:
            print(f"\n[!] No zstd files found for {symbol}")
            continue
        
        print(f"\nProcessing {symbol}:")
        
        for zst_file in zst_files:
            days = convert_databento_to_lean(str(zst_file), str(output_dir), symbol)
            total_days += days
    
    print("\n" + "=" * 70)
    print(f"[OK] Conversion complete! Total: {total_days} trading days converted")
    print(f"Output location: {output_dir}")
    print("=" * 70)
    
    # Verify output
    print("\nVerifying output:")
    for symbol in symbols:
        symbol_dir = output_dir / symbol.lower()
        if symbol_dir.exists():
            files = list(symbol_dir.glob("*_trade.zip"))
            if files:
                first_date = min(f.name[:8] for f in files)
                last_date = max(f.name[:8] for f in files)
                print(f"  {symbol}: {len(files)} zip files ({first_date} to {last_date})")
            else:
                print(f"  {symbol}: No files created")
        else:
            print(f"  {symbol}: Directory not found")


if __name__ == "__main__":
    main()
