"""
Extract reference prices from LEAN daily data for factor file entries.
LEAN daily format: date 00:00,open*10000,high*10000,low*10000,close*10000,volume
Reference price in factor file = the CLOSE price on the day before the split (raw, not *10000).
"""
import zipfile
import io

lean_data_path = "quantconnect-lean/Data/equity/usa/daily"

# TQQQ split dates (from yfinance) - we need the day BEFORE each split
tqqq_splits = [
    ("20110225", "2:1 forward"),   # need price on 20110224
    ("20120511", "2:1 forward"),   # need price on 20120510
    ("20140124", "2:1 forward"),   # need price on 20140123
    ("20170112", "2:1 forward"),   # need price on 20170111
    ("20180524", "3:1 forward"),   # existing entry 20180523
    ("20210121", "2:1 forward"),   # existing entry 20210120
    ("20220113", "2:1 forward"),   # existing entry 20220112
    ("20251120", "2:1 forward"),   # existing entry 20251119
]

# SQQQ split dates - we need the day BEFORE each split
sqqq_splits = [
    ("20120511", "1:4 reverse"),   # need price on 20120510
    ("20140124", "1:4 reverse"),   # need price on 20140123
    ("20170112", "1:4 reverse"),   # need price on 20170111
    ("20190524", "1:4 reverse"),   # existing entry 20190523
    ("20200818", "1:5 reverse"),   # existing entry 20200817
    ("20220113", "1:5 reverse"),   # existing entry 20220112
    ("20241107", "1:5 reverse"),   # existing entry 20241106
    ("20251120", "1:5 reverse"),   # existing entry 20251119
]

def load_daily_data(ticker):
    """Load all daily data from LEAN zip file."""
    zip_path = f"{lean_data_path}/{ticker}.zip"
    data = {}
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in zf.namelist():
            with zf.open(name) as f:
                for line in io.TextIOWrapper(f, encoding='utf-8'):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(',')
                    date_str = parts[0].split(' ')[0]  # "20100211 00:00" -> "20100211"
                    close = float(parts[4]) / 10000.0   # Convert from LEAN format
                    data[date_str] = close
    return data

print("Loading LEAN daily data...")
tqqq_data = load_daily_data("tqqq")
sqqq_data = load_daily_data("sqqq")
print(f"  TQQQ: {len(tqqq_data)} trading days loaded")
print(f"  SQQQ: {len(sqqq_data)} trading days loaded")

# Find prices around split dates
def find_price_before(data, split_date_str):
    """Find the close price on the trading day before or on the day before split."""
    # The factor file date is the day BEFORE the split
    # Try a few days before the split date
    from datetime import datetime, timedelta
    split_date = datetime.strptime(split_date_str, "%Y%m%d")
    
    for offset in range(1, 10):
        check_date = split_date - timedelta(days=offset)
        check_str = check_date.strftime("%Y%m%d")
        if check_str in data:
            return check_str, data[check_str]
    return None, None

print(f"\n{'='*70}")
print(f" TQQQ - Reference Prices for Factor File")
print(f"{'='*70}")
print(f"{'Split Date':<12} {'Factor Date':<12} {'Close Price':>12} {'Split':>12}")
print(f"{'-'*12} {'-'*12} {'-'*12:>12} {'-'*12:>12}")

for split_date, split_type in tqqq_splits:
    factor_date, close_price = find_price_before(tqqq_data, split_date)
    if factor_date:
        print(f"{split_date:<12} {factor_date:<12} {close_price:>12.2f} {split_type:>12}")
    else:
        print(f"{split_date:<12} {'NOT FOUND':<12} {'N/A':>12} {split_type:>12}")

print(f"\n{'='*70}")
print(f" SQQQ - Reference Prices for Factor File")
print(f"{'='*70}")
print(f"{'Split Date':<12} {'Factor Date':<12} {'Close Price':>12} {'Split':>12}")
print(f"{'-'*12} {'-'*12} {'-'*12:>12} {'-'*12:>12}")

for split_date, split_type in sqqq_splits:
    factor_date, close_price = find_price_before(sqqq_data, split_date)
    if factor_date:
        print(f"{split_date:<12} {factor_date:<12} {close_price:>12.2f} {split_type:>12}")
    else:
        print(f"{split_date:<12} {'NOT FOUND':<12} {'N/A':>12} {split_type:>12}")

# Now generate the CORRECT factor files
print(f"\n\n{'='*70}")
print(f" CORRECTED TQQQ FACTOR FILE")
print(f"{'='*70}")

# TQQQ: all forward splits
# Cumulative split factor from IPO: 1/(2*2*2*2*3*2*2*2) = 1/384
tqqq_cumulative_factors = {
    "ipo":      1.0 / (2*2*2*2*3*2*2*2),  # 0.00260417 - before any split
    "20110224": 1.0 / (2*2*2*3*2*2*2),     # 0.00520833 - after 1st 2:1
    "20120510": 1.0 / (2*2*3*2*2*2),       # 0.01041667 - after 2nd 2:1
    "20140123": 1.0 / (2*3*2*2*2),         # 0.02083333 - after 3rd 2:1
    "20170111": 1.0 / (3*2*2*2),           # 0.04166667 - after 4th 2:1
    "20180523": 1.0 / (2*2*2),             # 0.12500000 - after 3:1
    "20210120": 1.0 / (2*2),               # 0.25000000 - after 2:1
    "20220112": 1.0 / (2),                 # 0.50000000 - after 2:1
    "20251119": 1.0,                        # 1.00000000 - after 2:1
}

# Build TQQQ factor file entries
# Format: date,priceFactor,splitFactor,referencePrice
# IPO entry
ipo_date = "20100209"  # TQQQ IPO
ipo_price = tqqq_data.get("20100211", 0)  # First trading day we have data for
print(f"# IPO entry (first trading day data: {ipo_price})")

tqqq_factor_entries = []

# IPO entry - splitFactor for period before first split
factor_date = ipo_date
sf = tqqq_cumulative_factors["ipo"]
ref = ipo_price if ipo_price else 0.22
tqqq_factor_entries.append(f"{factor_date},1,{sf:.8f},{ref}")

# Entry for each split (date = day before split, factor = cumulative AFTER that split)
split_factor_dates = [
    ("20110224", "20110224"),
    ("20120510", "20120510"),
    ("20140123", "20140123"),
    ("20170111", "20170111"),
    ("20180523", "20180523"),
    ("20210120", "20210120"),
    ("20220112", "20220112"),
    ("20251119", "20251119"),
]

for factor_date_key, factor_date in split_factor_dates:
    sf = tqqq_cumulative_factors[factor_date_key]
    ref = tqqq_data.get(factor_date, 0)
    tqqq_factor_entries.append(f"{factor_date},1,{sf:.8f},{ref}")

# Terminal entry
tqqq_factor_entries.append("20501231,1,1,0")

print("\nCORRECT TQQQ factor file content:")
for entry in tqqq_factor_entries:
    print(f"  {entry}")


print(f"\n\n{'='*70}")
print(f" CORRECTED SQQQ FACTOR FILE")
print(f"{'='*70}")

# SQQQ: all reverse splits
# For reverse splits, splitFactor > 1 for older dates
# 1:4 reverse means ratio = 0.25, so 1/ratio = 4
# Cumulative from IPO: 4^4 * 5^4 = 256 * 625 = 160,000
sqqq_cumulative_factors = {
    "ipo":      4**4 * 5**4,          # 160000
    "20120510": 4**3 * 5**4,          # 40000  - after 1st 1:4
    "20140123": 4**2 * 5**4,          # 10000  - after 2nd 1:4
    "20170111": 4**1 * 5**4,          # 2500   - after 3rd 1:4
    "20190523": 5**4,                 # 625    - after 4th 1:4
    "20200817": 5**3,                 # 125    - after 1st 1:5
    "20220112": 5**2,                 # 25     - after 2nd 1:5
    "20241106": 5**1,                 # 5      - after 3rd 1:5
    "20251119": 1,                    # 1      - after 4th 1:5
}

sqqq_factor_entries = []

# IPO entry
sqqq_ipo_date = "20101105"
sqqq_ipo_price = sqqq_data.get("20101105", sqqq_data.get("20101108", 0))
sf = sqqq_cumulative_factors["ipo"]
sqqq_factor_entries.append(f"{sqqq_ipo_date},1,{sf},{sqqq_ipo_price}")

sqqq_split_dates = [
    ("20120510", "20120510"),
    ("20140123", "20140123"),
    ("20170111", "20170111"),
    ("20190523", "20190523"),
    ("20200817", "20200817"),
    ("20220112", "20220112"),
    ("20241106", "20241106"),
    ("20251119", "20251119"),
]

for factor_date_key, factor_date in sqqq_split_dates:
    sf = sqqq_cumulative_factors[factor_date_key]
    ref = sqqq_data.get(factor_date, 0)
    sqqq_factor_entries.append(f"{factor_date},1,{sf},{ref}")

# Terminal entry
sqqq_factor_entries.append("20501231,1,1,0")

print("\nCORRECT SQQQ factor file content:")
for entry in sqqq_factor_entries:
    print(f"  {entry}")

# Verify: check a known price
print(f"\n\n{'='*70}")
print(f" VERIFICATION")
print(f"{'='*70}")
print(f"\nTQQQ raw close on 20100211 (first day): {tqqq_data.get('20100211', 'N/A')}")
print(f"TQQQ raw close on 20260206 (recent):    {tqqq_data.get('20260206', 'N/A')}")
print(f"SQQQ raw close on 20101105 (IPO-ish):   {sqqq_data.get('20101105', sqqq_data.get('20101108', 'N/A'))}")
print(f"SQQQ raw close on 20260206 (recent):    {sqqq_data.get('20260206', 'N/A')}")

# Check: for recent TQQQ, adjusted = raw * 1 * 1 = raw (splitFactor=1 currently)
# For IPO TQQQ, adjusted = raw * 1 * 0.00260417
tqqq_ipo_raw = tqqq_data.get('20100211', 0)
tqqq_ipo_adjusted = tqqq_ipo_raw * 1 * tqqq_cumulative_factors["ipo"]
print(f"\nTQQQ 20100211: raw=${tqqq_ipo_raw:.2f}, adjusted=${tqqq_ipo_adjusted:.4f}")
print(f"  (Adjusted is low because after 384x forward splits, $1 then = $0.0026 equivalent)")

sqqq_ipo_raw = sqqq_data.get('20101105', sqqq_data.get('20101108', 0))
sqqq_ipo_adjusted = sqqq_ipo_raw * 1 * sqqq_cumulative_factors["ipo"]
print(f"\nSQQQ 20101105: raw=${sqqq_ipo_raw:.2f}, adjusted=${sqqq_ipo_adjusted:.2f}")
print(f"  (Adjusted is high because after many reverse splits, old shares worth much more per share)")
