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

NOTE ON SPLIT HANDLING:
Databento data with stype_in=raw_symbol provides RAW (unadjusted) prices.
Price jumps in the data (e.g., SQQQ going from $14 to $70 overnight) are
REAL corporate actions (reverse splits), not data errors.

LEAN handles splits via factor files in:
  quantconnect-lean/Data/equity/usa/factor_files/{symbol}.csv
These tell LEAN when splits occurred so it can:
  - Emit Split events to the algorithm
  - Adjust position quantities at split boundaries
  - Prevent false P&L from split price jumps

This converter does NO price adjustment — it passes through raw prices
exactly as received from Databento.
"""

import os
import csv
import zipfile
import zstandard as zstd
import io
from datetime import datetime
from pathlib import Path
from collections import defaultdict


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
    
    Passes through raw prices without any adjustment. Split handling is
    done by LEAN via factor files, not by this converter.
    """
    symbol_lower = symbol.lower()
    
    # Group data by date
    data_by_date = defaultdict(list)
    
    print(f"  Decompressing and reading {input_zst}...")
    
    rows = decompress_and_read_zst(input_zst)
    print(f"  Read {len(rows)} rows")
    
    skipped_count = 0
    
    for row in rows:
        try:
            # Parse timestamp
            date, ms_since_midnight = parse_databento_timestamp(row['ts_event'])
            
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
