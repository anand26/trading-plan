"""Verify the split correction logic by checking prices at transition dates.

The key question: are the jumps in Databento data from SEPARATE splits
being individually applied, or from ONE cumulative adjustment?

If SQQQ had 5 separate 1:5 reverse splits, then the oldest data should
indeed need 5^5 = 3125x correction. But that would make 2018 SQQQ
prices absurdly high ($2 * 3125 = $6250). That can't be right.

The reality is: Databento retroactively applied the LATEST split's
adjustment to ALL historical data. Each "jump" in the data is where
one round of retroactive reprocessing STOPPED. So:

- The 2025-11-20 jump: Databento reprocessed through Nov 19, applying
  the most recent SQQQ 1:5 reverse split (which happened in real life).
  Data before Nov 20 has this ONE split baked in: prices ÷5.

- The 2024-11-07 jump: An earlier round of reprocessing stopped here,
  applying the PREVIOUS 1:5 reverse split. But it also already had the
  most recent one. So data before Nov 7, 2024 has TWO splits: prices ÷25.

Wait... let me just check the actual numbers to figure this out.
"""
import zstandard as zstd
import io
import csv
import zipfile
from pathlib import Path

source_dir = Path(r"c:\Users\anand\Documents\trading_plan\Data\databento")
lean_dir = Path(r"c:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute")

# ===== CHECK DATABENTO SOURCE PRICES =====
print("=" * 70)
print("SQQQ DATABENTO SOURCE prices at transition dates")
print("=" * 70)

dates_to_check = [
    '2019-05-23', '2019-05-24',
    '2020-08-17', '2020-08-18',
    '2022-01-12', '2022-01-13',
    '2024-11-06', '2024-11-07',
    '2025-11-19', '2025-11-20',
    '2025-12-01', '2026-01-02',
]

zst = list(source_dir.glob("*.SQQQ.csv.zst"))[0]
with open(zst, 'rb') as f:
    dctx = zstd.ZstdDecompressor()
    with dctx.stream_reader(f) as reader:
        text_stream = io.TextIOWrapper(reader, encoding='utf-8')
        csv_reader = csv.DictReader(text_stream)
        first_open = {}
        last_close = {}
        for row in csv_reader:
            d = row['ts_event'][:10]
            if d in dates_to_check:
                if d not in first_open:
                    first_open[d] = float(row['open'])
                last_close[d] = float(row['close'])

print("\nSQQQ Databento source prices:")
for d in sorted(first_open.keys()):
    print(f"  {d}: open=${first_open[d]:.4f}  close=${last_close[d]:.4f}")

# ===== CHECK LEAN OUTPUT (after current converter ran) =====
print("\n" + "=" * 70)
print("SQQQ LEAN OUTPUT prices (after converter with corrections)")
print("=" * 70)

lean_dates = ['20191001', '20200101', '20220101', '20241101', '20251119', '20251120', '20251201', '20260102']

for date_str in lean_dates:
    zip_path = lean_dir / "sqqq" / f"{date_str}_trade.zip"
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as cf:
                lines = cf.read().decode().strip().split('\n')
                # First and last line
                first = lines[0].split(',')
                last = lines[-1].split(',')
                first_price = int(first[1]) / 10000
                last_price = int(last[4]) / 10000
                print(f"  {date_str}: first_open=${first_price:.2f}  last_close=${last_price:.2f}  ({len(lines)} bars)")
    else:
        print(f"  {date_str}: ZIP not found")

# ===== CHECK TQQQ TOO =====
print("\n" + "=" * 70)
print("TQQQ LEAN OUTPUT prices (after converter with corrections)")
print("=" * 70)

for date_str in ['20200101', '20210120', '20210121', '20220112', '20220113', '20251119', '20251120', '20260102']:
    zip_path = lean_dir / "tqqq" / f"{date_str}_trade.zip"
    if zip_path.exists():
        with zipfile.ZipFile(zip_path) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as cf:
                lines = cf.read().decode().strip().split('\n')
                first = lines[0].split(',')
                last = lines[-1].split(',')
                first_price = int(first[1]) / 10000
                last_price = int(last[4]) / 10000
                print(f"  {date_str}: first_open=${first_price:.2f}  last_close=${last_price:.2f}  ({len(lines)} bars)")
    else:
        print(f"  {date_str}: ZIP not found")

# ===== SANITY CHECK: What should SQQQ prices actually be? =====
print("\n" + "=" * 70)
print("SANITY CHECK")
print("=" * 70)
print("""
Known SQQQ facts (from public records):
- SQQQ is a 3x inverse QQQ ETF, launched 2010
- 1:5 reverse splits roughly every 1-2 years to keep price manageable
- Alpaca shows SQQQ = $68.42 on Jan 1, 2026 (verified raw price)
- Before Nov 2025 split, SQQQ was trading around $65-80 range
- Pre-split (before the 2024 reverse split), prices would have been lower

If our converter is correct:
- 2026-01-02 should show ~$67-69 (matches Alpaca $68.42)
- 2025-11-20 should show ~$68-70 (post-split, raw)
- 2025-11-19 should show ~$70-75 (pre-split, should be similar range)
  NOT $14.43 (the ÷5 adjusted price from Databento)
  $14.43 * 5 = $72.15 ← This is what we expect after correction

If prices are in thousands or millions, the cumulative factor is WRONG.
""")
