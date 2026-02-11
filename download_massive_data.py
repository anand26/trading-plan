"""
Polygon.io Free-Tier 1-Minute Data Downloader
==============================================
Downloads 1-minute OHLCV data for QQQ, SQQQ, TQQQ from Polygon.io.

Free-tier limits (as of 2026):
  • Up to 2 years of historical aggregate data
  • 5 API calls per minute

Strategy:
  • Fetches one day at a time per ticker (each day = 1 API call)
  • Pauses automatically to stay under 5 calls/min
  • Saves a checkpoint file so you can resume interrupted downloads
  • Outputs one CSV per ticker with all 1m bars merged

Usage:
  python download_massive_data.py --start 2024-02-08 --end 2026-02-08
  python download_massive_data.py --start 2024-02-08               # end defaults to today
  python download_massive_data.py --resume                          # resume from checkpoint
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Constants ────────────────────────────────────────────────────────────────
POLYGON_BASE = "https://api.polygon.io"
TICKERS = ["QQQ", "SQQQ", "TQQQ"]
OUTPUT_DIR = Path("Data/polygon_1m")
CHECKPOINT_FILE = OUTPUT_DIR / "_checkpoint.json"

# Free-tier rate limit: 5 calls/min → 1 call every 12s to be safe
RATE_LIMIT_PAUSE = 12.5  # seconds between API calls


# ── CLI ──────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    two_years_ago = (date.today() - timedelta(days=730)).isoformat()

    p = argparse.ArgumentParser(
        description="Download 1-minute OHLCV from Polygon.io (free tier, 2yr history)"
    )
    p.add_argument(
        "--start", type=str, default=two_years_ago,
        help=f"Start date YYYY-MM-DD (default: {two_years_ago})",
    )
    p.add_argument(
        "--end", type=str, default=date.today().isoformat(),
        help=f"End date YYYY-MM-DD (default: {date.today().isoformat()})",
    )
    p.add_argument(
        "--api-key", type=str,
        default=os.environ.get("POLYGON_API_KEY"),
        help="Polygon API key (or set POLYGON_API_KEY in .env)",
    )
    p.add_argument(
        "--out", type=str, default=str(OUTPUT_DIR),
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    p.add_argument(
        "--resume", action="store_true",
        help="Resume from last checkpoint (ignores --start/--end)",
    )
    return p.parse_args()


# ── Helpers ──────────────────────────────────────────────────────────────────
def trading_days(start: str, end: str) -> list[str]:
    """Return weekday dates between start and end (inclusive) as YYYY-MM-DD."""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    days = []
    cur = s
    while cur <= e:
        if cur.weekday() < 5:  # Mon–Fri
            days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return days


def load_checkpoint(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_checkpoint(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def fetch_day(ticker: str, day: str, api_key: str) -> list[dict]:
    """
    Fetch all 1-minute bars for a single ticker on a single day.
    Uses the v2 aggs endpoint with pagination (next_url).
    Returns a list of bar dicts.
    """
    url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/1/minute/{day}/{day}"
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000,
        "apiKey": api_key,
    }

    bars: list[dict] = []
    next_url: str | None = None

    while True:
        if next_url:
            # next_url is a full URL; append API key
            r = requests.get(next_url, params={"apiKey": api_key}, timeout=30)
        else:
            r = requests.get(url, params=params, timeout=30)

        if r.status_code == 429:
            # Rate-limited — wait and retry
            print("      ⏳ Rate-limited, waiting 60s…")
            time.sleep(60)
            continue

        r.raise_for_status()
        data = r.json()

        status = data.get("status")
        if status not in ("OK", "DELAYED"):
            # No data for this day (weekend/holiday/empty)
            break

        chunk = data.get("results") or []
        bars.extend(chunk)

        next_url = data.get("next_url")
        if not next_url:
            break

    return bars


def bars_to_df(bars: list[dict], ticker: str) -> pd.DataFrame:
    """Convert raw Polygon bars to a clean DataFrame."""
    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(bars)
    df = df.rename(columns={
        "t": "timestamp_ms",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "n": "transactions",
    })
    df["datetime"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
    df["datetime"] = df["datetime"].dt.tz_convert("America/New_York")
    df["ticker"] = ticker

    cols = ["datetime", "ticker", "open", "high", "low", "close", "volume", "vwap", "transactions"]
    return df[[c for c in cols if c in df.columns]]


# ── Main download loop ──────────────────────────────────────────────────────
def download_all(args):
    api_key = args.api_key
    if not api_key:
        print("ERROR: Polygon API key required.")
        print("  Set POLYGON_API_KEY in .env or pass --api-key")
        sys.exit(2)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load or init checkpoint
    checkpoint = load_checkpoint(CHECKPOINT_FILE)
    if args.resume and checkpoint:
        start = checkpoint.get("next_start", args.start)
        end = checkpoint.get("end", args.end)
        print(f"Resuming from checkpoint: {start}")
    else:
        start = args.start
        end = args.end
        checkpoint = {"start": start, "end": end, "completed": {}}

    days = trading_days(start, end)
    total_days = len(days)
    total_calls = total_days * len(TICKERS)
    est_minutes = (total_calls * RATE_LIMIT_PAUSE) / 60

    print()
    print("=" * 65)
    print("  Polygon.io Free-Tier 1-Minute Data Downloader")
    print("=" * 65)
    print(f"  Tickers     : {', '.join(TICKERS)}")
    print(f"  Date range  : {start} → {end}")
    print(f"  Trading days: {total_days}")
    print(f"  API calls   : {total_calls} ({len(TICKERS)} tickers × {total_days} days)")
    print(f"  Est. time   : ~{est_minutes:.0f} minutes (rate limit: 5 calls/min)")
    print(f"  Output      : {out_dir.absolute()}")
    print("=" * 65)
    print()

    # Per-ticker accumulators: load existing partial data if present
    ticker_data: dict[str, list[pd.DataFrame]] = {t: [] for t in TICKERS}

    for t in TICKERS:
        partial = out_dir / f"{t}_1m_partial.csv"
        if partial.exists():
            df = pd.read_csv(partial, parse_dates=["datetime"])
            ticker_data[t].append(df)
            print(f"  Loaded {len(df):,} existing rows for {t}")

    # Track progress
    completed = checkpoint.get("completed", {})
    calls_made = 0
    start_time = time.time()

    for day_idx, day in enumerate(days):
        for ticker in TICKERS:
            key = f"{ticker}:{day}"

            # Skip already-downloaded days
            if key in completed:
                continue

            # Rate-limit: pause between calls
            if calls_made > 0:
                time.sleep(RATE_LIMIT_PAUSE)

            # Progress
            elapsed = time.time() - start_time
            pct = (day_idx * len(TICKERS) + TICKERS.index(ticker)) / total_calls * 100
            remaining_calls = total_calls - calls_made
            eta_sec = remaining_calls * RATE_LIMIT_PAUSE
            eta_min = eta_sec / 60

            print(
                f"  [{pct:5.1f}%] {ticker} {day}  "
                f"(call {calls_made + 1}/{total_calls}, "
                f"ETA ~{eta_min:.0f}min)…",
                end="",
                flush=True,
            )

            try:
                bars = fetch_day(ticker, day, api_key)
                calls_made += 1

                if bars:
                    df = bars_to_df(bars, ticker)
                    ticker_data[ticker].append(df)
                    print(f"  ✓ {len(df)} bars")
                else:
                    print(f"  – no data")

            except requests.HTTPError as e:
                if "403" in str(e):
                    print(f"\n\n  ✗ 403 Forbidden — your free tier may not cover this date range.")
                    print(f"    Polygon free tier allows 2 years from today.")
                    print(f"    Try: --start {(date.today() - timedelta(days=730)).isoformat()}")
                    # Save what we have
                    _save_partials(ticker_data, out_dir)
                    save_checkpoint(CHECKPOINT_FILE, {
                        "next_start": day, "end": end, "completed": completed,
                    })
                    sys.exit(1)
                else:
                    print(f"  ✗ {e}")
                    calls_made += 1

            except Exception as e:
                print(f"  ✗ {e}")
                calls_made += 1

            # Mark completed
            completed[key] = True

        # Save checkpoint after each full day (all tickers)
        checkpoint["completed"] = completed
        checkpoint["next_start"] = day
        save_checkpoint(CHECKPOINT_FILE, checkpoint)

        # Save partial CSVs every 50 days to avoid data loss
        if (day_idx + 1) % 50 == 0:
            _save_partials(ticker_data, out_dir)

    # ── Final save ───────────────────────────────────────────────────────
    _save_final(ticker_data, out_dir, start, end)


def _save_partials(ticker_data: dict, out_dir: Path):
    """Save intermediate partial CSVs (for crash recovery)."""
    for ticker, dfs in ticker_data.items():
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            combined = combined.drop_duplicates(subset=["datetime"], keep="last")
            combined = combined.sort_values("datetime").reset_index(drop=True)
            path = out_dir / f"{ticker}_1m_partial.csv"
            combined.to_csv(path, index=False)


def _save_final(ticker_data: dict, out_dir: Path, start: str, end: str):
    """Merge, deduplicate, and save final per-ticker CSVs."""
    print()
    print("=" * 65)
    print("  Saving final files…")
    print("=" * 65)

    for ticker, dfs in ticker_data.items():
        if not dfs:
            print(f"  {ticker}: no data downloaded")
            continue

        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["datetime"], keep="last")
        combined = combined.sort_values("datetime").reset_index(drop=True)

        # Final output file
        fname = f"{ticker}_1m_{start}_to_{end}.csv"
        path = out_dir / fname
        combined.to_csv(path, index=False)

        size_mb = path.stat().st_size / (1024 * 1024)
        earliest = combined["datetime"].min()
        latest = combined["datetime"].max()
        print(f"  {ticker}: {len(combined):>10,} bars  |  {earliest} → {latest}  |  {size_mb:.1f} MB")
        print(f"         → {path}")

    # Clean up partial files and checkpoint
    for ticker in TICKERS:
        partial = out_dir / f"{ticker}_1m_partial.csv"
        if partial.exists():
            partial.unlink()

    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

    print()
    print("  ✓ Download complete! Checkpoint and partial files cleaned up.")
    print("=" * 65)


# ── Entry point ──────────────────────────────────────────────────────────────
def main():
    args = parse_args()
    download_all(args)


if __name__ == "__main__":
    main()
