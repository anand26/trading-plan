"""Calculate correct factor file entries for TQQQ and SQQQ back to IPO."""
import pandas as pd
import zipfile

# Load yfinance data (has both Close and Adj Close)
for sym in ['TQQQ', 'SQQQ']:
    df = pd.read_csv(f'Data/yfinance/daily/{sym}_daily.csv')
    first = df.iloc[0]
    
    # Load zip data for comparison
    with zipfile.ZipFile(f'quantconnect-lean/Data/equity/usa/daily/{sym.lower()}.zip') as z:
        with z.open(z.namelist()[0]) as f:
            zip_first = f.readline().decode().strip()
    
    zip_close = int(zip_first.split(',')[4]) / 10000
    
    print(f"=== {sym} ===")
    print(f"  First date: {first['Date']}")
    print(f"  yfinance Close (unadjusted): ${first['Close']:.4f}")
    print(f"  yfinance Adj Close:          ${first['Adj Close']:.4f}")
    print(f"  Zip close (LEAN raw):        ${zip_close:.4f}")
    
    # Check if zip data matches Adj Close or Close
    adj_match = abs(zip_close - first['Adj Close']) < 0.01
    raw_match = abs(zip_close - first['Close']) < 0.01
    print(f"  Zip matches Adj Close? {adj_match}")
    print(f"  Zip matches Close?     {raw_match}")
    
    if adj_match:
        # Zip has adjusted prices. LEAN expects raw prices.
        # Factor = adj / raw, so LEAN can reconstruct: raw * factor = adj
        # Actually LEAN: adjustedPrice = rawPrice * priceFactor * splitFactor
        # But our zip IS adjusted. So when LEAN applies factor, it double-adjusts.
        # We'd need factor = 1 so LEAN doesn't adjust further.
        print(f"  ZIP has ADJUSTED prices (matches Adj Close)")
        print(f"  splitFactor should be 1.0 for all dates")
    elif raw_match:
        # Zip has raw prices. Normal factor file behavior.
        print(f"  ZIP has RAW (unadjusted) prices")
        # splitFactor = how much to multiply raw to get adjusted
        factor = first['Adj Close'] / first['Close']
        print(f"  splitFactor at IPO = {factor:.10f}")
    else:
        print(f"  ZIP matches NEITHER! adj_diff={abs(zip_close - first['Adj Close']):.4f}, raw_diff={abs(zip_close - first['Close']):.4f}")
        # Might match approximately
        adj_ratio = zip_close / first['Adj Close'] if first['Adj Close'] != 0 else 0
        raw_ratio = zip_close / first['Close'] if first['Close'] != 0 else 0
        print(f"  zip/adj ratio: {adj_ratio:.6f}")
        print(f"  zip/raw ratio: {raw_ratio:.6f}")
    
    print()

# Also verify for a recent date where factor=1 (no adjustment needed)
print("=== Verification: recent date (should match exactly) ===")
for sym in ['TQQQ', 'SQQQ']:
    df = pd.read_csv(f'Data/yfinance/daily/{sym}_daily.csv')
    last = df.iloc[-1]
    
    with zipfile.ZipFile(f'quantconnect-lean/Data/equity/usa/daily/{sym.lower()}.zip') as z:
        with z.open(z.namelist()[0]) as f:
            lines = f.readlines()
            zip_last = lines[-1].decode().strip()
    
    zip_close = int(zip_last.split(',')[4]) / 10000
    
    print(f"  {sym} last date: {last['Date']}")
    print(f"    yfinance Close: ${last['Close']:.4f}")
    print(f"    yfinance Adj:   ${last['Adj Close']:.4f}")
    print(f"    Zip close:      ${zip_close:.4f}")
    print(f"    Zip==Close? {abs(zip_close - last['Close']) < 0.01}")
    print(f"    Zip==Adj?   {abs(zip_close - last['Adj Close']) < 0.01}")
