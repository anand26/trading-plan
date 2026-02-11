import argparse
import os
from datetime import datetime, date
from typing import List, Optional

import pandas as pd
import httpx

POLYGON_BASE = "https://api.polygon.io"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download 1-minute OHLCV data for US equities from Polygon.io"
    )
    p.add_argument(
        "--tickers",
        nargs="+",
        default=["QQQ", "SQQQ", "TQQQ"],
        help="List of tickers to download",
    )
    p.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD). Example: 2010-01-01",
    )
    p.add_argument(
        "--end",
        type=str,
        default=date.today().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD). Default: today",
    )
    p.add_argument(
        "--out",
        type=str,
        default=os.path.join("Data", "polygon"),
        help="Output directory for CSV files",
    )
    p.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("POLYGON_API_KEY"),
        help="Polygon.io API key (or set POLYGON_API_KEY env var)",
    )
    p.add_argument(
        "--prepost",
        action="store_true",
        help="Include pre/post market (extended hours) where available",
    )
    return p.parse_args()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def fetch_minute_bars(
    client: httpx.Client,
    ticker: str,
    start: str,
    end: str,
    adjusted: bool = True,
    include_extended: bool = False,
) -> List[dict]:
    """Fetch minute aggregates using v2 aggs endpoint, following pagination."""
    url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/1/minute/{start}/{end}"
    params = {
        "adjusted": "true" if adjusted else "false",
        "sort": "asc",
        "limit": 50000,
        "apiKey": client.headers.get("X-API-KEY", None),
    }
    # If API key isn't in header, provide via params using env value
    if not params["apiKey"]:
        api_key = os.environ.get("POLYGON_API_KEY")
        if api_key:
            params["apiKey"] = api_key

    results: List[dict] = []
    next_url: Optional[str] = None
    while True:
        r = client.get(next_url or url, params=None if next_url else params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "OK":
            raise RuntimeError(f"Polygon returned non-OK status: {data.get('status')}")
        chunk = data.get("results") or []
        results.extend(chunk)
        next_url = data.get("next_url")
        if not next_url:
            break
    # Filter out pre/post if requested to exclude
    if not include_extended:
        # Polygon minute aggregates include only regular session by default; keeping as-is.
        pass
    return results


def bars_to_dataframe(results: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame(results)
    if df.empty:
        return df
    # Expected columns: t (timestamp ms), o,h,l,c,v,vw,n
    df = df.rename(
        columns={
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "n": "transactions",
        }
    )
    # Convert ms epoch to ISO time (UTC)
    df["time_utc"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    # Order columns
    cols = [
        "time_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "transactions",
        "timestamp",
    ]
    df = df[[c for c in cols if c in df.columns]]
    return df


def save_csv(df: pd.DataFrame, out_dir: str, ticker: str, start: str, end: str) -> str:
    ensure_dir(out_dir)
    path = os.path.join(out_dir, f"{ticker}_1m_{start}_to_{end}.csv")
    df.to_csv(path, index=False)
    return path


def main() -> None:
    args = parse_args()
    if not args.api_key:
        print("ERROR: Polygon API key required. Pass --api-key or set POLYGON_API_KEY.")
        raise SystemExit(2)

    headers = {"X-API-KEY": args.api_key}
    with httpx.Client(headers=headers) as client:
        for ticker in args.tickers:
            print(f"Downloading {ticker} 1m from {args.start} to {args.end}…")
            results = fetch_minute_bars(
                client,
                ticker=ticker,
                start=args.start,
                end=args.end,
                adjusted=True,
                include_extended=args.prepost,
            )
            df = bars_to_dataframe(results)
            if df.empty:
                print(f"No data returned for {ticker}.")
                continue
            out_path = save_csv(df, args.out, ticker, args.start, args.end)
            print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
