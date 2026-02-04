"""
Convert Alpaca CSV data to LEAN format.

LEAN minute data format:
- One ZIP file per day: {YYYYMMDD}_trade.zip
- Inside ZIP: {YYYYMMDD}_{symbol}_minute_trade.csv
- CSV format: milliseconds_since_midnight,open*10000,high*10000,low*10000,close*10000,volume
- No headers
"""

import os
import csv
import zipfile
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import shutil


def parse_timestamp(ts_str: str) -> tuple[datetime, int]:
    """Parse timestamp and return (date, milliseconds_since_midnight)."""
    # Handle format: "2026-01-01 00:00:00+00:00" or "2026-01-01T00:00:00+00:00"
    ts_str = ts_str.replace('T', ' ')
    
    # Remove timezone info for parsing
    if '+' in ts_str:
        ts_str = ts_str.split('+')[0].strip()
    elif '-' in ts_str and ts_str.count('-') > 2:
        # Handle negative timezone offset
        parts = ts_str.rsplit('-', 1)
        if ':' in parts[-1]:
            ts_str = parts[0].strip()
    
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    
    # Calculate milliseconds since midnight
    ms_since_midnight = (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000
    
    return dt.date(), ms_since_midnight


def convert_csv_to_lean(input_csv: str, output_dir: str, symbol: str):
    """Convert a single CSV file to LEAN format ZIP files."""
    symbol_lower = symbol.lower()
    
    # Group data by date
    data_by_date = defaultdict(list)
    
    print(f"Reading {input_csv}...")
    
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Parse timestamp
                date, ms_since_midnight = parse_timestamp(row['Timestamp'])
                
                # Convert prices to scaled integers (multiply by 10000)
                open_price = int(float(row['Open']) * 10000)
                high_price = int(float(row['High']) * 10000)
                low_price = int(float(row['Low']) * 10000)
                close_price = int(float(row['Close']) * 10000)
                volume = int(float(row['Volume']))
                
                # Store as LEAN format line
                lean_line = f"{ms_since_midnight},{open_price},{high_price},{low_price},{close_price},{volume}"
                data_by_date[date].append((ms_since_midnight, lean_line))
                
            except (KeyError, ValueError) as e:
                print(f"  Skipping row due to error: {e}")
                continue
    
    # Create output directory for symbol
    symbol_dir = Path(output_dir) / symbol_lower
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Converting {len(data_by_date)} trading days to LEAN format...")
    
    # Create ZIP file for each date
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
        
        print(f"  Created {zip_name} with {len(rows)} bars")
    
    return len(data_by_date)


def main():
    # Source data location - Alpaca downloaded CSV files
    source_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\alpaca")
    
    # LEAN data output location - LEAN's test data directory
    output_dir = Path(r"c:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute")
    
    symbols = ['TQQQ', 'SQQQ', 'QQQ']
    
    print("=" * 60)
    print("LEAN Data Format Converter")
    print("=" * 60)
    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print("=" * 60)
    
    total_days = 0
    
    for symbol in symbols:
        # Look for CSV files
        csv_files = list(source_dir.glob(f"{symbol}_*.csv"))
        
        if not csv_files:
            print(f"\n[!] No CSV files found for {symbol}")
            continue
        
        print(f"\nProcessing {symbol}:")
        
        for csv_file in csv_files:
            days = convert_csv_to_lean(str(csv_file), str(output_dir), symbol)
            total_days += days
    
    print("\n" + "=" * 60)
    print(f"[OK] Conversion complete! Total: {total_days} trading days")
    print(f"Output location: {output_dir}")
    print("=" * 60)
    
    # Verify output
    print("\nVerifying output:")
    for symbol in symbols:
        symbol_dir = output_dir / symbol.lower()
        if symbol_dir.exists():
            files = list(symbol_dir.glob("*_trade.zip"))
            print(f"  {symbol}: {len(files)} zip files created")


if __name__ == "__main__":
    main()
