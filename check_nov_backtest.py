import json
from datetime import datetime

BT_DIR = 'backtest/results/BT_20260206_044648_4912f873'

# Load order events
orders = json.load(open(f'{BT_DIR}/TQQQSQQQPairsAlgorithm-order-events.json'))
sqqq_filled = [o for o in orders if o.get('symbolValue','')=='SQQQ' and o.get('status','')=='filled']
tqqq_filled = [o for o in orders if o.get('symbolValue','')=='TQQQ' and o.get('status','')=='filled']

print(f"Total orders: {len(orders)}")
print(f"SQQQ filled: {len(sqqq_filled)}")
print(f"TQQQ filled: {len(tqqq_filled)}")

print("\n=== ALL SQQQ fills (chronological) ===")
for o in sqqq_filled:
    t = datetime.fromtimestamp(o['time'])
    d = o['direction']
    qty = int(o['fillQuantity'])
    price = o['fillPrice']
    print(f"  {t} | {d:4s} | qty={qty:7d} | price=${price:.4f}")

print("\n=== ALL TQQQ fills (chronological) ===")
for o in tqqq_filled:
    t = datetime.fromtimestamp(o['time'])
    d = o['direction']
    qty = int(o['fillQuantity'])
    price = o['fillPrice']
    print(f"  {t} | {d:4s} | qty={qty:7d} | price=${price:.4f}")

# Also check the algorithm log for price data
print("\n\n=== Algorithm Log (first 100 lines) ===")
with open(f'{BT_DIR}/TQQQSQQQPairsAlgorithm-log.txt', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:100]):
        print(f"  {line.rstrip()}")
    print(f"\n  ... ({len(lines)} total lines)")

# Look for any price-related log entries
print("\n=== Log lines mentioning 'price' or 'SQQQ' (first 50) ===")
count = 0
for line in lines:
    if 'price' in line.lower() or 'sqqq' in line.lower():
        print(f"  {line.rstrip()}")
        count += 1
        if count >= 50:
            break
