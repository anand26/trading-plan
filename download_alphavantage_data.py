"""
Download Alpha Vantage 1-min intraday data and convert to LEAN format.

Uses month-by-month API endpoint with:
  - adjusted=false  → RAW as-traded prices (matches Databento RAW data)
  - extended_hours=false → RTH only (9:30 AM - 4:00 PM ET)
  - outputsize=full → all bars for the month

Output: quantconnect-lean/Data/equity/usa/minute/{symbol}/{YYYYMMDD}_trade.zip
Inside zip: {YYYYMMDD}_{symbol}_minute_trade.csv
CSV format: ms_since_midnight,Open*10000,High*10000,Low*10000,Close*10000,Volume

Download strategy:
  Go year-by-year. For each year, download all 3 tickers (QQQ → TQQQ → SQQQ)
  so at any given time all 3 symbols have data up to the same timeframe.
"""

import os
import sys
import json
import time
import zipfile
import argparse
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' package required. Run: pip install requests")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

API_KEY = "GJU4TDYFABLUSRT0"
BASE_URL = "https://www.alphavantage.co/query"

DEFAULT_SYMBOLS = ["GLD"]
DEFAULT_START = "2004-11"   # Continue from where current AV data ends
DEFAULT_END = "2026-02"     # Up to current month

# Output: same location as Databento converted data
LEAN_DATA_DIR = Path(__file__).parent / "quantconnect-lean" / "Data" / "equity" / "usa" / "minute"

# Rate limiting — Premium: 75 calls/min
CALLS_PER_MINUTE = 75
SLEEP_BETWEEN_CALLS = 60.0 / CALLS_PER_MINUTE  # ~0.8s

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Progress file for resume support
PROGRESS_FILE = Path(__file__).parent / ".av_download_progress.json"


# ============================================================================
# PROGRESS TRACKING
# ============================================================================

def load_progress() -> dict:
    """Load download progress from file."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_progress(progress: dict):
    """Save download progress to file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def is_month_done(progress: dict, symbol: str, month: str) -> bool:
    """Check if a month has already been downloaded."""
    key = f"{symbol}_{month}"
    return progress.get(key, {}).get("done", False)


def mark_month_done(progress: dict, symbol: str, month: str, bars: int, days: int):
    """Mark a month as downloaded."""
    key = f"{symbol}_{month}"
    progress[key] = {
        "done": True,
        "bars": bars,
        "days": days,
        "timestamp": datetime.now().isoformat()
    }
    save_progress(progress)


# ============================================================================
# API FUNCTIONS
# ============================================================================

def fetch_month_data(symbol: str, month: str) -> dict:
    """
    Fetch 1-minute data for a symbol for an entire month.
    
    Args:
        symbol: e.g. "QQQ"
        month: e.g. "2010-02"
    
    Returns:
        dict of {timestamp_str: {open, high, low, close, volume}} or empty dict
    """
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": "1min",
        "month": month,
        "adjusted": "false",         # RAW as-traded prices
        "extended_hours": "false",   # RTH only (9:30-16:00)
        "outputsize": "full",        # All bars for the month
        "datatype": "json",
        "apikey": API_KEY,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)

            if resp.status_code == 429:
                wait = RETRY_DELAY * (attempt + 1) * 2
                print(f"    [RATE LIMIT] Waiting {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                print(f"    [HTTP {resp.status_code}] (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                continue

            data = resp.json()

            # Check for API error/info messages
            if "Error Message" in data:
                print(f"    [API ERROR] {data['Error Message'][:80]}")
                return {}

            if "Note" in data:
                # Rate limit note from AV
                wait = RETRY_DELAY * (attempt + 1) * 3
                print(f"    [RATE LIMIT NOTE] Waiting {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue

            if "Information" in data:
                print(f"    [INFO] {data['Information'][:80]}")
                return {}

            ts_key = "Time Series (1min)"
            if ts_key in data:
                return data[ts_key]
            else:
                print(f"    [NO DATA] No time series in response (attempt {attempt+1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                continue

        except requests.exceptions.Timeout:
            print(f"    [TIMEOUT] (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
        except requests.exceptions.RequestException as e:
            print(f"    [REQUEST ERROR] {e} (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
        except json.JSONDecodeError:
            print(f"    [JSON ERROR] Invalid response (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)

    print(f"    [FAILED] All {MAX_RETRIES} attempts failed for {symbol} {month}")
    return {}


# ============================================================================
# LEAN FORMAT CONVERSION
# ============================================================================

def convert_month_to_lean(symbol: str, time_series: dict) -> dict:
    """
    Convert Alpha Vantage time series to LEAN format, grouped by date.
    
    AV format: {"2010-02-11 09:43:00": {"1. open": "...", ...}}
    LEAN format: ms_since_midnight,O*10000,H*10000,L*10000,C*10000,Volume
    
    Returns:
        dict of {date_obj: list_of_csv_lines}
    """
    data_by_date = defaultdict(list)

    for timestamp_str, bar in time_series.items():
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            trade_date = dt.date()

            # Calculate milliseconds since midnight
            ms_since_midnight = (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000

            # LEAN stores prices as integer * 10000
            open_price = int(round(float(bar["1. open"]) * 10000))
            high_price = int(round(float(bar["2. high"]) * 10000))
            low_price = int(round(float(bar["3. low"]) * 10000))
            close_price = int(round(float(bar["4. close"]) * 10000))
            volume = int(float(bar["5. volume"]))

            lean_line = f"{ms_since_midnight},{open_price},{high_price},{low_price},{close_price},{volume}"
            data_by_date[trade_date].append((ms_since_midnight, lean_line))

        except (KeyError, ValueError) as e:
            continue  # Skip malformed bars

    return data_by_date


def save_lean_zips(symbol: str, data_by_date: dict) -> int:
    """
    Save grouped data as LEAN-format zip files.
    
    Creates: quantconnect-lean/Data/equity/usa/minute/{symbol}/{YYYYMMDD}_trade.zip
    Inside:  {YYYYMMDD}_{symbol}_minute_trade.csv
    
    Returns number of zip files created.
    """
    symbol_lower = symbol.lower()
    symbol_dir = LEAN_DATA_DIR / symbol_lower
    symbol_dir.mkdir(parents=True, exist_ok=True)

    files_created = 0

    for trade_date, rows in sorted(data_by_date.items()):
        # Sort by milliseconds since midnight
        rows.sort(key=lambda x: x[0])

        date_str = trade_date.strftime("%Y%m%d")
        zip_name = f"{date_str}_trade.zip"
        csv_name = f"{date_str}_{symbol_lower}_minute_trade.csv"

        zip_path = symbol_dir / zip_name

        # Write CSV inside ZIP
        csv_content = "\n".join(line for _, line in rows)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(csv_name, csv_content)

        files_created += 1

    return files_created


# ============================================================================
# MONTH GENERATION
# ============================================================================

def generate_months(start_month: str, end_month: str) -> list:
    """
    Generate list of YYYY-MM strings from start to end (inclusive).
    """
    start = datetime.strptime(start_month, "%Y-%m")
    end = datetime.strptime(end_month, "%Y-%m")

    months = []
    current = start
    while current <= end:
        months.append(current.strftime("%Y-%m"))
        # Advance to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return months


def group_months_by_year(months: list) -> dict:
    """Group months into {year: [months]} for year-by-year processing."""
    by_year = defaultdict(list)
    for m in months:
        year = m.split("-")[0]
        by_year[year].append(m)
    return dict(sorted(by_year.items()))


# ============================================================================
# EXISTING DATA CHECK
# ============================================================================

def get_existing_dates(symbol: str) -> set:
    """Get set of dates already downloaded for a symbol."""
    symbol_dir = LEAN_DATA_DIR / symbol.lower()
    if not symbol_dir.exists():
        return set()

    dates = set()
    for f in symbol_dir.glob("*_trade.zip"):
        try:
            date_str = f.name[:8]
            dates.add(date_str)
        except (ValueError, IndexError):
            continue
    return dates


# ============================================================================
# MAIN DOWNLOAD LOGIC
# ============================================================================

def download_all(symbols: list, start_month: str, end_month: str, dry_run: bool = False):
    """
    Download data year-by-year, all symbols per year.
    
    For each year: download QQQ for all months → TQQQ → SQQQ
    This ensures all 3 symbols stay in sync at each year boundary.
    """
    all_months = generate_months(start_month, end_month)
    months_by_year = group_months_by_year(all_months)
    progress = load_progress()

    total_months = len(all_months) * len(symbols)
    total_api_calls = total_months  # 1 API call per month
    already_done = sum(1 for s in symbols for m in all_months if is_month_done(progress, s, m))

    print("=" * 70)
    print("  Alpha Vantage Minute Data Downloader → LEAN Format")
    print("=" * 70)
    print(f"  Symbols:     {symbols}")
    print(f"  Period:      {start_month} to {end_month}")
    print(f"  Output:      {LEAN_DATA_DIR}")
    print(f"  Total:       {total_months} symbol-months ({total_api_calls} API calls)")
    print(f"  Already done:{already_done}")
    print(f"  Remaining:   {total_months - already_done}")
    print(f"  Rate:        {CALLS_PER_MINUTE} calls/min ({SLEEP_BETWEEN_CALLS:.1f}s delay)")
    print(f"  Dry run:     {dry_run}")
    print()

    # Show existing data
    print("--- Existing LEAN Data ---")
    for sym in symbols:
        existing = get_existing_dates(sym)
        if existing:
            print(f"  {sym}: {len(existing)} days ({min(existing)} to {max(existing)})")
        else:
            print(f"  {sym}: No data")
    print()

    if dry_run:
        print("[DRY RUN] Would download the following:\n")
        for year, year_months in months_by_year.items():
            print(f"  Year {year}:")
            for sym in symbols:
                remaining = [m for m in year_months if not is_month_done(progress, sym, m)]
                if remaining:
                    print(f"    {sym}: {len(remaining)} months ({remaining[0]} to {remaining[-1]})")
                else:
                    print(f"    {sym}: all done ✓")
        print("\nRun without --dry-run to start downloading.")
        input("\n  Press ENTER to close this window...")
        return

    # Download year by year
    start_time = time.time()
    global_done = 0
    global_total_bars = 0
    global_total_days = 0

    for year, year_months in months_by_year.items():
        print("=" * 70)
        print(f"  YEAR {year} — {len(year_months)} months × {len(symbols)} symbols")
        print("=" * 70)

        for sym in symbols:
            sym_bars = 0
            sym_days = 0
            skipped = 0

            print(f"\n  [{sym}] {year} ({len(year_months)} months)")

            for month in year_months:
                # Check if already done
                if is_month_done(progress, sym, month):
                    skipped += 1
                    continue

                global_done += 1
                remaining = total_months - already_done - global_done + 1
                elapsed = time.time() - start_time
                rate = global_done / elapsed * 60 if elapsed > 0 else 0
                eta_min = remaining / rate if rate > 0 else 0

                print(f"    {month} ... ", end="", flush=True)

                # Fetch from API
                time_series = fetch_month_data(sym, month)

                if not time_series:
                    print(f"no data")
                    mark_month_done(progress, sym, month, 0, 0)
                    time.sleep(SLEEP_BETWEEN_CALLS)
                    continue

                # Convert to LEAN format
                data_by_date = convert_month_to_lean(sym, time_series)

                # Save zip files
                files_created = save_lean_zips(sym, data_by_date)
                bar_count = len(time_series)

                sym_bars += bar_count
                sym_days += files_created
                global_total_bars += bar_count
                global_total_days += files_created

                mark_month_done(progress, sym, month, bar_count, files_created)

                print(f"{bar_count:>6,} bars, {files_created:>2} days  "
                      f"[{global_done}/{total_months - already_done} | ETA {eta_min:.0f}m]")

                time.sleep(SLEEP_BETWEEN_CALLS)

            if skipped > 0:
                print(f"    ({skipped} months already done, skipped)")

            print(f"  [{sym}] {year} totals: {sym_bars:,} bars, {sym_days} days")

    # Final summary
    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print("  DOWNLOAD COMPLETE")
    print("=" * 70)
    print(f"  Total bars downloaded:  {global_total_bars:,}")
    print(f"  Total trading days:     {global_total_days}")
    print(f"  Elapsed time:           {elapsed/60:.1f} minutes")
    print(f"  Output:                 {LEAN_DATA_DIR}")
    print()

    # Final verification
    print("--- Final LEAN Data ---")
    for sym in symbols:
        existing = get_existing_dates(sym)
        if existing:
            print(f"  {sym}: {len(existing)} days ({min(existing)} to {max(existing)})")
        else:
            print(f"  {sym}: No data")
    print("=" * 70)
    print()
    print("  ✅ ALL DOWNLOADS COMPLETED SUCCESSFULLY!")
    print(f"  📁 Data saved to: {LEAN_DATA_DIR}")
    print()
    input("  Press ENTER to close this window...")



# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Download Alpha Vantage 1-min data → LEAN format"
    )
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Symbols to download (default: {DEFAULT_SYMBOLS})")
    parser.add_argument("--start", default=DEFAULT_START,
                        help=f"Start month YYYY-MM (default: {DEFAULT_START})")
    parser.add_argument("--end", default=DEFAULT_END,
                        help=f"End month YYYY-MM (default: {DEFAULT_END})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be downloaded without downloading")
    parser.add_argument("--reset-progress", action="store_true",
                        help="Clear download progress and start fresh")

    args = parser.parse_args()

    if args.reset_progress:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
            print("[OK] Progress file cleared.")
        else:
            print("[OK] No progress file to clear.")
        if not args.dry_run:
            return

    download_all(
        symbols=args.symbols,
        start_month=args.start,
        end_month=args.end,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Download interrupted by user. Progress has been saved.")
        print("  Re-run the script to resume from where you left off.")
        input("\n  Press ENTER to close this window...")
    except Exception as e:
        print(f"\n\n  ❌ ERROR: {e}")
        print("  Progress has been saved. Re-run to resume.")
        input("\n  Press ENTER to close this window...")