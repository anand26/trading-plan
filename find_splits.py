"""Find exact split dates and ratios from the raw price data in LEAN zips."""
import zipfile

def load_zip_data(sym):
    path = f'quantconnect-lean/Data/equity/usa/daily/{sym}.zip'
    data = []
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as f:
            for line in f:
                parts = line.decode().strip().split(',')
                date = parts[0].split()[0]  # strip time component
                close = int(parts[4]) / 10000
                data.append((date, close))
    return data

# Find price jumps that indicate reverse splits
# A reverse split shows as a sudden price DROP in raw data 
# (e.g., 1:10 means 10 old shares -> 1 new share, so price jumps 10x on the new day)
# BUT in raw historical data, the pre-split prices are NOT adjusted
# So on split day, price appears to jump UP (new share = 10 old shares worth)

for sym in ['tqqq', 'sqqq']:
    print(f"=== {sym.upper()} price jumps (potential splits) ===")
    data = load_zip_data(sym)
    
    for i in range(1, len(data)):
        prev_date, prev_close = data[i-1]
        curr_date, curr_close = data[i]
        
        if prev_close == 0:
            continue
            
        ratio = curr_close / prev_close
        # Reverse split: price jumps UP by split ratio (e.g., 10x for 1:10)
        if ratio > 1.5 or ratio < 0.67:
            print(f"  {prev_date} -> {curr_date}: ${prev_close:.4f} -> ${curr_close:.4f} "
                  f"(ratio: {ratio:.4f}, likely {round(ratio)}:1 reverse split)" if ratio > 1 else 
                  f"  {prev_date} -> {curr_date}: ${prev_close:.4f} -> ${curr_close:.4f} "
                  f"(ratio: {ratio:.4f}, likely 1:{round(1/ratio)} forward split)")
    print()
