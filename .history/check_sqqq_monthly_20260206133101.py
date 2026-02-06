import json
from datetime import datetime

orders = json.load(open('backtest/results/BT_20260206_033228_1567d584/TQQQSQQQPairsAlgorithm-order-events.json'))
sqqq_filled = [o for o in orders if o.get('symbolValue','')=='SQQQ' and o.get('status','')=='filled']
print(f'Total SQQQ filled: {len(sqqq_filled)}')

# Show fills across months with prices
monthly = {}
for o in sqqq_filled:
    t = datetime.fromtimestamp(o['time'])
    month_key = t.strftime('%Y-%m')
    if month_key not in monthly:
        monthly[month_key] = []
    monthly[month_key].append(o['fillPrice'])

print("\n=== Monthly SQQQ Fill Price Summary ===")
for month in sorted(monthly.keys()):
    prices = monthly[month]
    min_p = min(prices)
    max_p = max(prices)
    avg_p = sum(prices)/len(prices)
    print(f"  {month}: fills={len(prices):3d}  min=${min_p:7.2f}  max=${max_p:7.2f}  avg=${avg_p:7.2f}")

# What should real SQQQ prices be?
print("\n=== Expected Real SQQQ Prices (approx) ===")
print("  2025-01: ~$37-42  (pre-split adjusted would be /5 = $7-8)")
print("  2025-04: ~$55-65")
print("  2025-08: ~$90-100 (if /5 = $18-20)")
print("  2025-11: ~$65-80")

# Show first 10 and last 10 fills
print("\n=== First 10 SQQQ fills ===")
for o in sqqq_filled[:10]:
    t = datetime.fromtimestamp(o['time'])
    d = 'buy' if o['direction'] == 'buy' else 'sell'
    print(f"  {t} | {d:4s} | qty={o['fillQuantity']:7d} | price=${o['fillPrice']:.4f}")

print("\n=== Last 10 SQQQ fills ===")
for o in sqqq_filled[-10:]:
    t = datetime.fromtimestamp(o['time'])
    d = 'buy' if o['direction'] == 'buy' else 'sell'
    print(f"  {t} | {d:4s} | qty={o['fillQuantity']:7d} | price=${o['fillPrice']:.4f}")

# Also check TQQQ prices
tqqq_filled = [o for o in orders if o.get('symbolValue','')=='TQQQ' and o.get('status','')=='filled']
print(f"\n\nTotal TQQQ filled: {len(tqqq_filled)}")
monthly_tqqq = {}
for o in tqqq_filled:
    t = datetime.fromtimestamp(o['time'])
    month_key = t.strftime('%Y-%m')
    if month_key not in monthly_tqqq:
        monthly_tqqq[month_key] = []
    monthly_tqqq[month_key].append(o['fillPrice'])

print("\n=== Monthly TQQQ Fill Price Summary ===")
for month in sorted(monthly_tqqq.keys()):
    prices = monthly_tqqq[month]
    min_p = min(prices)
    max_p = max(prices)
    avg_p = sum(prices)/len(prices)
    print(f"  {month}: fills={len(prices):3d}  min=${min_p:7.2f}  max=${max_p:7.2f}  avg=${avg_p:7.2f}")

# Check ratio of fill price to expected real price for a key date
print("\n=== Price Ratio Analysis ===")
for o in sqqq_filled:
    t = datetime.fromtimestamp(o['time'])
    if t.strftime('%Y-%m-%d') == '2025-11-20':
        print(f"  Nov 20 fill: ${o['fillPrice']:.4f} (expected ~$70, ratio: {70/o['fillPrice']:.2f}x)")
        break

# Check if SQQQ price jumps abruptly (suggesting split boundary)
print("\n=== Detecting price jumps (possible split boundary) ===")
prev_price = None
for o in sqqq_filled:
    t = datetime.fromtimestamp(o['time'])
    price = o['fillPrice']
    if prev_price and prev_price > 0:
        ratio = price / prev_price
        if ratio > 2.0 or ratio < 0.5:
            print(f"  JUMP at {t}: ${prev_price:.2f} -> ${price:.2f} (ratio: {ratio:.2f}x)")
    prev_price = price
