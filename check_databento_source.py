"""Check Databento source data for SQQQ and TQQQ around Nov 19-20 transition"""
import zstandard as zstd
import io
import csv
from pathlib import Path

source_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\databento")

for symbol in ['SQQQ', 'TQQQ']:
    print(f"\n{'='*60}")
    print(f"  {symbol} Databento Source Data")
    print(f"{'='*60}")
    
    zst_files = list(source_dir.glob(f"*.{symbol}.csv.zst"))
    if not zst_files:
        print(f"  No file found for {symbol}")
        continue
    
    zst_file = zst_files[0]
    print(f"  File: {zst_file.name}")
    
    target_dates = ['2025-11-14', '2025-11-17', '2025-11-19', '2025-11-20', '2025-11-21']
    
    with open(zst_file, 'rb') as f:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(f) as reader:
            text_stream = io.TextIOWrapper(reader, encoding='utf-8')
            csv_reader = csv.DictReader(text_stream)
            
            for target_date in target_dates:
                found_rows = []
                # Reset to beginning - can't seek in streaming, so read through
                break  # Can't re-read, need different approach
    
    # Read all relevant rows in one pass
    with open(zst_file, 'rb') as f:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(f) as reader:
            text_stream = io.TextIOWrapper(reader, encoding='utf-8')
            csv_reader = csv.DictReader(text_stream)
            
            date_data = {}
            for row in csv_reader:
                ts = row['ts_event']
                date_str = ts[:10]  # YYYY-MM-DD
                
                if date_str in target_dates:
                    if date_str not in date_data:
                        date_data[date_str] = {'first': row, 'last': row, 'count': 0, 'instrument_ids': set()}
                    date_data[date_str]['last'] = row
                    date_data[date_str]['count'] += 1
                    date_data[date_str]['instrument_ids'].add(row.get('instrument_id', 'N/A'))
            
            for date_str in sorted(date_data.keys()):
                d = date_data[date_str]
                first = d['first']
                last = d['last']
                print(f"\n  {date_str} ({d['count']} bars, instrument_ids: {d['instrument_ids']}):")
                print(f"    First bar: open=${float(first['open']):.2f}, close=${float(first['close']):.2f}")
                print(f"    Last bar:  open=${float(last['open']):.2f}, close=${float(last['close']):.2f}")
