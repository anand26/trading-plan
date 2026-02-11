"""
Verify AV data integrity and determine correct factor files.

Since Alpha Vantage adjusted=false means:
  - SPLIT-ADJUSTED (splits baked into prices, no price jumps at splits)
  - NOT dividend-adjusted (raw dividend impact remains)

Factor file format: date, price_factor, split_factor, reference_price
  raw_price * price_factor * split_factor = fully_adjusted_price

For split-adjusted data:
  - split_factor must be 1.0 everywhere (splits already in prices)
  - price_factor handles dividend adjustments only
  - TQQQ/SQQQ: no dividends → pf=1, sf=1 (trivial factor file)
  - QQQ: pays dividends → pf varies, sf=1.0
"""
import zipfile
from pathlib import Path

base = Path("quantconnect-lean/Data/equity/usa/minute")

print("=" * 70)
print("  POST-AV-DOWNLOAD VERIFICATION")
print("=" * 70)

# ── 1. Data inventory ──
print("\n=== Data Inventory ===\n")
for sym in ["qqq", "tqqq", "sqqq"]:
    d = base / sym
    if not d.exists():
        print(f"  {sym.upper()}: NO DIRECTORY")
        continue
    files = sorted(d.glob("*_trade.zip"))
    if not files:
        print(f"  {sym.upper()}: 0 files")
        continue
    first = files[0].name[:8]
    last = files[-1].name[:8]
    print(f"  {sym.upper()}: {len(files):,} files ({first} to {last})")

# ── 2. Verify NO split jumps anywhere (all AV data) ──
print("\n=== Split Jump Verification (should ALL be ~1.0) ===\n")

tqqq_splits = [
    ("20120509", "20120510", "TQQQ 2:1"),
    ("20140122", "20140123", "TQQQ 2:1"),
    ("20170110", "20170111", "TQQQ 2:1"),
    ("20180523", "20180524", "TQQQ 3:1 (was AV/Databento boundary)"),
    ("20210119", "20210120", "TQQQ 3:1"),
    ("20220111", "20220112", "TQQQ 2:1"),
]

sqqq_splits = [
    ("20120509", "20120510", "SQQQ 1:10"),
    ("20140122", "20140123", "SQQQ 1:4"),
    ("20170110", "20170111", "SQQQ 1:4"),
    ("20190522", "20190523", "SQQQ 1:4"),
    ("20200814", "20200817", "SQQQ 1:5"),
    ("20220111", "20220112", "SQQQ 1:5"),
]

qqq_splits = [
    ("20000316", "20000317", "QQQ 2:1 forward"),
    ("20031222", "20031223", "QQQ 1:2 reverse"),
]

all_ok = True
for checks, sym in [(tqqq_splits, "tqqq"), (sqqq_splits, "sqqq"), (qqq_splits, "qqq")]:
    for before, after, label in checks:
        prices = {}
        for dt in [before, after]:
            f = base / sym / f"{dt}_trade.zip"
            if f.exists():
                with zipfile.ZipFile(f) as z:
                    data = z.read(z.namelist()[0]).decode().strip().split("\n")
                    last_line = data[-1].split(",")
                    prices[dt] = int(last_line[4]) / 10000.0

        b, a = prices.get(before), prices.get(after)
        if b and a:
            ratio = b / a
            ok = 0.8 < ratio < 1.2
            status = "OK" if ok else "SPLIT JUMP!"
            if not ok:
                all_ok = False
            print(f"  {label}: {b:.2f} -> {a:.2f}  ratio={ratio:.3f}  {status}")
        else:
            missing = before if not b else after
            print(f"  {label}: MISSING {missing}")

print(f"\n  Overall: {'ALL CLEAN - no split jumps' if all_ok else 'PROBLEMS FOUND'}")

# ── 3. Verify QQQ dividend impact (prices should NOT be dividend-adjusted) ──
print("\n=== QQQ Dividend Check ===")
print("  QQQ pays quarterly dividends. With adjusted=false, we expect")
print("  small price drops on ex-dividend dates (not adjusted away).\n")

# Some known QQQ ex-dividend dates (approximate)
qqq_div_dates = [
    ("20240318", "20240319", "2024 Q1 ex-div ~$0.63"),
    ("20230619", "20230620", "2023 Q2 ex-div ~$0.50"),
]

for before, after, label in qqq_div_dates:
    prices = {}
    for dt in [before, after]:
        f = base / "qqq" / f"{dt}_trade.zip"
        if f.exists():
            with zipfile.ZipFile(f) as z:
                data = z.read(z.namelist()[0]).decode().strip().split("\n")
                # First bar open
                first_line = data[0].split(",")
                prices[dt] = int(first_line[1]) / 10000.0  # open price

    b, a = prices.get(before), prices.get(after)
    if b and a:
        drop = b - a
        print(f"  {label}: {b:.2f} -> {a:.2f}  drop={drop:.2f}")
    else:
        print(f"  {label}: data missing")

# ── 4. Sample prices at key dates ──
print("\n=== Sample Prices (sanity check) ===\n")
sample_dates = ["20100211", "20150101", "20180601", "20200320", "20220103", "20250103"]

for dt in sample_dates:
    row = []
    for sym in ["qqq", "tqqq", "sqqq"]:
        f = base / sym / f"{dt}_trade.zip"
        if f.exists():
            with zipfile.ZipFile(f) as z:
                data = z.read(z.namelist()[0]).decode().strip().split("\n")
                mid = data[len(data)//2].split(",")
                close = int(mid[4]) / 10000.0
                row.append(f"{close:>10.2f}")
        else:
            row.append(f"{'N/A':>10}")
    print(f"  {dt}:  QQQ={row[0]}  TQQQ={row[1]}  SQQQ={row[2]}")

# ── 5. Read current factor files ──
print("\n=== Current Factor Files ===\n")
ff_dir = Path("quantconnect-lean/Data/equity/usa/factor_files")
for sym in ["qqq", "tqqq", "sqqq"]:
    ff = ff_dir / f"{sym}.csv"
    if ff.exists():
        lines = ff.read_text().strip().split("\n")
        print(f"  {sym.upper()}.csv ({len(lines)} rows):")
        for line in lines[:3]:
            print(f"    {line}")
        if len(lines) > 6:
            print(f"    ...")
        for line in lines[-3:]:
            print(f"    {line}")
    else:
        print(f"  {sym.upper()}.csv: NOT FOUND")
    print()

print("=" * 70)
