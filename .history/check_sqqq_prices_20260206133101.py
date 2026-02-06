"""Check SQQQ raw data prices across dates to determine if data is split-adjusted."""
import zipfile
import os

data_dir = r"C:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute\sqqq"

# Key dates to check:
# SQQQ had 1:5 reverse splits on:
#   - Jan 12, 2024
#   - Jan 12, 2023
# So if data is RAW (unadjusted):
#   - Before Jan 2023: prices should be LOW (~$5-30 range)
#   - After Jan 2023 split: prices jump UP (multiplied by 5)
#   - After Jan 2024 split: prices jump UP again (multiplied by 5)
#   - Nov 2025: actual market price was ~$65-80
# If data is ADJUSTED (normalized):
#   - All dates: prices look consistent/smooth (~$10-15 range)

dates_to_check = [
    ('20220103', 'Jan 3, 2022 (before both splits)'),
    ('20221003', 'Oct 3, 2022 (before both splits)'),
    ('20230111', 'Jan 11, 2023 (day BEFORE 1st split)'),
    ('20230112', 'Jan 12, 2023 (1st split day)'),
    ('20230113', 'Jan 13, 2023 (day AFTER 1st split)'),
    ('20230605', 'Jun 5, 2023 (between splits)'),
    ('20240111', 'Jan 11, 2024 (day BEFORE 2nd split)'),
    ('20240112', 'Jan 12, 2024 (2nd split day)'),
    ('20240115', 'Jan 15, 2024 (day AFTER 2nd split)'),
    ('20240701', 'Jul 1, 2024'),
    ('20250102', 'Jan 2, 2025'),
    ('20250602', 'Jun 2, 2025'),
    ('20251103', 'Nov 3, 2025'),
    ('20260113', 'Jan 13, 2026 (latest data)'),
]

print(f"{'Date':<12} {'Description':<40} {'Price ($)':<12} {'Raw Value':<12}")
print("-" * 80)

for date, desc in dates_to_check:
    zip_path = os.path.join(data_dir, f"{date}_trade.zip")
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path) as z:
            name = z.namelist()[0]
            with z.open(name) as f:
                line = f.readline().decode().strip()
                parts = line.split(",")
                raw_val = int(parts[1])
                price = raw_val / 10000.0
                print(f"{date:<12} {desc:<40} ${price:<11.2f} {raw_val}")
    else:
        print(f"{date:<12} {desc:<40} {'N/A':<12} {'N/A'}")

# Also check TQQQ
print("\n\n=== TQQQ CHECK ===")
tqqq_dir = r"C:\Users\anand\Documents\trading_plan\quantconnect-lean\Data\equity\usa\minute\tqqq"
tqqq_dates = [
    ('20251103', 'Nov 3, 2025'),
    ('20250102', 'Jan 2, 2025'),
    ('20240115', 'Jan 15, 2024'),
]
for date, desc in tqqq_dates:
    zip_path = os.path.join(tqqq_dir, f"{date}_trade.zip")
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path) as z:
            name = z.namelist()[0]
            with z.open(name) as f:
                line = f.readline().decode().strip()
                parts = line.split(",")
                raw_val = int(parts[1])
                price = raw_val / 10000.0
                print(f"{date:<12} {desc:<40} ${price:<11.2f} {raw_val}")
    else:
        print(f"{date:<12} {desc:<40} {'N/A':<12} {'N/A'}")
