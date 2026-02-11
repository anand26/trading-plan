"""Verify Alpha Vantage adjusted=false data vs factor files."""
import zipfile
from pathlib import Path

base = Path("quantconnect-lean/Data/equity/usa/minute")

print("=" * 70)
print("  FACTOR FILE vs RAW PRICE VERIFICATION")
print("=" * 70)

# ── TQQQ split dates from factor file ──
# When split_factor changes between rows, a split happened.
# factor file: date, price_factor, split_factor, ref_price
tqqq_factors = [
    ("20100211", 1.0, 0.0026041667, 0.2163),
    ("20110224", 1.0, 0.0026041667, 0.4322),   # no split (same sf)
    ("20120510", 1.0, 0.0052083333, 0.5283),   # split: sf doubled
    ("20140123", 1.0, 0.0104166667, 1.3097),   # split: sf doubled
    ("20170111", 1.0, 0.0208333333, 2.9496),   # split: sf doubled
    ("20180523", 1.0, 0.0416666667, 6.9321),   # split: sf doubled
    ("20210120", 1.0, 0.125,        24.745),   # split: sf tripled
    ("20220112", 1.0, 0.25,         38.17),    # split: sf doubled
    ("20251119", 1.0, 0.5,          50.025),   # split: sf doubled
    ("20501231", 1.0, 1.0,          0),        # sentinel
]

# Check prices around splits — if data is truly RAW, price should jump at split
print("\n=== TQQQ: Price around split dates ===")
print("If data is RAW (as-traded), we expect a ~2x or 3x price ratio at splits")
print("If data is SPLIT-ADJUSTED, ratio should be ~1.0\n")

split_dates = [
    ("20120509", "20120510", "2:1 reverse"),
    ("20140122", "20140123", "2:1 reverse"),
    ("20170110", "20170111", "2:1 reverse"),
    ("20180523", "20180524", "~3:1 reverse"),  # boundary AV→Databento
    ("20210119", "20210120", "3:1 reverse"),
    ("20220111", "20220112", "2:1 reverse"),
]

for before, after, label in split_dates:
    prices = {}
    for dt in [before, after]:
        f = base / "tqqq" / f"{dt}_trade.zip"
        if f.exists():
            with zipfile.ZipFile(f) as z:
                data = z.read(z.namelist()[0]).decode().strip().split("\n")
                last_line = data[-1].split(",")
                prices[dt] = int(last_line[4]) / 10000.0
        else:
            prices[dt] = None

    b, a = prices.get(before), prices.get(after)
    if b and a:
        ratio = b / a
        is_raw = ratio > 1.5
        status = "RAW (split visible)" if is_raw else "SPLIT-ADJUSTED (no jump)"
        print(f"  {before}->{after} ({label}): {b:.2f} -> {a:.2f}  ratio={ratio:.3f}  => {status}")
    else:
        missing = before if not b else after
        print(f"  {before}->{after}: MISSING {missing}")

# ── SQQQ ──
print("\n=== SQQQ: Price around split dates ===\n")

sqqq_splits = [
    ("20120509", "20120510", "1:10 reverse"),
    ("20140122", "20140123", "1:4 reverse"),
    ("20170110", "20170111", "1:4 reverse"),
    ("20190522", "20190523", "1:4 reverse"),
    ("20200814", "20200817", "1:5 reverse"),
    ("20220111", "20220112", "1:5 reverse"),
]

for before, after, label in sqqq_splits:
    prices = {}
    for dt in [before, after]:
        f = base / "sqqq" / f"{dt}_trade.zip"
        if f.exists():
            with zipfile.ZipFile(f) as z:
                data = z.read(z.namelist()[0]).decode().strip().split("\n")
                last_line = data[-1].split(",")
                prices[dt] = int(last_line[4]) / 10000.0
        else:
            prices[dt] = None

    b, a = prices.get(before), prices.get(after)
    if b and a:
        ratio = b / a
        is_raw = ratio > 1.5 or ratio < 0.67
        status = "RAW (split visible)" if is_raw else "SPLIT-ADJUSTED (no jump)"
        print(f"  {before}->{after} ({label}): {b:.2f} -> {a:.2f}  ratio={ratio:.3f}  => {status}")
    else:
        missing = before if not b else after
        print(f"  {before}->{after}: MISSING {missing}")

# ── Data source boundary ──
print("\n=== DATA SOURCE BOUNDARY (AV ends ~ 2018-05, Databento starts) ===\n")

for sym in ["tqqq", "sqqq", "qqq"]:
    print(f"  {sym.upper()}:")
    dates_to_check = ["20180521", "20180522", "20180523", "20180524", "20180525", 
                       "20180529", "20180530", "20180601"]
    for dt in dates_to_check:
        f = base / sym / f"{dt}_trade.zip"
        if f.exists():
            with zipfile.ZipFile(f) as z:
                data = z.read(z.namelist()[0]).decode().strip().split("\n")
                mid = data[len(data)//2].split(",")
                close = int(mid[4]) / 10000.0
                print(f"    {dt}: {len(data):>4} bars, close={close:.4f}")
        else:
            print(f"    {dt}: NO FILE")
    print()

print("=" * 70)
print("CONCLUSION:")
print("  If AV data shows ratio ~1.0 at splits but Databento shows jumps,")
print("  then AV adjusted=false is SPLIT-ADJUSTED and Databento is truly RAW.")
print("  These are INCOMPATIBLE. Must use one source for all data.")
print("=" * 70)
