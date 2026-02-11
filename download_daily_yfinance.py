"""
Download Daily OHLCV Data from yfinance → LEAN Daily Format
=============================================================
Downloads TQQQ, SQQQ, QQQ daily data back to each ticker's inception
and writes LEAN-compatible daily ZIP files.

LEAN daily format (from existing qqq.zip):
  - One ZIP per symbol: {symbol}.zip
  - Inside: {symbol}.csv
  - CSV row format: YYYYMMDD 00:00,open*10000,high*10000,low*10000,close*10000,volume
  - No header row
  - Prices are UNADJUSTED (raw) — LEAN applies its own factor files

Ticker inception dates:
  QQQ:  1999-03-10  (Invesco QQQ Trust)
  TQQQ: 2010-02-09  (ProShares UltraPro QQQ — 3x leveraged)
  SQQQ: 2010-02-09  (ProShares UltraPro Short QQQ — 3x inverse)

Usage:
  python download_daily_yfinance.py                  # Download all 3 tickers
  python download_daily_yfinance.py --tickers TQQQ   # Download specific ticker
  python download_daily_yfinance.py --dry-run        # Preview without writing

Requirements:
  pip install yfinance
"""

import argparse
import os
import sys
import zipfile
from datetime import datetime, date
from io import StringIO
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("[ERROR] yfinance not installed. Run: pip install yfinance")
    sys.exit(1)


# ============================================================
# CONFIGURATION
# ============================================================
# Target directory — LEAN's daily data location
LEAN_DAILY_DIR = Path(__file__).parent / "quantconnect-lean" / "Data" / "equity" / "usa" / "daily"

# Also save a raw backup for reference
RAW_BACKUP_DIR = Path(__file__).parent / "Data" / "yfinance" / "daily"

# Tickers and their start dates (yfinance will auto-clip if data doesn't exist)
TICKERS = {
    "QQQ":  "1999-01-01",   # Actually started 1999-03-10
    "TQQQ": "2010-01-01",   # Actually started 2010-02-09
    "SQQQ": "2010-01-01",   # Actually started 2010-02-09
}


# ============================================================
# DOWNLOAD
# ============================================================
def download_ticker(ticker: str, start_date: str) -> "pd.DataFrame":
    """Download daily OHLCV data from yfinance.
    
    Uses auto_adjust=False to get RAW (unadjusted) prices.
    LEAN applies its own factor files for split/dividend adjustments,
    so we MUST provide raw prices.
    """
    import pandas as pd
    
    end_date = date.today().strftime("%Y-%m-%d")
    
    print(f"  Downloading {ticker}: {start_date} → {end_date} ...")
    
    data = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        auto_adjust=False,   # RAW unadjusted prices — critical for LEAN
        actions=False,        # Don't need dividends/splits column
        progress=False,
    )
    
    if data.empty:
        print(f"  [WARNING] No data returned for {ticker}")
        return pd.DataFrame()
    
    # yfinance may return MultiIndex columns when downloading single ticker
    # Flatten if needed
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Drop any rows with NaN prices
    data = data.dropna(subset=["Open", "High", "Low", "Close"])
    
    print(f"  Downloaded {len(data)} trading days "
          f"({data.index[0].strftime('%Y-%m-%d')} → {data.index[-1].strftime('%Y-%m-%d')})")
    
    return data


# ============================================================
# CONVERT TO LEAN FORMAT
# ============================================================
def to_lean_daily_csv(df: "pd.DataFrame", ticker: str) -> str:
    """Convert a DataFrame to LEAN daily CSV format string.
    
    LEAN daily format:
      YYYYMMDD 00:00,open*10000,high*10000,low*10000,close*10000,volume
    
    Prices are scaled by 10000 and stored as integers.
    """
    lines = []
    
    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y%m%d")
        
        # Scale prices by 10000 (LEAN convention)
        open_p  = int(round(row["Open"]  * 10000))
        high_p  = int(round(row["High"]  * 10000))
        low_p   = int(round(row["Low"]   * 10000))
        close_p = int(round(row["Close"] * 10000))
        volume  = int(row["Volume"])
        
        lines.append(f"{date_str} 00:00,{open_p},{high_p},{low_p},{close_p},{volume}")
    
    return "\n".join(lines)


def write_lean_zip(csv_content: str, ticker: str, output_dir: Path):
    """Write LEAN daily ZIP file: {symbol}.zip containing {symbol}.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    symbol_lower = ticker.lower()
    zip_path = output_dir / f"{symbol_lower}.zip"
    csv_name = f"{symbol_lower}.csv"
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(csv_name, csv_content)
    
    # Get file size
    size_kb = zip_path.stat().st_size / 1024
    print(f"  Wrote: {zip_path}  ({size_kb:.1f} KB)")
    
    return zip_path


def save_raw_backup(df: "pd.DataFrame", ticker: str, output_dir: Path):
    """Save raw CSV backup (with headers) for reference/debugging."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = output_dir / f"{ticker}_daily.csv"
    df.to_csv(filepath)
    print(f"  Backup: {filepath}")


# ============================================================
# VERIFICATION
# ============================================================
def verify_lean_zip(zip_path: Path, expected_rows: int, ticker: str):
    """Verify the generated LEAN ZIP file is valid."""
    symbol_lower = ticker.lower()
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert len(names) == 1, f"Expected 1 file in ZIP, got {len(names)}"
        assert names[0] == f"{symbol_lower}.csv", f"Expected {symbol_lower}.csv, got {names[0]}"
        
        content = zf.read(names[0]).decode("utf-8")
        lines = [l for l in content.strip().split("\n") if l.strip()]
        
        assert len(lines) == expected_rows, (
            f"Row count mismatch: expected {expected_rows}, got {len(lines)}")
        
        # Spot-check first and last lines
        first = lines[0]
        last = lines[-1]
        
        # Validate format: YYYYMMDD 00:00,int,int,int,int,int
        parts = first.split(",")
        assert len(parts) == 6, f"Expected 6 columns, got {len(parts)}: {first}"
        assert " 00:00" in parts[0], f"Missing ' 00:00' in date field: {parts[0]}"
        
        # All price columns should be positive integers
        for p in parts[1:5]:
            val = int(p)
            assert val > 0, f"Non-positive price: {val}"
        
        print(f"  ✓ Verified: {len(lines)} rows, "
              f"first={parts[0].split()[0]}, last={last.split(',')[0].split()[0]}")


# ============================================================
# COMPARE WITH EXISTING DATA
# ============================================================
def compare_with_existing(zip_path: Path, ticker: str, lean_dir: Path):
    """If existing LEAN data exists, compare overlap for consistency."""
    existing_zip = lean_dir / f"{ticker.lower()}.zip"
    
    if not existing_zip.exists() or existing_zip == zip_path:
        return
    
    # Read existing data
    with zipfile.ZipFile(existing_zip, "r") as zf:
        old_content = zf.read(zf.namelist()[0]).decode("utf-8")
        old_lines = {l.split(",")[0]: l for l in old_content.strip().split("\n") if l.strip()}
    
    # Read new data
    with zipfile.ZipFile(zip_path, "r") as zf:
        new_content = zf.read(zf.namelist()[0]).decode("utf-8")
        new_lines = {l.split(",")[0]: l for l in new_content.strip().split("\n") if l.strip()}
    
    overlap_dates = set(old_lines.keys()) & set(new_lines.keys())
    
    if not overlap_dates:
        print(f"  No date overlap with existing {existing_zip.name}")
        return
    
    mismatches = 0
    for d in sorted(overlap_dates):
        old_parts = old_lines[d].split(",")
        new_parts = new_lines[d].split(",")
        
        # Compare close prices (allow small rounding differences)
        old_close = int(old_parts[4])
        new_close = int(new_parts[4])
        
        # Allow up to 0.5% difference due to different data providers
        if old_close > 0:
            pct_diff = abs(old_close - new_close) / old_close
            if pct_diff > 0.005:
                mismatches += 1
                if mismatches <= 5:
                    print(f"    Mismatch on {d}: existing close={old_close}, "
                          f"new close={new_close} ({pct_diff:.2%} diff)")
    
    print(f"  Compared {len(overlap_dates)} overlapping dates: "
          f"{mismatches} mismatches (>{0.5}% threshold)")
    
    if mismatches == 0:
        print(f"  ✓ Data consistent with existing LEAN data")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Download daily OHLCV data from yfinance and convert to LEAN format")
    parser.add_argument("--tickers", nargs="+", default=list(TICKERS.keys()),
                        help="Tickers to download (default: QQQ TQQQ SQQQ)")
    parser.add_argument("--start", type=str, default=None,
                        help="Override start date for all tickers (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=str(LEAN_DAILY_DIR),
                        help=f"Output directory (default: {LEAN_DAILY_DIR})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Download and show info but don't write files")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip saving raw CSV backup")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing LEAN ZIP files without prompting")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    
    print()
    print("=" * 70)
    print("  yfinance → LEAN Daily Data Downloader")
    print("=" * 70)
    print(f"  Output:  {output_dir}")
    print(f"  Backup:  {RAW_BACKUP_DIR}")
    print(f"  Tickers: {', '.join(args.tickers)}")
    print(f"  Date:    {date.today()}")
    print("=" * 70)
    
    results = {}
    
    for ticker in args.tickers:
        ticker = ticker.upper()
        start = args.start or TICKERS.get(ticker, "2010-01-01")
        
        print(f"\n{'─' * 70}")
        print(f"  {ticker}")
        print(f"{'─' * 70}")
        
        # 1. Download
        df = download_ticker(ticker, start)
        if df.empty:
            continue
        
        # 2. Convert to LEAN format
        print(f"  Converting to LEAN daily format (prices × 10000) ...")
        csv_content = to_lean_daily_csv(df, ticker)
        
        if args.dry_run:
            # Show preview
            lines = csv_content.split("\n")
            print(f"  [DRY RUN] Would write {len(lines)} rows")
            print(f"  First: {lines[0]}")
            print(f"  Last:  {lines[-1]}")
            results[ticker] = {"rows": len(lines), "start": df.index[0], "end": df.index[-1]}
            continue
        
        # 3. Check for existing file
        zip_path = output_dir / f"{ticker.lower()}.zip"
        if zip_path.exists() and not args.force:
            print(f"  [EXISTS] {zip_path}")
            resp = input(f"  Overwrite? (y/N): ").strip().lower()
            if resp != "y":
                print(f"  Skipped {ticker}")
                continue
        
        # 4. Write LEAN ZIP
        zip_path = write_lean_zip(csv_content, ticker, output_dir)
        
        # 5. Verify
        verify_lean_zip(zip_path, len(df), ticker)
        
        # 6. Compare with existing data (if we're writing to a different location)
        compare_with_existing(zip_path, ticker, LEAN_DAILY_DIR)
        
        # 7. Save raw backup
        if not args.no_backup:
            save_raw_backup(df, ticker, RAW_BACKUP_DIR)
        
        results[ticker] = {
            "rows": len(df),
            "start": df.index[0],
            "end": df.index[-1],
            "zip": zip_path,
        }
    
    # Summary
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    for ticker, info in results.items():
        start_str = info["start"].strftime("%Y-%m-%d")
        end_str = info["end"].strftime("%Y-%m-%d")
        years = (info["end"] - info["start"]).days / 365.25
        print(f"  {ticker:5}  {info['rows']:>6} days  "
              f"{start_str} → {end_str}  ({years:.1f} years)")
    
    print()
    print("  Next steps:")
    print("  1. Verify data: python download_daily_yfinance.py --dry-run")
    print("  2. Run backtest: Update algorithm to use Resolution.Daily or keep")
    print("     Resolution.Minute (LEAN will auto-load daily for warmup)")
    print("  3. Extend backtests back to 2010 in your parameter CSVs")
    print()
    
    # NDX note
    print("  NOTE on NDX vs QQQ:")
    print("  ─────────────────────")
    print("  Your algorithm uses QQQ for regime detection (SMA on QQQ closes).")
    print("  NDX (Nasdaq-100 index) tracks the SAME basket as QQQ but differs:")
    print("    • QQQ has splits, dividends, tracking error — needs factor files")
    print("    • NDX is a pure index — no splits/dividends, clean data")
    print("    • BUT: TQQQ/SQQQ leverage the NDX, so using QQQ adds one layer")
    print("      of ETF tracking error into your regime signal.")
    print("    • For backtesting, QQQ is fine — the correlation is >0.999")
    print("    • For a cleaner signal, you COULD switch to ^NDX in the algorithm,")
    print("      but you'd need to map it to LEAN's index format (different path).")
    print("  Recommendation: Stick with QQQ for now — it's simpler and the")
    print("  difference is negligible for daily SMA-based regime detection.")
    print()


if __name__ == "__main__":
    main()
