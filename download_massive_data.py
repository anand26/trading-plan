"""
Download 1-minute stock data from Massive.com using boto3 SDK.
Fetches TQQQ, SQQQ, and QQQ data for the last 2 years.

Data is stored as daily CSV.GZ files at:
  us_stocks_sip/minute_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz

Each file contains all symbols for that trading day.
We download the files and filter for our target symbols.
"""

import boto3
from botocore.config import Config
from datetime import datetime, timedelta
import gzip
import pandas as pd
from pathlib import Path
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Initialize a session using your credentials (GitHub OAuth)
session = boto3.Session(
    aws_access_key_id='49396bfa-bc7d-4998-b177-bfe701369439',
    aws_secret_access_key='WCZBkB2cU6m8sU4YNejf5lR704GPwuQh',
)

# Create a client with your session and specify the endpoint
s3 = session.client(
    's3',
    endpoint_url='https://files.massive.com',
    config=Config(signature_version='s3v4'),
)

# Configuration
SYMBOLS = ['TQQQ', 'SQQQ', 'QQQ']
PREFIX = 'us_stocks_sip/minute_aggs_v1'
OUTPUT_DIR = Path('Data/massive')
BUCKET_NAME = 'flatfiles'

# Calculate date range (last 2 years)
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=365 * 2)


def list_buckets():
    """List all available buckets."""
    try:
        response = s3.list_buckets()
        print("Available buckets:")
        for bucket in response.get('Buckets', []):
            print(f"  - {bucket['Name']}")
        return [b['Name'] for b in response.get('Buckets', [])]
    except Exception as e:
        print(f"Error listing buckets: {e}")
        return []


def check_bucket_access(bucket_name: str):
    """Check if we can access a bucket and list its contents."""
    print(f"\nChecking access to bucket: {bucket_name}")
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=10)
        if 'Contents' in response:
            print(f"  Contents found:")
            for obj in response['Contents'][:5]:
                print(f"    - {obj['Key']}")
        if 'CommonPrefixes' in response:
            print(f"  Prefixes found:")
            for prefix in response.get('CommonPrefixes', [])[:5]:
                print(f"    - {prefix['Prefix']}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_file_download():
    """Test downloading files from different data sources."""
    test_files = [
        # Try different data sources
        "global_crypto/day_aggs_v1/2013/11/2013-11-01.csv.gz",
        "us_stocks_sip/minute_aggs_v1/2003/09/2003-09-10.csv.gz",
        "us_stocks_sip/minute_aggs_v1/2024/01/2024-01-15.csv.gz",
        "us_stocks_sip/minute_aggs_v1/2025/01/2025-01-10.csv.gz",
    ]
    
    accessible_prefixes = []
    
    for test_key in test_files:
        print(f"\nTesting download of: {test_key}")
        
        # Method 1: Direct get_object
        try:
            response = s3.get_object(Bucket=BUCKET_NAME, Key=test_key)
            content = response['Body'].read()
            print(f"  [OK] Direct download: {len(content)} bytes")
            accessible_prefixes.append(test_key.split('/')[0])
            continue
        except Exception as e:
            print(f"  [FAIL] Direct download: {e}")
        
        # Method 2: Try with presigned URL
        try:
            import requests
            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET_NAME, 'Key': test_key},
                ExpiresIn=3600
            )
            print(f"  Trying presigned URL...")
            resp = requests.get(url)
            if resp.status_code == 200:
                print(f"  [OK] Presigned URL: {len(resp.content)} bytes")
                accessible_prefixes.append(test_key.split('/')[0])
                continue
            else:
                print(f"  [FAIL] Presigned URL: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [FAIL] Presigned URL: {e}")
    
    return list(set(accessible_prefixes))


def get_trading_days(start_date: datetime, end_date: datetime) -> list:
    """Generate list of trading days (weekdays only, holidays not filtered)."""
    trading_days = []
    current = start_date
    while current <= end_date:
        # Skip weekends (5 = Saturday, 6 = Sunday)
        if current.weekday() < 5:
            trading_days.append(current)
        current += timedelta(days=1)
    return trading_days


def download_and_filter_day(date: datetime, symbols: list) -> pd.DataFrame:
    """Download a day's data and filter for specific symbols."""
    key = f"{PREFIX}/{date.year}/{date.month:02d}/{date.strftime('%Y-%m-%d')}.csv.gz"
    
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        
        # Decompress and read CSV
        with gzip.GzipFile(fileobj=io.BytesIO(response['Body'].read())) as gz:
            df = pd.read_csv(gz)
        
        # Filter for target symbols (try common column names)
        symbol_col = None
        for col in ['ticker', 'symbol', 'Symbol', 'Ticker', 'sym']:
            if col in df.columns:
                symbol_col = col
                break
        
        if symbol_col:
            df = df[df[symbol_col].isin(symbols)]
        
        if not df.empty:
            df['date'] = date.strftime('%Y-%m-%d')
            print(f"[OK] {date.strftime('%Y-%m-%d')}: {len(df)} rows")
        
        return df
        
    except s3.exceptions.NoSuchKey:
        # File doesn't exist (holiday or no data)
        return pd.DataFrame()
    except Exception as e:
        if 'NoSuchKey' in str(e) or '404' in str(e):
            return pd.DataFrame()
        print(f"[FAIL] {date.strftime('%Y-%m-%d')}: {e}")
        return pd.DataFrame()


def download_all_data(symbols: list, start_date: datetime, end_date: datetime) -> dict:
    """Download all data for the given date range."""
    trading_days = get_trading_days(start_date, end_date)
    print(f"\nDownloading {len(trading_days)} trading days of data...")
    print(f"Symbols: {symbols}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    all_data = {symbol: [] for symbol in symbols}
    
    # Process days sequentially to avoid rate limiting
    for i, date in enumerate(trading_days):
        if i % 50 == 0:
            print(f"\nProgress: {i}/{len(trading_days)} days processed...")
        
        df = download_and_filter_day(date, symbols)
        
        if not df.empty:
            # Determine symbol column
            symbol_col = None
            for col in ['ticker', 'symbol', 'Symbol', 'Ticker', 'sym']:
                if col in df.columns:
                    symbol_col = col
                    break
            
            if symbol_col:
                for symbol in symbols:
                    symbol_df = df[df[symbol_col] == symbol]
                    if not symbol_df.empty:
                        all_data[symbol].append(symbol_df)
    
    return all_data


def save_data(all_data: dict, output_dir: Path):
    """Save downloaded data to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for symbol, dfs in all_data.items():
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            output_file = output_dir / f"{symbol}_1min_{START_DATE.strftime('%Y%m%d')}_{END_DATE.strftime('%Y%m%d')}.csv"
            combined.to_csv(output_file, index=False)
            print(f"Saved {symbol}: {len(combined)} rows -> {output_file}")
        else:
            print(f"No data found for {symbol}")


def main():
    """Main function to download all data."""
    print("=" * 60)
    print("Massive.com Data Downloader")
    print("=" * 60)
    print(f"\nDownloading 1-minute data for {SYMBOLS}")
    print(f"Date range: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    
    # First, list available buckets and test access
    print("\n=== Checking Available Buckets ===")
    buckets = list_buckets()
    
    for bucket in buckets[:5]:
        check_bucket_access(bucket)
    
    # Test file download
    print("\n=== Testing File Downloads ===")
    accessible = test_file_download()
    
    if not accessible:
        print("\n" + "=" * 60)
        print("ERROR: Unable to download files from any data source.")
        print("Your account may not have download permissions for this data.")
        print("Please check your Massive.com subscription/access tier.")
        print("=" * 60)
        return
    
    print(f"\nAccessible data sources: {accessible}")
    
    # Download all data
    all_data = download_all_data(SYMBOLS, START_DATE, END_DATE)
    
    # Save to CSV files
    print("\n" + "=" * 60)
    print("Saving data...")
    save_data(all_data, OUTPUT_DIR)
    
    print("\n" + "=" * 60)
    print("Download complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
