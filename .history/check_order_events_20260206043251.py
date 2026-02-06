import json
from datetime import datetime

bt_dir = 'backtest/results/BT_20260206_033228_1567d584'

with open(f'{bt_dir}/TQQQSQQQPairsAlgorithm-order-events.json', 'r') as f:
    orders = json.load(f)

# Find SQQQ fills with low prices
low_price_fills = []
for o in orders:
    if 'SQQQ' in str(o.get('symbolValue', '')) and o.get('status') == 'filled':
        fp = o.get('fillPrice', 0)
        if fp > 0 and fp < 20:
            low_price_fills.append(o)

print(f'SQQQ fills with price < $20: {len(low_price_fills)}')
for o in low_price_fills[:10]:
    t = datetime.fromtimestamp(o['time'])
    direction = o['direction']
    qty = o['fillQuantity']
    price = o['fillPrice']
    oid = o['orderId']
    print(f'  {t} | {direction:4s} | qty={qty:8.0f} | price=${price:.4f} | orderId={oid}')

# Also find largest fills by value
print()
print('=== Largest SQQQ fills by absolute quantity x price ===')
sqqq_fills = [o for o in orders if 'SQQQ' in str(o.get('symbolValue', '')) and o.get('status') == 'filled' and o.get('fillPrice', 0) > 0]
sqqq_fills.sort(key=lambda x: abs(x['fillQuantity'] * x['fillPrice']), reverse=True)
for o in sqqq_fills[:10]:
    t = datetime.fromtimestamp(o['time'])
    direction = o['direction']
    qty = o['fillQuantity']
    price = o['fillPrice']
    val = abs(qty * price)
    print(f'  {t} | {direction:4s} | qty={qty:8.0f} | price=${price:.2f} | value=${val:,.0f}')

# Check all unique prices for SQQQ
print()
print('=== SQQQ Fill Price Distribution ===')
prices = [o['fillPrice'] for o in sqqq_fills]
prices.sort()
print(f'Min: ${min(prices):.2f}')
print(f'Max: ${max(prices):.2f}')
print(f'Median: ${prices[len(prices)//2]:.2f}')

# Count in ranges
ranges = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100), (100, 200)]
for lo, hi in ranges:
    count = sum(1 for p in prices if lo <= p < hi)
    if count > 0:
        print(f'  ${lo}-${hi}: {count} fills')
