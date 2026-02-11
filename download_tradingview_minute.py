"""
TradingView Historical Data Downloader — Resilient Edition
==========================================================
Uses tvDatafeed (unofficial) to download 1-minute and daily OHLCV data
for QQQ, SQQQ, TQQQ with full resume support.

Key features:
  • Checkpoint file tracks exactly which ticker+timeframe combos are done
  • Auto-resume on crash/restart — just re-run the same command
  • Exponential backoff with automatic WebSocket reconnection
  • Merges new bars into existing CSVs (dedup by datetime)
  • Flexible: any tickers, any exchange, any supported interval

tvDatafeed limitations:
  • 1-minute: returns the LATEST 5000 bars only (~12-13 trading days)
  • Daily:    returns the LATEST 5000 bars (~19+ years — full history)
  • No date-range or backward-pagination in the API
  • Run this script DAILY to accumulate 1m history over time

Usage:
  python download_tradingview_minute.py                           # defaults
  python download_tradingview_minute.py --no-auth                 # no login
  python download_tradingview_minute.py --tickers AAPL MSFT       # custom
  python download_tradingview_minute.py --resume                  # resume
  python download_tradingview_minute.py --daily-only              # skip 1m
  python download_tradingview_minute.py --minute-only             # skip daily

⚠️  WARNING: Unofficial API — may violate TradingView's Terms of Service.
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


# ── Constants ────────────────────────────────────────────────────────────────
MAX_BARS = 5000
MAX_RETRIES = 5
BASE_DELAY = 5          # seconds — initial backoff
MAX_DELAY = 120          # seconds — max backoff cap
INTER_TICKER_PAUSE = 5   # seconds between tickers


# ── CLI ──────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download historical data from TradingView (tvDatafeed)"
    )
    p.add_argument(
        "--tickers", nargs="+", default=["QQQ", "SQQQ", "TQQQ"],
        help="Tickers to download (default: QQQ SQQQ TQQQ)",
    )
    p.add_argument(
        "--exchange", type=str, default="NASDAQ",
        help="Exchange (default: NASDAQ)",
    )
    p.add_argument(
        "--out", type=str, default=str(Path("Data", "tradingview")),
        help="Output directory (default: Data/tradingview)",
    )
    p.add_argument(
        "--username", type=str, default=os.environ.get("TRADINGVIEW_USERNAME"),
        help="TradingView username (or TRADINGVIEW_USERNAME env var)",
    )
    p.add_argument(
        "--password", type=str, default=os.environ.get("TRADINGVIEW_PASSWORD"),
        help="TradingView password (or TRADINGVIEW_PASSWORD env var)",
    )
    p.add_argument(
        "--no-auth", action="store_true",
        help="Connect without credentials (public data, may be limited)",
    )
    p.add_argument(
        "--bars", type=int, default=MAX_BARS,
        help=f"Bars per request, max {MAX_BARS} (default: {MAX_BARS})",
    )
    p.add_argument(
        "--retries", type=int, default=MAX_RETRIES,
        help=f"Max retries per download (default: {MAX_RETRIES})",
    )
    p.add_argument(
        "--interval", type=str, default=None,
        help="Download a specific interval: 1m, 5m, 15m, 30m, 1h, 4h, daily (default: daily+1m)",
    )
    p.add_argument(
        "--daily-only", action="store_true",
        help="Only download daily data (skip 1-minute)",
    )
    p.add_argument(
        "--minute-only", action="store_true",
        help="Only download 1-minute data (skip daily)",
    )
    p.add_argument(
        "--resume", action="store_true",
        help="Resume from checkpoint (automatic — this flag is just explicit)",
    )
    p.add_argument(
        "--start", type=str, default=None,
        help="Keep data FROM this date (YYYY-MM-DD). Earlier bars are trimmed.",
    )
    p.add_argument(
        "--end", type=str, default=None,
        help="Keep data UP TO this date (YYYY-MM-DD). Later bars are trimmed.",
    )
    p.add_argument(
        "--reset", action="store_true",
        help="Delete checkpoint and start fresh",
    )
    return p.parse_args()


# ── Checkpoint ───────────────────────────────────────────────────────────────
class Checkpoint:
    """Tracks which ticker+timeframe combos have been downloaded this session."""

    def __init__(self, out_dir: str):
        self.path = Path(out_dir) / "_tv_checkpoint.json"
        self.state: dict = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text())
            except Exception:
                self.state = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2, default=str))

    def is_done(self, ticker: str, timeframe: str) -> bool:
        return self.state.get(f"{ticker}:{timeframe}", {}).get("done", False)

    def mark_done(self, ticker: str, timeframe: str, rows: int, earliest: str, latest: str):
        self.state[f"{ticker}:{timeframe}"] = {
            "done": True,
            "rows": rows,
            "earliest": earliest,
            "latest": latest,
            "timestamp": datetime.now().isoformat(),
        }
        self.save()

    def mark_failed(self, ticker: str, timeframe: str, error: str):
        self.state[f"{ticker}:{timeframe}"] = {
            "done": False,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        self.save()

    def reset(self):
        self.state = {}
        if self.path.exists():
            self.path.unlink()

    def cleanup(self):
        """Remove checkpoint file after all tasks complete."""
        if self.path.exists():
            self.path.unlink()

    def summary(self) -> list[dict]:
        rows = []
        for key, info in sorted(self.state.items()):
            ticker, tf = key.split(":", 1)
            rows.append({
                "ticker": ticker,
                "timeframe": tf,
                "done": info.get("done", False),
                "rows": info.get("rows", 0),
                "earliest": info.get("earliest", ""),
                "latest": info.get("latest", ""),
                "error": info.get("error", ""),
            })
        return rows


# ── Connection management ────────────────────────────────────────────────────
class TVConnection:
    """Manages TvDatafeed connection with automatic reconnection."""

    def __init__(self, username, password, no_auth):
        self.username = username
        self.password = password
        self.no_auth = no_auth
        self.tv = None
        self.connect()

    def connect(self):
        from tvDatafeed import TvDatafeed
        if self.no_auth:
            self.tv = TvDatafeed()
        else:
            self.tv = TvDatafeed(username=self.username, password=self.password)

    def reconnect(self, reason: str = ""):
        print(f"    🔄 Reconnecting… ({reason})")
        try:
            self.connect()
            print(f"    ✓ Reconnected")
            return True
        except Exception as e:
            print(f"    ✗ Reconnect failed: {e}")
            return False

    def fetch(self, symbol, exchange, interval, n_bars, retries, label=""):
        """
        Fetch data with exponential backoff and auto-reconnect.
        Returns a DataFrame or None.
        """
        delay = BASE_DELAY

        for attempt in range(1, retries + 1):
            try:
                df = self.tv.get_hist(
                    symbol=symbol,
                    exchange=exchange,
                    interval=interval,
                    n_bars=n_bars,
                    extended_session=False,
                )
                if df is not None and not df.empty:
                    return df

                print(f"    ⟳ {label} attempt {attempt}/{retries}: empty response")

            except Exception as e:
                err_msg = str(e)
                print(f"    ⟳ {label} attempt {attempt}/{retries}: {err_msg}")

                # Reconnect on WebSocket/connection errors
                if any(kw in err_msg.lower() for kw in [
                    "websocket", "connection", "timed out", "eof",
                    "broken pipe", "reset by peer", "ssl",
                ]):
                    self.reconnect(err_msg[:60])

            if attempt < retries:
                wait = min(delay, MAX_DELAY)
                print(f"    ⏳ Waiting {wait:.0f}s before retry…")
                time.sleep(wait)
                delay *= 2  # exponential backoff

        return None


# ── Data helpers ─────────────────────────────────────────────────────────────
def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize tvDatafeed output DataFrame."""
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    if "symbol" in df.columns:
        df = df.drop(columns=["symbol"])
    return df


def filter_by_date(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    """Trim DataFrame to [start, end] date range."""
    if df.empty:
        return df
    if "datetime" not in df.columns:
        return df
    df["datetime"] = pd.to_datetime(df["datetime"])
    if start:
        before = len(df)
        df = df[df["datetime"] >= pd.Timestamp(start)]
        trimmed = before - len(df)
        if trimmed:
            print(f"    Trimmed {trimmed:,} bars before {start}")
    if end:
        before = len(df)
        df = df[df["datetime"] <= pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
        trimmed = before - len(df)
        if trimmed:
            print(f"    Trimmed {trimmed:,} bars after {end}")
    return df.reset_index(drop=True)


def merge_and_save(new_df: pd.DataFrame, csv_path: str) -> pd.DataFrame:
    """Merge new data into existing CSV, deduplicate, sort, save."""
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)

    if os.path.exists(csv_path):
        try:
            existing = pd.read_csv(csv_path, parse_dates=["datetime"])
        except Exception:
            existing = pd.DataFrame()

        if not existing.empty:
            before = len(existing)
            combined = pd.concat([existing, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["datetime"], keep="last")
            combined = combined.sort_values("datetime").reset_index(drop=True)
            added = len(combined) - before
            print(f"    Merged: {before:,} existing + {added:,} new = {len(combined):,} total")
            combined.to_csv(csv_path, index=False)
            return combined

    # No existing file or empty
    new_df = new_df.drop_duplicates(subset=["datetime"], keep="last")
    new_df = new_df.sort_values("datetime").reset_index(drop=True)
    new_df.to_csv(csv_path, index=False)
    return new_df


# ── Interval map ─────────────────────────────────────────────────────────────
def _get_interval_map():
    from tvDatafeed import Interval as I
    return {
        "1m":    (I.in_1_minute,   "1m"),
        "5m":    (I.in_5_minute,   "5m"),
        "15m":   (I.in_15_minute,  "15m"),
        "30m":   (I.in_30_minute,  "30m"),
        "1h":    (I.in_1_hour,     "1h"),
        "4h":    (I.in_4_hour,     "4h"),
        "daily": (I.in_daily,      "daily"),
    }


def download_interval(conn: TVConnection, ticker: str, exchange: str,
                      interval_key: str, bars: int, retries: int,
                      out_dir: str, checkpoint: Checkpoint, args) -> bool:
    """Generic download for any interval (4h, 1h, 5m, 15m, 30m)."""
    imap = _get_interval_map()
    if interval_key not in imap:
        print(f"  [{interval_key}] ✗ Unknown interval")
        return False

    tv_interval, file_suffix = imap[interval_key]
    label = interval_key.upper()

    if checkpoint.is_done(ticker, interval_key):
        info = checkpoint.state.get(f"{ticker}:{interval_key}", {})
        print(f"  [{label:5s}] ✓ Already done ({info.get('rows', '?'):,} rows). Skipping.")
        return True

    csv_path = os.path.join(out_dir, f"{ticker}_{file_suffix}.csv")
    if os.path.exists(csv_path):
        existing = pd.read_csv(csv_path, parse_dates=["datetime"])
        print(f"  [{label:5s}] Existing file: {len(existing):,} rows")

    print(f"  [{label:5s}] Fetching up to {bars} bars…")
    df = conn.fetch(ticker, exchange, tv_interval, bars, retries, label=label)

    if df is None:
        print(f"  [{label:5s}] ✗ Failed after {retries} attempts")
        checkpoint.mark_failed(ticker, interval_key, "no data after retries")
        return False

    df = clean_df(df)
    result = merge_and_save(df, csv_path)
    # Apply date filter on the FINAL merged result
    if args and (args.start or args.end):
        result = filter_by_date(result, args.start, args.end)
        if result.empty:
            print(f"  [{label:5s}] ✗ No data in date range")
            checkpoint.mark_failed(ticker, interval_key, "no data in date range")
            return False
        result.to_csv(csv_path, index=False)
    earliest = str(result["datetime"].min())
    latest = str(result["datetime"].max())
    print(f"  [{label:5s}] ✓ {earliest} → {latest}  ({len(result):,} rows)")
    print(f"  [{label:5s}]   Saved: {csv_path}")
    checkpoint.mark_done(ticker, interval_key, len(result), earliest, latest)
    return True


# ── Download functions ───────────────────────────────────────────────────────
def download_daily(conn: TVConnection, ticker: str, exchange: str,
                   bars: int, retries: int, out_dir: str,
                   checkpoint: Checkpoint, args=None) -> bool:
    """Download daily data (up to 5000 days ≈ 19+ years)."""
    from tvDatafeed import Interval as TvInterval

    key_tf = "daily"
    if checkpoint.is_done(ticker, key_tf):
        info = checkpoint.state.get(f"{ticker}:{key_tf}", {})
        print(f"  [DAILY] ✓ Already done ({info.get('rows', '?'):,} rows). Skipping.")
        return True

    print(f"  [DAILY] Fetching up to {bars} daily bars…")
    df = conn.fetch(ticker, exchange, TvInterval.in_daily, bars, retries, label="DAILY")

    if df is None:
        print(f"  [DAILY] ✗ Failed after {retries} attempts")
        checkpoint.mark_failed(ticker, key_tf, "no data after retries")
        return False

    df = clean_df(df)
    csv_path = os.path.join(out_dir, f"{ticker}_daily.csv")
    result = merge_and_save(df, csv_path)
    # Apply date filter on the FINAL merged result
    if args and (args.start or args.end):
        result = filter_by_date(result, args.start, args.end)
        if result.empty:
            print(f"  [DAILY] ✗ No data in date range")
            checkpoint.mark_failed(ticker, key_tf, "no data in date range")
            return False
        result.to_csv(csv_path, index=False)
    earliest = str(result["datetime"].min())
    latest = str(result["datetime"].max())
    print(f"  [DAILY] ✓ {earliest} → {latest}  ({len(result):,} rows)")
    print(f"  [DAILY]   Saved: {csv_path}")
    checkpoint.mark_done(ticker, key_tf, len(result), earliest, latest)
    return True


def download_minute(conn: TVConnection, ticker: str, exchange: str,
                    bars: int, retries: int, out_dir: str,
                    checkpoint: Checkpoint, args) -> bool:
    """Download 1-minute data (latest 5000 bars ≈ 12-13 trading days)."""
    from tvDatafeed import Interval as TvInterval

    key_tf = "1m"
    if checkpoint.is_done(ticker, key_tf):
        info = checkpoint.state.get(f"{ticker}:{key_tf}", {})
        print(f"  [1min]  ✓ Already done ({info.get('rows', '?'):,} rows). Skipping.")
        return True

    csv_path = os.path.join(out_dir, f"{ticker}_1m.csv")
    if os.path.exists(csv_path):
        existing = pd.read_csv(csv_path, parse_dates=["datetime"])
        print(f"  [1min]  Existing file: {len(existing):,} rows")

    print(f"  [1min]  Fetching {bars} most recent 1-minute bars…")

    # Use a fresh connection to avoid stale WebSocket
    fresh = TVConnection(args.username, args.password, args.no_auth)
    df = fresh.fetch(ticker, exchange, TvInterval.in_1_minute, bars, retries, label="1min")

    if df is None:
        print(f"  [1min]  ✗ Failed after {retries} attempts")
        checkpoint.mark_failed(ticker, key_tf, "no data after retries")
        return False

    df = clean_df(df)
    result = merge_and_save(df, csv_path)
    # Apply date filter on the FINAL merged result
    if args.start or args.end:
        result = filter_by_date(result, args.start, args.end)
        if result.empty:
            print(f"  [1min]  ✗ No data in date range")
            checkpoint.mark_failed(ticker, key_tf, "no data in date range")
            return False
        result.to_csv(csv_path, index=False)
    earliest = str(result["datetime"].min())
    latest = str(result["datetime"].max())
    print(f"  [1min]  ✓ {earliest} → {latest}  ({len(result):,} rows)")
    print(f"  [1min]    Saved: {csv_path}")
    checkpoint.mark_done(ticker, key_tf, len(result), earliest, latest)
    return True


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # Validate credentials
    if not args.no_auth and (not args.username or not args.password):
        print("ERROR: TradingView credentials required.")
        print("  Set TRADINGVIEW_USERNAME / TRADINGVIEW_PASSWORD in .env")
        print("  or pass --username / --password, or use --no-auth")
        sys.exit(2)

    out_dir = args.out
    checkpoint = Checkpoint(out_dir)

    if args.reset:
        checkpoint.reset()
        print("Checkpoint cleared.\n")

    # Build task list
    tasks = []
    for ticker in args.tickers:
        if args.interval:
            # Single specific interval requested
            tasks.append((ticker, args.interval))
        else:
            if not args.minute_only:
                tasks.append((ticker, "daily"))
            if not args.daily_only:
                tasks.append((ticker, "1m"))

    # Count pending
    pending = [t for t in tasks if not checkpoint.is_done(t[0], t[1])]
    already = len(tasks) - len(pending)

    print()
    print("=" * 65)
    print("  TradingView Data Downloader — Resilient Edition")
    print("  (tvDatafeed, unofficial)")
    print("=" * 65)
    print(f"  Tickers   : {', '.join(args.tickers)}")
    print(f"  Exchange  : {args.exchange}")
    print(f"  Tasks     : {len(tasks)} total, {already} done, {len(pending)} pending")
    print(f"  Retries   : {args.retries} per task (exponential backoff)")
    date_range = f"{args.start or 'earliest'} → {args.end or 'latest'}"
    print(f"  Date range: {date_range}")
    print(f"  Output    : {Path(out_dir).absolute()}")
    if already > 0:
        print(f"  ℹ️  Resuming — {already} tasks already completed")
    print("=" * 65)
    print()

    if not pending:
        print("All tasks already completed! Use --reset to start fresh.")
        _print_summary(out_dir, checkpoint)
        return

    # Connect
    print("Connecting to TradingView…")
    try:
        conn = TVConnection(args.username, args.password, args.no_auth)
        print("✓ Connected\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

    # Process each task
    successes = 0
    failures = 0

    for i, (ticker, timeframe) in enumerate(tasks):
        # Show ticker header on first task for this ticker
        prev_ticker = tasks[i - 1][0] if i > 0 else None
        if ticker != prev_ticker:
            if prev_ticker is not None:
                print(f"  Pausing {INTER_TICKER_PAUSE}s…")
                time.sleep(INTER_TICKER_PAUSE)
            print(f"\n{'─' * 55}")
            print(f"  {ticker}  ({args.exchange})")
            print(f"{'─' * 55}")

        try:
            if timeframe == "daily":
                ok = download_daily(conn, ticker, args.exchange, args.bars,
                                    args.retries, out_dir, checkpoint, args)
            elif timeframe == "1m":
                ok = download_minute(conn, ticker, args.exchange, args.bars,
                                     args.retries, out_dir, checkpoint, args)
            else:
                ok = download_interval(conn, ticker, args.exchange, timeframe,
                                       args.bars, args.retries, out_dir,
                                       checkpoint, args)

            if ok:
                successes += 1
            else:
                failures += 1

        except KeyboardInterrupt:
            print("\n\n  ⚠️  Interrupted! Progress saved to checkpoint.")
            print(f"     Re-run the same command to resume.\n")
            checkpoint.save()
            sys.exit(130)

        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            traceback.print_exc()
            checkpoint.mark_failed(ticker, timeframe, str(e)[:200])
            failures += 1

            # Try to reconnect for remaining tasks
            conn.reconnect("unexpected error")

    # Final summary
    _print_summary(out_dir, checkpoint)

    if failures == 0:
        checkpoint.cleanup()
        print("  ✓ All tasks succeeded — checkpoint cleaned up.")
    else:
        print(f"  ⚠️  {failures} task(s) failed. Re-run to retry them.")

    print("=" * 65)


def _print_summary(out_dir: str, checkpoint: Checkpoint):
    print()
    print("=" * 65)
    print("  Download Summary")
    print("=" * 65)

    # File listing
    out_abs = Path(out_dir).absolute()
    if out_abs.is_dir():
        for f in sorted(out_abs.iterdir()):
            if f.suffix == ".csv" and not f.name.startswith("_"):
                size_mb = f.stat().st_size / (1024 * 1024)
                try:
                    row_count = sum(1 for _ in open(f)) - 1
                except Exception:
                    row_count = -1
                print(f"  {f.name:40s}  {row_count:>10,} rows  ({size_mb:.2f} MB)")

    # Checkpoint status
    summary = checkpoint.summary()
    if summary:
        print()
        print("  Task Status:")
        for s in summary:
            status = "✓" if s["done"] else "✗"
            detail = f"{s['rows']:,} rows" if s["done"] else s.get("error", "pending")
            print(f"    {status} {s['ticker']:6s} {s['timeframe']:6s}  {detail}")

    print()
    print("  TIP: Run this script daily to accumulate 1-minute history.")
    print("       Each run appends new bars; duplicates are removed.")


if __name__ == "__main__":
    main()
