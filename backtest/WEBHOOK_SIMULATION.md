# Webhook Simulation for Backtesting

## Overview

The webhook simulator ensures your backtests accurately reflect live trading behavior where TradingView sends webhooks at regular intervals to trigger strategy execution.

## Problem Solved

**Without Webhook Simulation:**
- Backtests process every tick/bar immediately
- No visibility into when webhooks would fire in live trading
- Timing mismatches between backtest and live behavior
- Can't validate if your 5-minute alert strategy actually works as expected

**With Webhook Simulation:**
- Logs when webhooks WOULD fire based on your TradingView alert configuration
- Shows exact market conditions at webhook trigger time
- Validates that backtest behavior matches live expectations
- Provides audit trail of all simulated webhook events

## How It Works

### 1. Scheduled Webhooks (Regular Interval)

Simulates TradingView alerts firing at fixed intervals:

```python
# In TQQQScalpingAlgorithm.py
def OnTQQQBarConsolidated(self, sender, bar: TradeBar):
    # Webhook fires every 5 minutes during trading hours (9:30 AM - 4:00 PM)
    if self.webhook_simulator:
        market_data = self._get_market_data_snapshot("TQQQ", bar)
        self.webhook_simulator.trigger_scheduled_webhook(
            current_time=self.Time,
            symbol="TQQQ",
            market_data=market_data
        )
```

**Output:**
```
[WEBHOOK #1] SCHEDULED | TQQQ @ 45.50 | 5-minute interval
[WEBHOOK #2] SCHEDULED | TQQQ @ 45.62 | 5-minute interval
[WEBHOOK #3] SCHEDULED | TQQQ @ 45.48 | 5-minute interval
```

### 2. Signal Webhooks (Trading Events)

Logs when buy/sell signals are generated:

```python
# When entering a position
if self.webhook_simulator:
    self.webhook_simulator.trigger_signal_webhook(
        current_time=self.Time,
        symbol="TQQQ",
        signal_type="BUY_L1",
        market_data=market_data,
        trigger_conditions={
            "rsi": 28.5,
            "price": 45.50,
            "bb_lower": 44.80,
            "volume_spike": True
        }
    )
```

**Output:**
```
[WEBHOOK #15] SIGNAL | TQQQ @ 45.50 | BUY_L1 signal detected
```

### 3. Alert Webhooks (Stop Loss / Take Profit)

Logs when price alerts would fire:

```python
# When stop loss hits
if self.webhook_simulator:
    self.webhook_simulator.trigger_alert_webhook(
        current_time=self.Time,
        symbol="TQQQ",
        alert_type="STOP_LOSS",
        market_data=market_data,
        alert_message=f"Stop loss triggered at -2.00%"
    )
```

**Output:**
```
[WEBHOOK #42] ALERT | TQQQ @ 44.60 | Stop loss triggered at -2.00%
```

## Configuration

### Enable/Disable Webhook Simulation

**In Algorithm Parameters:**
```python
# Enabled by default in backtests
"webhook-simulation": "true"

# To disable:
"webhook-simulation": "false"
```

**In Backtest Runner:**
```python
config = BacktestConfig(
    session_id="BT_20260113_150000",
    start_date="2024-01-01",
    end_date="2024-12-31"
)
# Webhook simulation automatically enabled
```

### Customize Webhook Interval

Match your TradingView alert frequency:

```python
self.webhook_simulator = WebhookSimulator(
    interval_minutes=5,  # TradingView alert every 5 minutes
    trading_hours=(datetime.time(9, 30), datetime.time(16, 0)),
    enable_signal_webhooks=True,
    enable_status_webhooks=True
)
```

### Log File Location

Webhook events are logged to:
```
backtest/results/<session_id>/webhook_log.txt
```

Example:
```
backtest/results/BT_20260113_150000_a1b2c3d4/webhook_log.txt
```

## Webhook Event Structure

Each webhook event contains:

```python
{
    "timestamp": "2024-06-15T10:35:00",
    "type": "scheduled",  # or "signal", "alert", "status"
    "symbol": "TQQQ",
    "reason": "5-minute interval",
    "bar_time": "2024-06-15T10:35:00",
    "price": 45.50,
    "conditions": {
        "rsi": 28.5,
        "vwap": 45.80,
        "bb_lower": 44.80
    },
    "market_data": {
        "price": 45.50,
        "open": 45.40,
        "high": 45.65,
        "low": 45.35,
        "volume": 125000,
        "rsi": 28.5,
        "vwap": 45.80,
        "bb_upper": 46.80,
        "bb_middle": 45.80,
        "bb_lower": 44.80,
        "position_quantity": 500,
        "position_value": 22750.00,
        "unrealized_pnl": 125.50,
        "market_regime": "trending_up"
    }
}
```

## Reading Webhook Logs

### During Backtest

Check console output for webhook summary:

```
[WEBHOOK] Simulation enabled - logging to backtest/results/.../webhook_log.txt
...
[WEBHOOK] Simulation Summary:
  Total webhooks fired: 156
  Scheduled: 120
  Signals: 28
  Alerts: 6
  Status: 2
  Webhook log: See results folder
```

### After Backtest

Read the webhook log file:

```python
import json

with open("backtest/results/BT_20260113_150000/webhook_log.txt") as f:
    for line in f:
        if "WEBHOOK" in line:
            print(line.strip())
```

### Analyze Webhook Patterns

```python
from webhook_simulator import WebhookSimulator

# Parse webhook events
simulator = WebhookSimulator()
summary = simulator.get_summary()

print(f"Total: {summary['total_webhooks']}")
print(f"Scheduled: {summary['by_type']['scheduled']}")
print(f"Signals: {summary['by_type']['signal']}")

# Get all webhook events
events = summary['events']
for event in events:
    print(f"{event['timestamp']} | {event['symbol']} @ {event['price']}")
```

## Validation Checklist

Use webhook logs to validate backtest vs live behavior:

- [ ] **Timing**: Webhooks fire at exact intervals (e.g., every 5 min)
- [ ] **Trading Hours**: No webhooks outside 9:30 AM - 4:00 PM EST
- [ ] **Signal Count**: Number of BUY/SELL signals matches trades
- [ ] **Alert Triggers**: Stop loss webhooks match liquidations
- [ ] **Market Data**: Indicator values match at webhook time
- [ ] **Position Sync**: Position quantities match at webhook trigger

## Comparing Backtest vs Live

### Backtest Webhook Log:
```
2024-06-15 10:35:00 - [WEBHOOK #1] SCHEDULED | TQQQ @ 45.50 | RSI=28.5
2024-06-15 10:40:00 - [WEBHOOK #2] SCHEDULED | TQQQ @ 45.62 | RSI=30.2
2024-06-15 10:45:00 - [WEBHOOK #3] SIGNAL | TQQQ @ 45.48 | BUY_L1
```

### Live TradingView Webhook Log:
```
2024-06-15 10:35:00 - TradingView Alert: TQQQ @ 45.50 | RSI=28.5
2024-06-15 10:40:00 - TradingView Alert: TQQQ @ 45.62 | RSI=30.2  
2024-06-15 10:45:00 - TradingView Alert: TQQQ @ 45.48 | BUY_L1
```

✅ **Match!** Backtest behavior mirrors live trading.

## Benefits

1. **Confidence**: Know your backtest accurately represents live trading
2. **Debugging**: See exactly when and why webhooks fire
3. **Optimization**: Identify if 5-minute intervals are optimal
4. **Audit Trail**: Complete history of all webhook events
5. **Validation**: Verify TradingView alert configuration before going live

## Advanced Usage

### Custom Webhook Types

Add custom webhook types for specific use cases:

```python
# In TQQQScalpingAlgorithm.py
if self.webhook_simulator:
    self.webhook_simulator.trigger_status_webhook(
        current_time=self.Time,
        symbol="TQQQ",
        status_type="POSITION_OPENED",
        market_data=market_data
    )
```

### Webhook Event Callbacks

Process webhook events in real-time:

```python
def on_webhook_fired(event):
    # Custom logic when webhook fires
    if event.webhook_type == WebhookType.SIGNAL:
        # Validate signal conditions
        pass

simulator = WebhookSimulator()
simulator.on_webhook = on_webhook_fired
```

### Export Webhook Data

Export webhook events to CSV for analysis:

```python
import pandas as pd

summary = simulator.get_summary()
events = summary['events']

df = pd.DataFrame(events)
df.to_csv("webhook_analysis.csv", index=False)
```

## Troubleshooting

### No Webhooks Logged

**Check:**
1. Webhook simulation enabled: `webhook-simulation=true`
2. Not in warmup period: Webhooks only fire after `IsWarmingUp == False`
3. Trading hours: Webhooks only fire during 9:30 AM - 4:00 PM
4. Log file path: Verify `webhook_log.txt` exists in results folder

### Webhook Count Mismatch

**Expected for 1 day of trading:**
- Trading hours: 6.5 hours (9:30 AM - 4:00 PM)
- 5-minute intervals: 6.5 * 60 / 5 = 78 scheduled webhooks
- Plus signal webhooks (BUY/SELL)
- Plus alert webhooks (stop loss/take profit)

**Total: ~80-100 webhooks per trading day**

### Timing Off by a Few Seconds

This is normal - LEAN consolidates bars to 5-minute intervals, so webhook timing may be slightly off from exact clock times. The important part is the **interval consistency** (every 5 minutes), not absolute timing.

## Next Steps

1. Run a backtest with webhook simulation enabled
2. Review `webhook_log.txt` in results folder
3. Verify webhook timing matches your TradingView alert config
4. Use webhook data to validate strategy behavior
5. Deploy to live trading with confidence! 🚀
