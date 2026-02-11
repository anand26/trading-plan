"""Check TQQQ data around split dates to verify factor file calculation."""
import zipfile

with zipfile.ZipFile('quantconnect-lean/Data/equity/usa/daily/tqqq.zip') as z:
    with z.open('tqqq.csv') as f:
        all_lines = f.readlines()

print("=== TQQQ around Jun 2010 split ===")
for line in all_lines:
    decoded = line.decode().strip()
    date = decoded.split(',')[0].split()[0]
    if date in ['20100618', '20100621', '20100622', '20100623', '20100624']:
        parts = decoded.split(',')
        close = int(parts[4])
        print(f"  {date}: close={close} (${close/10000:.4f})")

print("\n=== TQQQ around May 2018 split ===")
for line in all_lines:
    decoded = line.decode().strip()
    date = decoded.split(',')[0].split()[0]
    if date in ['20180522', '20180523', '20180524']:
        parts = decoded.split(',')
        close = int(parts[4])
        print(f"  {date}: close={close} (${close/10000:.4f})")

print("\n=== TQQQ around Jan 2021 split ===")
for line in all_lines:
    decoded = line.decode().strip()
    date = decoded.split(',')[0].split()[0]
    if date in ['20210119', '20210120', '20210121']:
        parts = decoded.split(',')
        close = int(parts[4])
        print(f"  {date}: close={close} (${close/10000:.4f})")

print("\n=== TQQQ around Jan 2022 split ===")
for line in all_lines:
    decoded = line.decode().strip()
    date = decoded.split(',')[0].split()[0]
    if date in ['20220111', '20220112', '20220113']:
        parts = decoded.split(',')
        close = int(parts[4])
        print(f"  {date}: close={close} (${close/10000:.4f})")

print("\n=== TQQQ around Nov 2025 split ===")
for line in all_lines:
    decoded = line.decode().strip()
    date = decoded.split(',')[0].split()[0]
    if date in ['20251118', '20251119', '20251120']:
        parts = decoded.split(',')
        close = int(parts[4])
        print(f"  {date}: close={close} (${close/10000:.4f})")

# Now do the same for SQQQ
with zipfile.ZipFile('quantconnect-lean/Data/equity/usa/daily/sqqq.zip') as z:
    with z.open('sqqq.csv') as f:
        sqqq_lines = f.readlines()

print("\n\n=== SQQQ first 5 days ===")
for line in sqqq_lines[:5]:
    decoded = line.decode().strip()
    parts = decoded.split(',')
    close = int(parts[4])
    print(f"  {parts[0]}: close={close} (${close/10000:.4f})")

print("\n=== SQQQ around May 2019 (first factor entry) ===")
for line in sqqq_lines:
    decoded = line.decode().strip()
    date = decoded.split(',')[0].split()[0]
    if date in ['20190522', '20190523', '20190524']:
        parts = decoded.split(',')
        close = int(parts[4])
        print(f"  {date}: close={close} (${close/10000:.4f})")
