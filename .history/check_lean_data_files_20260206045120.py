"""Check LEAN minute data files for SQQQ around the price transition date"""
import zipfile
import os

DATA_DIR = 'quantconnect-lean/Data/equity/usa/minute/sqqq'

# Check dates around the transition
dates = ['20251114', '20251117', '20251119', '20251120', '20251121']

for date in dates:
    fname = f'{DATA_DIR}/{date}_trade.zip'
    if not os.path.exists(fname):
        print(f"\n{date}: FILE MISSING!")
        continue
    
    with zipfile.ZipFile(fname) as z:
        for name in z.namelist():
            with z.open(name) as f:
                lines = f.read().decode().strip().split('\n')
                # LEAN format: milliseconds,open*10000,high*10000,low*10000,close*10000,volume
                first_line = lines[0]
                last_line = lines[-1]
                parts_first = first_line.split(',')
                parts_last = last_line.split(',')
                
                open_first = int(parts_first[1]) / 10000
                close_first = int(parts_first[4]) / 10000
                open_last = int(parts_last[1]) / 10000
                close_last = int(parts_last[4]) / 10000
                
                print(f"\n{date} ({len(lines)} bars):")
                print(f"  First bar: open=${open_first:.2f}, close=${close_first:.2f}")
                print(f"  Last bar:  open=${open_last:.2f}, close=${close_last:.2f}")
                
                # Show a few more lines around mid-day
                if len(lines) > 200:
                    mid = len(lines) // 2
                    parts_mid = lines[mid].split(',')
                    open_mid = int(parts_mid[1]) / 10000
                    close_mid = int(parts_mid[4]) / 10000
                    # Time is in milliseconds from midnight
                    time_ms = int(parts_mid[0])
                    hours = time_ms // 3600000
                    mins = (time_ms % 3600000) // 60000
                    print(f"  Mid bar ({hours}:{mins:02d}): open=${open_mid:.2f}, close=${close_mid:.2f}")

# Also check TQQQ
print("\n\n=== TQQQ Data Files ===")
TQQQ_DIR = 'quantconnect-lean/Data/equity/usa/minute/tqqq'
tqqq_dates = ['20251117', '20251119', '20251120', '20251121']

for date in tqqq_dates:
    fname = f'{TQQQ_DIR}/{date}_trade.zip'
    if not os.path.exists(fname):
        print(f"\n{date}: FILE MISSING!")
        continue
    
    with zipfile.ZipFile(fname) as z:
        for name in z.namelist():
            with z.open(name) as f:
                lines = f.read().decode().strip().split('\n')
                parts_first = lines[0].split(',')
                parts_last = lines[-1].split(',')
                open_first = int(parts_first[1]) / 10000
                close_first = int(parts_first[4]) / 10000
                open_last = int(parts_last[1]) / 10000
                close_last = int(parts_last[4]) / 10000
                print(f"\n{date} ({len(lines)} bars):")
                print(f"  First bar: open=${open_first:.2f}, close=${close_first:.2f}")
                print(f"  Last bar:  open=${open_last:.2f}, close=${close_last:.2f}")
