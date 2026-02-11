#!/usr/bin/env python3
"""
Download historical 1-minute intraday data from FinancialModelingPrep (FMP) API
and convert to LEAN format for backtesting.

Symbols: QQQ, TQQQ, SQQQ
Period: 2010-02-09 to 2015-02-09 (5 years, TQQQ/SQQQ launch date)

Usage:
    python download_fmp_data.py
    python download_fmp_data.py --start 2010-02-09 --end 2015-02-09
    python download_fmp_data.py --symbols QQQ TQQQ SQQQ
    python download_fmp_data.py --dry-run   # test API without downloading everything

Output: LEAN-format minute data in Data/equity/usa/minute/{symbol}/
"""

import os
import sys
import json
import time
import zipfile
import argparse
import io
from datetime import datetime, timedelta, date
from pathlib import Path

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError

import ssl

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()
    # Fallback: system certs should work on most systems

# ============================================================================
# CONFIGURATION
# ============================================================================

API_KEY = "CQE7I0ImXNW5OanplvQlwcoLUnDwcqho"
BASE_URL = "https://financialmodelingprep.com/stable/historical-chart/1min"

DEFAULT_SYMBOLS = ["QQQ", "TQQQ", "SQQQ"]
DEFAULT_START = "2010-02-09"  # TQQQ/SQQQ launch date
DEFAULT_END = "2015-02-09"    # 5 years

# LEAN data directory
LEAN_DATA_DIR = Path(__file__).parent / "Data" / "equity" / "usa" / "minute"

# Rate limiting
CALLS_PER_MINUTE = 250  # Conservative — adjust based on your plan
SLEEP_BETWEEN_CALLS = 60.0 / CALLS_PER_MINUTE  # seconds between API calls
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# US market holidays (major ones 2010-2015)
US_HOLIDAYS = {
    # 2010
    date(2010, 1, 1), date(2010, 1, 18), date(2010, 2, 15),
    date(2010, 4, 2), date(2010, 5, 31), date(2010, 7, 5),
    date(2010, 9, 6), date(2010, 11, 25), date(2010, 12, 24),
    # 2011
    date(2011, 1, 17), date(2011, 2, 21), date(2011, 4, 22),
    date(2011, 5, 30), date(2011, 7, 4), date(2011, 9, 5),
    date(2011, 11, 24), date(2011, 12, 26),
    # 2012
    date(2012, 1, 2), date(2012, 1, 16), date(2012, 2, 20),
    date(2012, 4, 6), date(2012, 5, 28), date(2012, 7, 4),
    date(2012, 9, 3), date(2012, 10, 29), date(2012, 10, 30),  # Hurricane Sandy
    date(2012, 11, 22), date(2012, 12, 25),
    # 2013
    date(2013, 1, 1), date(2013, 1, 21), date(2013, 2, 18),
    date(2013, 3, 29), date(2013, 5, 27), date(2013, 7, 4),
    date(2013, 9, 2), date(2013, 11, 28), date(2013, 12, 25),
    # 2014
    date(2014, 1, 1), date(2014, 1, 20), date(2014, 2, 17),
    date(2014, 4, 18), date(2014, 5, 26), date(2014, 7, 4),
    date(2014, 9, 1), date(2014, 11, 27), date(2014, 12, 25),
    # 2015
    date(2015, 1, 1), date(2015, 1, 19), date(2015, 2, 16),
    date(2015, 4, 3), date(2015, 5, 25), date(2015, 7, 3),
    date(2015, 9, 7), date(2015, 11, 26), date(2015, 12, 25),
}


# ============================================================================
# API FUNCTIONS
# ============================================================================

def fetch_minute_data(symbol: str, day: date) -> list:
    """
    Fetch 1-minute data for a single symbol and single day from FMP.
    Returns list of bar dicts or empty list.
    """
    day_str = day.strftime("%Y-%m-%d")
    url = f"{BASE_URL}?symbol={symbol}&from={day_str}&to={day_str}&apikey={API_KEY}"
    
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url)
            response = urlopen(req, context=SSL_CONTEXT, timeout=30)
            
            data = response.read().decode("utf-8")
            parsed = json.loads(data)
            
            # Check for API error messages
            if isinstance(parsed, dict) and "Error Message" in parsed:
                print(f"  [API ERROR] {symbol} {day_str}: {parsed['Error Message']}")
                return []
            
            if isinstance(parsed, dict) and "error" in parsed:
                print(f"  [API ERROR] {symbol} {day_str}: {parsed['error']}")
                return []
            
            if not isinstance(parsed, list):
                print(f"  [WARN] {symbol} {day_str}: Unexpected response type: {type(parsed)}")
                return []
            
            return parsed
            
        except HTTPError as e:
            if e.code == 429:  # Rate limited
                wait = RETRY_DELAY * (attempt + 1) * 2
                print(f"  [RATE LIMIT] {symbol} {day_str}: Waiting {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
            elif e.code == 403:
                print(f"  [FORBIDDEN] {symbol} {day_str}: API key may not have minute data access")
                return []
            else:
                print(f"  [HTTP {e.code}] {symbol} {day_str}: {e.reason} (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
        except URLError as e:
            print(f"  [URL ERROR] {symbol} {day_str}: {e.reason} (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  [ERROR] {symbol} {day_str}: {e} (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    
    print(f"  [FAILED] {symbol} {day_str}: All {MAX_RETRIES} attempts failed")
    return []


def is_trading_day(d: date) -> bool:
    """Check if a date is a US trading day (not weekend, not holiday)."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if d in US_HOLIDAYS:
        return False
    return True


def get_trading_days(start: date, end: date) -> list:
    """Get all trading days between start and end (inclusive)."""
    days = []
    current = start
    while current <= end:
        if is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days


# ============================================================================
# LEAN FORMAT CONVERSION
# ============================================================================

def bars_to_lean_csv(bars: list, trade_date: date) -> str:
    """
    Convert FMP bars to LEAN minute CSV format.
    
    LEAN minute format (milliseconds since midnight):
    Time(ms),Open*10000,High*10000,Low*10000,Close*10000,Volume
    
    FMP returns bars in descending order (latest first), so we reverse.
    FMP timestamps are in EST (exchange time).
    """
    if not bars:
        return ""
    
    # Sort by date ascending (FMP returns newest first)
    sorted_bars = sorted(bars, key=lambda x: x["date"])
    
    lines = []
    for bar in sorted_bars:
        try:
            # Parse timestamp: "2024-06-03 09:30:00"
            dt = datetime.strptime(bar["date"], "%Y-%m-%d %H:%M:%S")
            
            # Skip bars that don't match the requested date
            if dt.date() != trade_date:
                continue
            
            # Filter to regular trading hours (9:30 AM - 4:00 PM ET)
            bar_time = dt.hour * 100 + dt.minute
            if bar_time < 930 or bar_time >= 1600:
                continue
            
            # LEAN uses milliseconds since midnight
            ms_since_midnight = (dt.hour * 3600 + dt.minute * 60) * 1000
            
            # LEAN stores prices as integer * 10000
            open_price = int(round(bar["open"] * 10000))
            high_price = int(round(bar["high"] * 10000))
            low_price = int(round(bar["low"] * 10000))
            close_price = int(round(bar["close"] * 10000))
            volume = int(bar["volume"])
            
            lines.append(f"{ms_since_midnight},{open_price},{high_price},{low_price},{close_price},{volume}")
            
        except (KeyError, ValueError) as e:
            continue  # Skip malformed bars
    
    return "\n".join(lines)


def save_lean_zip(symbol: str, trade_date: date, csv_content: str) -> Path:
    """
    Save CSV content as a LEAN-format zip file.
    
    LEAN expects: Data/equity/usa/minute/{symbol}/{date}_trade.zip
    Inside zip: {date}_{symbol}_minute_trade.csv
    """
    symbol_lower = symbol.lower()
    date_str = trade_date.strftime("%Y%m%d")
    
    # Create directory
    output_dir = LEAN_DATA_DIR / symbol_lower
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Zip file path
    zip_path = output_dir / f"{date_str}_trade.zip"
    
    # CSV filename inside the zip
    csv_filename = f"{date_str}_{symbol_lower}_minute_trade.csv"
    
    # Write zip
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(csv_filename, csv_content)
    
    return zip_path


# ============================================================================
# PROGRESS TRACKING
# ============================================================================

def load_progress(symbol: str) -> set:
    """Load set of already-downloaded dates for a symbol."""
    progress_file = LEAN_DATA_DIR / symbol.lower() / ".download_progress"
    if progress_file.exists():
        with open(progress_file, "r") as f:
            return set(f.read().strip().split("\n"))
    return set()


def save_progress(symbol: str, date_str: str):
    """Append a completed date to the progress file."""
    progress_dir = LEAN_DATA_DIR / symbol.lower()
    progress_dir.mkdir(parents=True, exist_ok=True)
    progress_file = progress_dir / ".download_progress"
    with open(progress_file, "a") as f:
        f.write(date_str + "\n")


# ============================================================================
# MAIN DOWNLOAD LOGIC
# ============================================================================

def download_symbol(symbol: str, start: date, end: date, dry_run: bool = False) -> dict:
    """
    Download all minute data for a symbol between start and end dates.
    Returns stats dict.
    """
    trading_days = get_trading_days(start, end)
    completed = load_progress(symbol)
    
    stats = {
        "symbol": symbol,
        "total_days": len(trading_days),
        "skipped": 0,
        "downloaded": 0,
        "empty": 0,
        "failed": 0,
        "total_bars": 0,
    }
    
    # Filter out already-downloaded days
    remaining = [d for d in trading_days if d.strftime("%Y-%m-%d") not in completed]
    already_done = len(trading_days) - len(remaining)
    
    print(f"\n{'='*60}")
    print(f"  {symbol}: {len(trading_days)} trading days ({start} to {end})")
    print(f"  Already downloaded: {already_done}")
    print(f"  Remaining: {len(remaining)}")
    print(f"{'='*60}")
    
    if dry_run and remaining:
        # Test with first day only
        print(f"\n  [DRY RUN] Testing with {remaining[0]}...")
        bars = fetch_minute_data(symbol, remaining[0])
        if bars:
            print(f"  [DRY RUN] Got {len(bars)} bars for {remaining[0]}")
            # Show first and last bar
            sorted_bars = sorted(bars, key=lambda x: x["date"])
            print(f"  [DRY RUN] First bar: {sorted_bars[0]}")
            print(f"  [DRY RUN] Last bar:  {sorted_bars[-1]}")
            csv = bars_to_lean_csv(bars, remaining[0])
            csv_lines = csv.count("\n") + 1 if csv else 0
            print(f"  [DRY RUN] LEAN bars (RTH only): {csv_lines}")
        else:
            print(f"  [DRY RUN] No data returned — check API plan/availability")
        return stats
    
    for i, day in enumerate(remaining):
        day_str = day.strftime("%Y-%m-%d")
        
        # Progress indicator
        pct = ((already_done + i + 1) / len(trading_days)) * 100
        sys.stdout.write(f"\r  [{symbol}] {day_str} ({already_done + i + 1}/{len(trading_days)}, {pct:.1f}%) | "
                        f"Downloaded: {stats['downloaded']} | Bars: {stats['total_bars']:,}")
        sys.stdout.flush()
        
        # Fetch data
        bars = fetch_minute_data(symbol, day)
        
        if not bars:
            stats["empty"] += 1
            save_progress(symbol, day_str)
            time.sleep(SLEEP_BETWEEN_CALLS)
            continue
        
        # Convert to LEAN format
        csv_content = bars_to_lean_csv(bars, day)
        
        if not csv_content:
            stats["empty"] += 1
            save_progress(symbol, day_str)
            time.sleep(SLEEP_BETWEEN_CALLS)
            continue
        
        # Save zip file
        bar_count = csv_content.count("\n") + 1
        zip_path = save_lean_zip(symbol, day, csv_content)
        
        stats["downloaded"] += 1
        stats["total_bars"] += bar_count
        save_progress(symbol, day_str)
        
        # Rate limiting
        time.sleep(SLEEP_BETWEEN_CALLS)
    
    print()  # Newline after progress
    return stats


def check_existing_data(symbols: list) -> dict:
    """Check what LEAN data already exists for each symbol."""
    existing = {}
    for symbol in symbols:
        symbol_dir = LEAN_DATA_DIR / symbol.lower()
        if symbol_dir.exists():
            zips = list(symbol_dir.glob("*.zip"))
            if zips:
                dates = sorted([z.stem.replace("_trade", "") for z in zips])
                existing[symbol] = {
                    "count": len(zips),
                    "earliest": dates[0],
                    "latest": dates[-1],
                }
            else:
                existing[symbol] = {"count": 0}
        else:
            existing[symbol] = {"count": 0}
    return existing


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Download FMP minute data → LEAN format")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Symbols to download (default: {DEFAULT_SYMBOLS})")
    parser.add_argument("--start", default=DEFAULT_START,
                        help=f"Start date YYYY-MM-DD (default: {DEFAULT_START})")
    parser.add_argument("--end", default=DEFAULT_END,
                        help=f"End date YYYY-MM-DD (default: {DEFAULT_END})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test API with 1 day per symbol, don't download everything")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Override LEAN data output directory")
    args = parser.parse_args()
    
    global LEAN_DATA_DIR
    if args.output_dir:
        LEAN_DATA_DIR = Path(args.output_dir)
    
    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    
    print("=" * 60)
    print("  FMP Minute Data Downloader → LEAN Format")
    print("=" * 60)
    print(f"  Symbols:  {args.symbols}")
    print(f"  Period:   {start_date} to {end_date}")
    print(f"  Output:   {LEAN_DATA_DIR}")
    print(f"  Dry run:  {args.dry_run}")
    print(f"  Rate:     {CALLS_PER_MINUTE} calls/min ({SLEEP_BETWEEN_CALLS:.2f}s delay)")
    
    # Check existing data
    print(f"\n--- Existing LEAN Data ---")
    existing = check_existing_data(args.symbols)
    for symbol, info in existing.items():
        if info["count"] > 0:
            print(f"  {symbol}: {info['count']} files ({info['earliest']} to {info['latest']})")
        else:
            print(f"  {symbol}: No data")
    
    # Estimate API calls needed
    trading_days = get_trading_days(start_date, end_date)
    total_calls = len(trading_days) * len(args.symbols)
    est_minutes = total_calls * SLEEP_BETWEEN_CALLS / 60
    print(f"\n--- Estimated Work ---")
    print(f"  Trading days:  {len(trading_days)}")
    print(f"  API calls:     {total_calls}")
    print(f"  Est. time:     {est_minutes:.0f} minutes ({est_minutes/60:.1f} hours)")
    
    if not args.dry_run:
        print(f"\n  Starting download in 3 seconds... (Ctrl+C to cancel)")
        time.sleep(3)
    
    # Download each symbol
    all_stats = []
    start_time = time.time()
    
    for symbol in args.symbols:
        try:
            stats = download_symbol(symbol, start_date, end_date, dry_run=args.dry_run)
            all_stats.append(stats)
        except KeyboardInterrupt:
            print(f"\n\n  [INTERRUPTED] Stopping. Progress saved — rerun to resume.")
            break
    
    elapsed = time.time() - start_time
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  DOWNLOAD SUMMARY")
    print(f"{'='*60}")
    for stats in all_stats:
        print(f"  {stats['symbol']}:")
        print(f"    Total trading days: {stats['total_days']}")
        print(f"    Downloaded:         {stats['downloaded']}")
        print(f"    Empty/no data:      {stats['empty']}")
        print(f"    Total bars:         {stats['total_bars']:,}")
    print(f"\n  Elapsed time: {elapsed/60:.1f} minutes")
    print(f"  Output:       {LEAN_DATA_DIR}")
    
    # Check final state
    print(f"\n--- Final LEAN Data ---")
    final = check_existing_data(args.symbols)
    for symbol, info in final.items():
        if info["count"] > 0:
            print(f"  {symbol}: {info['count']} files ({info['earliest']} to {info['latest']})")


if __name__ == "__main__":
    main()
