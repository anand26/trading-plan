"""Verify factor file values match actual raw price data."""
import zipfile
from pathlib import Path

base = Path("quantconnect-lean/Data/equity/usa/minute")
ff_dir = Path("quantconnect-lean/Data/equity/usa/factor_files")


def parse_ff(sym):
    lines = (ff_dir / f"{sym}.csv").read_text().strip().split("\n")
    rows = []
    for line in lines:
        parts = line.split(",")
        rows.append({
            "date": parts[0],
            "pf": float(parts[1]),
            "sf": float(parts[2]),
            "ref": float(parts[3]) if len(parts) > 3 else 0
        })
    return rows


def get_raw_close(sym, dt):
    f = base / sym / f"{dt}_trade.zip"
    if not f.exists():
        return None
    with zipfile.ZipFile(f) as z:
        data = z.read(z.namelist()[0]).decode().strip().split("\n")
        return int(data[-1].split(",")[4]) / 10000.0


# ── TQQQ ──
print("=" * 80)
print("TQQQ Factor File Verification")
print("=" * 80)
print(f"{'Date':<12} {'PF':>10} {'SF':>16} {'SF Ratio':>10} {'Raw Close':>12} {'Ref Price':>12} {'Status':>10}")
print("-" * 80)

tqqq = parse_ff("tqqq")
for i in range(len(tqqq) - 1):
    row = tqqq[i]
    nxt = tqqq[i + 1]
    sf_ratio = row["sf"] / nxt["sf"]

    raw_close = get_raw_close("tqqq", row["date"])
    status = ""
    raw_str = ""

    if raw_close:
        raw_str = f"{raw_close:.2f}"
        # ref_price should be raw_close * sf  (adjusted close)
        expected_ref = raw_close * row["sf"]
        if abs(expected_ref - row["ref"]) / max(abs(row["ref"]), 0.001) < 0.05:
            status = "OK"
        else:
            status = f"MISMATCH (exp={expected_ref:.4f})"
    else:
        raw_str = "N/A"
        status = "no data"

    print(f"{row['date']:<12} {row['pf']:>10.7f} {row['sf']:>16.10f} {sf_ratio:>10.4f} {raw_str:>12} {row['ref']:>12.4f} {status:>10}")

# ── SQQQ ──
print()
print("=" * 80)
print("SQQQ Factor File Verification")
print("=" * 80)
print(f"{'Date':<12} {'PF':>10} {'SF':>16} {'SF Ratio':>10} {'Raw Close':>12} {'Ref Price':>12} {'Status':>10}")
print("-" * 80)

sqqq = parse_ff("sqqq")
for i in range(len(sqqq) - 1):
    row = sqqq[i]
    nxt = sqqq[i + 1]
    sf_ratio = row["sf"] / nxt["sf"]

    raw_close = get_raw_close("sqqq", row["date"])
    status = ""
    raw_str = ""

    if raw_close:
        raw_str = f"{raw_close:.2f}"
        expected_ref = raw_close * row["sf"]
        if abs(expected_ref - row["ref"]) / max(abs(row["ref"]), 0.001) < 0.05:
            status = "OK"
        else:
            status = f"MISMATCH (exp={expected_ref:.2f})"
    else:
        raw_str = "N/A"
        status = "no data"

    print(f"{row['date']:<12} {row['pf']:>10.7f} {row['sf']:>16.6f} {sf_ratio:>10.4f} {raw_str:>12} {row['ref']:>12.4f} {status:>10}")

# ── QQQ ──
print()
print("=" * 80)
print("QQQ Factor File Verification (first & last few rows)")
print("=" * 80)
print(f"{'Date':<12} {'PF':>10} {'SF':>8} {'Raw Close':>12} {'Ref Price':>12} {'Status':>10}")
print("-" * 80)

qqq = parse_ff("qqq")
check_rows = list(range(min(5, len(qqq)))) + list(range(max(0, len(qqq)-5), len(qqq)))
check_rows = sorted(set(check_rows))

for i in check_rows:
    row = qqq[i]
    raw_close = get_raw_close("qqq", row["date"])
    raw_str = f"{raw_close:.2f}" if raw_close else "N/A"
    status = ""

    if raw_close and row["ref"] > 0:
        expected_ref = raw_close * row["pf"] * row["sf"]
        # For QQQ, ref_price is the raw close, not adjusted
        # Actually from source code: ref_price is the raw close price
        # Let me check both interpretations
        if abs(raw_close - row["ref"]) / row["ref"] < 0.05:
            status = "ref=raw OK"
        elif abs(expected_ref - row["ref"]) / row["ref"] < 0.05:
            status = "ref=adj OK"
        else:
            status = f"CHECK (raw={raw_close:.2f})"

    print(f"{row['date']:<12} {row['pf']:>10.7f} {row['sf']:>8.4f} {raw_str:>12} {row['ref']:>12.4f} {status:>10}")

print()
print("=" * 80)
print("LEAN Factor File Format (from CorporateFactorRow.cs source code):")
print("  date, price_factor, split_factor, reference_price")
print("  PriceScaleFactor = price_factor * split_factor")
print("  raw_price * PriceScaleFactor = adjusted_price")
print("  reference_price = raw close on the day BEFORE the event takes effect")
print("  The factor file date = previous trading day before the split/dividend")
print("=" * 80)
