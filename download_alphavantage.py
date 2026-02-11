"""
AlphaVantage Intraday Bulk Downloader — Production Edition
==========================================================
Downloads full intraday history using the month= parameter.
Supports 1min, 5min, 15min, 30min, 60min intervals.

FREE tier:  Intraday is PREMIUM ONLY (won't work)
Premium:    $49.99/month → 75 req/min → download everything in ~3 min
Strategy:   Subscribe → run this → download 15 years → cancel subscription

Coverage:
  • TQQQ: Feb 2010 → present (inception)
  • SQQQ: Nov 2008 → present (inception)
  • QQQ:  Mar 1999 → present (inception)

Usage:
  python download_alphavantage.py                                          # defaults
  python download_alphavantage.py --interval 1min                          # 1-minute
  python download_alphavantage.py --start 2010-02 --end 2018-05            # date range
  python download_alphavantage.py --tickers TQQQ SQQQ QQQ                  # all 3
  python download_alphavantage.py --resume                                 # resume
  python download_alphavantage.py --premium                                # fast mode (75 req/min)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Constants ────────────────────────────────────────────────────────────────
FREE_DELAY = 86400 / 25    # 25 calls/day = ~3456s between calls (impractical)
PREMIUM_DELAY = 1.0        # 75 calls/min = ~0.8s, use 1s for safety
TIMEOUT = 30

# Inception dates for tickers
INCEPTION = {
    "TQQQ": "2010-02",
    "SQQQ": "2008-11",
    "QQQ":  "1999-03",
}


# ── CLI ──────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="AlphaVantage Intraday Bulk Downloader")
    p.add_argument("--tickers", nargs="+", default=["QQQ", "SQQQ", "TQQQ"])
    p.add_argument("--interval", nargs="+", default=["5min"],
                   help="Bar interval(s): 1min 5min 15min 30min 60min (can specify multiple)")
    p.add_argument("--start", default=None,
                   help="Start month YYYY-MM (default: ticker inception)")
    p.add_argument("--end", default=None,
                   help="End month YYYY-MM (default: current month)")
    p.add_argument("--apikey", default=os.environ.get("ALPHAVANTAGE_API_KEY", ""),
                   help="AlphaVantage API key (or ALPHAVANTAGE_API_KEY env var)")
    p.add_argument("--premium", action="store_true",
                   help="Premium mode: 75 req/min (fast). Default: free tier (slow)")
    p.add_argument("--out", default="Data/alphavantage",
                   help="Output directory (default: Data/alphavantage)")
    p.add_argument("--resume", action="store_true",
                   help="Skip already-downloaded months (default: enabled)")
    p.add_argument("--reset", action="store_true",
                   help="Re-download everything, overwrite existing files")
    p.add_argument("--test", action="store_true",
                   help="Test mode: download only 2 months to verify API key works")
    return p.parse_args()


# ── Checkpoint ───────────────────────────────────────────────────────────────
class Checkpoint:
    def __init__(self, out_dir):
        self.path = Path(out_dir) / "_av_checkpoint.json"
        self.state = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text())
            except Exception:
                self.state = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))

    def is_done(self, key):
        return self.state.get(key, {}).get("done", False)

    def mark_done(self, key, rows):
        self.state[key] = {"done": True, "rows": rows, "ts": datetime.now().isoformat()}
        self.save()

    def mark_failed(self, key, error):
        self.state[key] = {"done": False, "error": error[:200], "ts": datetime.now().isoformat()}
        self.save()

    def reset(self):
        self.state = {}
        if self.path.exists():
            self.path.unlink()


# ── Month iterator ───────────────────────────────────────────────────────────
def month_range(start_str, end_str):
    """Generate YYYY-MM strings from start to end inclusive."""
    sy, sm = map(int, start_str.split("-"))
    ey, em = map(int, end_str.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield f"{y}-{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1


# ── Download ─────────────────────────────────────────────────────────────────
def download_month(symbol, month, interval, api_key, out_dir):
    """Download one month of intraday data. Returns (rows, error)."""
    url = (
        f"https://www.alphavantage.co/query?"
        f"function=TIME_SERIES_INTRADAY&symbol={symbol}"
        f"&interval={interval}&month={month}"
        f"&outputsize=full&adjusted=true"
        f"&apikey={api_key}&datatype=csv"
    )

    try:
        r = requests.get(url, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        return 0, "timeout"
    except requests.exceptions.RequestException as e:
        return 0, str(e)[:100]

    text = r.text

    # Check for errors
    if "premium" in text.lower():
        return 0, "PREMIUM_REQUIRED"
    if "rate limit" in text.lower() or "call frequency" in text.lower():
        return 0, "RATE_LIMITED"
    if "Invalid API" in text:
        return 0, "INVALID_API_KEY"
    if "Error" in text[:200] or "Information" in text[:200]:
        # Try to parse JSON error
        try:
            err = json.loads(text)
            return 0, list(err.values())[0][:100]
        except Exception:
            return 0, text[:100]

    # Check for valid CSV
    if "timestamp" not in text[:200]:
        return 0, f"unexpected response: {text[:80]}"

    # Save CSV
    filename = f"{symbol}_{month}_{interval}.csv"
    filepath = Path(out_dir) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(text)

    rows = text.count("\n") - 1  # subtract header
    return rows, None


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    if not args.apikey:
        print("ERROR: No API key. Set ALPHAVANTAGE_API_KEY in .env or pass --apikey")
        sys.exit(2)

    delay = PREMIUM_DELAY if args.premium else FREE_DELAY
    out_dir = args.out
    checkpoint = Checkpoint(out_dir)

    if args.reset:
        checkpoint.reset()
        print("Checkpoint cleared.\n")

    now = datetime.now()
    end_month = args.end or f"{now.year}-{now.month:02d}"

    # Build task list
    tasks = []
    for ticker in args.tickers:
        start_month = args.start or INCEPTION.get(ticker, "2010-01")
        for month in month_range(start_month, end_month):
            tasks.append((ticker, month))

    # Filter if test mode
    if args.test:
        tasks = tasks[:2]
        print("TEST MODE: downloading only 2 months to verify API key\n")

    # Count pending
    pending = [t for t in tasks if not checkpoint.is_done(f"{t[0]}:{t[1]}")]
    already = len(tasks) - len(pending)

    # Estimate time
    if args.premium:
        est_min = len(pending) * PREMIUM_DELAY / 60
        rate_str = "75 req/min (premium)"
    else:
        est_min = len(pending) * FREE_DELAY / 60
        rate_str = "25 req/day (free — VERY SLOW)"

    print("=" * 65)
    print("  AlphaVantage Intraday Bulk Downloader")
    print("=" * 65)
    print(f"  Tickers   : {', '.join(args.tickers)}")
    print(f"  Interval  : {args.interval}")
    print(f"  Months    : {len(tasks)} total, {already} done, {len(pending)} pending")
    print(f"  Rate      : {rate_str}")
    print(f"  Est. time : {est_min:.1f} minutes")
    print(f"  Output    : {Path(out_dir).absolute()}")
    print("=" * 65)
    print()

    if not pending:
        print("All months already downloaded! Use --reset to re-download.")
        _print_summary(args, out_dir, checkpoint)
        return

    # Process
    successes = 0
    failures = 0
    total_bars = 0
    current_ticker = None

    for i, (ticker, month) in enumerate(tasks):
        key = f"{ticker}:{month}"

        # Skip done
        if checkpoint.is_done(key) and not args.reset:
            continue

        # Ticker header
        if ticker != current_ticker:
            current_ticker = ticker
            print(f"\n── {ticker} ──────────────────────────────────────")

        # Download
        rows, error = download_month(ticker, month, args.interval, args.apikey, out_dir)

        if error:
            if error == "PREMIUM_REQUIRED":
                print(f"  {month}: ✗ PREMIUM REQUIRED — free key cannot access intraday")
                print(f"\n  ⚠️  Subscribe at https://www.alphavantage.co/premium/")
                print(f"      Then re-run with --premium flag.")
                checkpoint.mark_failed(key, error)
                sys.exit(1)
            elif error == "RATE_LIMITED":
                print(f"  {month}: ⏳ Rate limited — waiting 60s…")
                time.sleep(60)
                # Retry once
                rows, error = download_month(ticker, month, args.interval, args.apikey, out_dir)
                if error:
                    print(f"  {month}: ✗ {error}")
                    checkpoint.mark_failed(key, error)
                    failures += 1
                else:
                    print(f"  {month}: ✓ {rows:,} bars")
                    checkpoint.mark_done(key, rows)
                    successes += 1
                    total_bars += rows
            elif error == "INVALID_API_KEY":
                print(f"  {month}: ✗ Invalid API key!")
                sys.exit(2)
            else:
                print(f"  {month}: ✗ {error}")
                checkpoint.mark_failed(key, error)
                failures += 1
        else:
            print(f"  {month}: ✓ {rows:,} bars")
            checkpoint.mark_done(key, rows)
            successes += 1
            total_bars += rows

        # Rate limit pause
        remaining = len(pending) - (successes + failures)
        if remaining > 0:
            time.sleep(delay)

    # Summary
    _print_summary(args, out_dir, checkpoint)
    print(f"\n  Downloaded: {successes} months, {total_bars:,} total bars")
    if failures:
        print(f"  Failed: {failures} months — re-run with --resume to retry")
    print("=" * 65)


def _print_summary(args, out_dir, checkpoint):
    print()
    print("=" * 65)
    print("  Download Summary")
    print("=" * 65)

    out_path = Path(out_dir).absolute()
    if out_path.is_dir():
        for ticker in args.tickers:
            files = sorted(out_path.glob(f"{ticker}_*_{args.interval}.csv"))
            if files:
                total_rows = 0
                total_size = 0
                earliest = files[0].stem.split("_")[1]
                latest = files[-1].stem.split("_")[1]
                for f in files:
                    total_size += f.stat().st_size
                    total_rows += sum(1 for _ in open(f)) - 1
                print(f"  {ticker}: {len(files)} files, {total_rows:,} bars, "
                      f"{total_size/1024/1024:.1f} MB  ({earliest} → {latest})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Interrupted! Progress saved. Re-run to resume.")
        sys.exit(130)
