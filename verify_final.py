"""Verify the raw LEAN data files have correct prices (no corrections applied).
Also verify factor files are correctly formatted."""
import zipfile
from pathlib import Path

lean_dir = Path(r"c:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute")
factor_dir = Path(r"c:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\factor_files")

def read_lean_prices(symbol, date_str):
    """Read first open and last close from a LEAN zip file."""
    zip_path = lean_dir / symbol / f"{date_str}_trade.zip"
    if not zip_path.exists():
        return None, None, 0
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as cf:
            lines = cf.read().decode().strip().split('\n')
            first = lines[0].split(',')
            last = lines[-1].split(',')
            return int(first[1]) / 10000, int(last[4]) / 10000, len(lines)

# ===== SQQQ Verification =====
print("=" * 70)
print("SQQQ LEAN DATA - Raw prices at split boundaries")
print("=" * 70)
print(f"{'Date':<12} {'Open':>10} {'Close':>10} {'Bars':>6}  Notes")
print("-" * 70)

sqqq_dates = [
    ('20190523', 'Day BEFORE 1:4 reverse split'),
    ('20190524', 'Split day - price should jump ~4x'),
    ('20200817', 'Day BEFORE 1:5 reverse split'),
    ('20200818', 'Split day - price should jump ~5x'),
    ('20220112', 'Day BEFORE 1:5 reverse split'),
    ('20220113', 'Split day - price should jump ~5x'),
    ('20241106', 'Day BEFORE 1:5 reverse split'),
    ('20241107', 'Split day - price should jump ~5x'),
    ('20251119', 'Day BEFORE 1:5 reverse split'),
    ('20251120', 'Split day - price should jump ~5x'),
    ('20260102', 'Recent data - should be ~$67-69'),
]
for date_str, note in sqqq_dates:
    o, c, bars = read_lean_prices('sqqq', date_str)
    if o:
        print(f"{date_str:<12} ${o:>9.2f} ${c:>9.2f} {bars:>6}  {note}")
    else:
        print(f"{date_str:<12} {'N/A':>10} {'N/A':>10} {'':>6}  {note}")

# ===== TQQQ Verification =====
print("\n" + "=" * 70)
print("TQQQ LEAN DATA - Raw prices at split boundaries")
print("=" * 70)
print(f"{'Date':<12} {'Open':>10} {'Close':>10} {'Bars':>6}  Notes")
print("-" * 70)

tqqq_dates = [
    ('20180523', 'Day BEFORE 3:1 forward split'),
    ('20180524', 'Split day - price should drop ~3x'),
    ('20210120', 'Day BEFORE 2:1 forward split'),
    ('20210121', 'Split day - price should drop ~2x'),
    ('20220112', 'Day BEFORE 2:1 forward split'),
    ('20220113', 'Split day - price should drop ~2x'),
    ('20251119', 'Day BEFORE 2:1 forward split'),
    ('20251120', 'Split day - price should drop ~2x'),
    ('20260102', 'Recent data - should be ~$52-55'),
]
for date_str, note in tqqq_dates:
    o, c, bars = read_lean_prices('tqqq', date_str)
    if o:
        print(f"{date_str:<12} ${o:>9.2f} ${c:>9.2f} {bars:>6}  {note}")
    else:
        print(f"{date_str:<12} {'N/A':>10} {'N/A':>10} {'':>6}  {note}")

# ===== Factor File Verification =====
print("\n" + "=" * 70)
print("FACTOR FILES")
print("=" * 70)

for symbol in ['sqqq', 'tqqq', 'qqq']:
    ff = factor_dir / f"{symbol}.csv"
    if ff.exists():
        print(f"\n{symbol.upper()} factor file ({ff.name}):")
        lines = ff.read_text().strip().split('\n')
        for line in lines:
            parts = line.split(',')
            date, pf, sf, rp = parts[0], parts[1], parts[2], parts[3]
            # Compute per-event ratio by comparing to next row
            print(f"  {date}  price_factor={pf}  split_factor={sf}  ref_price=${rp}")
        
        # Compute per-event split ratios
        print(f"  Per-event split ratios:")
        for i in range(len(lines) - 1):
            this_sf = float(lines[i].split(',')[2])
            next_sf = float(lines[i+1].split(',')[2])
            ratio = this_sf / next_sf
            this_date = lines[i].split(',')[0]
            next_date = lines[i+1].split(',')[0]
            if ratio > 1:
                split_type = f"1:{ratio:.0f} reverse split"
            else:
                split_type = f"{1/ratio:.0f}:1 forward split"
            print(f"    {this_date} → {next_date}: ratio={ratio:.4f} ({split_type})")
    else:
        print(f"\n{symbol.upper()}: NO factor file found")

# ===== Alpaca Cross-Reference =====
print("\n" + "=" * 70)
print("CROSS-REFERENCE with Alpaca (ground truth)")
print("=" * 70)
import csv
alpaca_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\alpaca")
for symbol in ['TQQQ', 'SQQQ']:
    alpaca_files = list(alpaca_dir.glob(f"{symbol}_*.csv"))
    if alpaca_files:
        with open(alpaca_files[0]) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                first = rows[0]
                print(f"  Alpaca {symbol} first row: date={first.get('timestamp', first.get('date', 'N/A'))[:10]}  open=${float(first.get('open', 0)):.2f}")
                # Compare with LEAN
                lean_o, lean_c, _ = read_lean_prices(symbol.lower(), '20260102')
                if lean_o:
                    print(f"  LEAN   {symbol} 2026-01-02:  open=${lean_o:.2f}")
