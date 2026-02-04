# Quick Start: Webhook Simulation

## In 3 Steps

### 1. Run Tests (Verify Everything Works)
```bash
cd backtest
python test_webhook_simulator.py
```

Expected:
```
✓ ALL TESTS PASSED - Webhook simulator ready for use!
```

### 2. Run a Backtest
```bash
python backtest_runner.py --start 2024-01-01 --end 2024-01-31
```

### 3. Check Webhook Log
```bash
# Log location printed in backtest output
cat results/<session_id>/webhook_log.txt
```

## What You'll See

```
[WEBHOOK #1] SCHEDULED | TQQQ @ 45.50 | 5-minute interval
[WEBHOOK #2] SCHEDULED | TQQQ @ 45.62 | 5-minute interval
[WEBHOOK #15] SIGNAL | TQQQ @ 45.48 | BUY_L1 signal detected
[WEBHOOK #42] ALERT | TQQQ @ 44.60 | Stop loss triggered at -2.00%
```

## Expected Webhook Counts

**For 1 Trading Day:**
- Scheduled: ~79 webhooks (every 5 min, 9:30 AM - 4:00 PM)
- Signals: Varies (depends on how many trades)
- Alerts: Varies (depends on stop losses)

**For 1 Month (20 trading days):**
- Scheduled: ~1,580 webhooks
- Signals: 20-100 (depends on strategy)
- Alerts: 5-30 (depends on stop losses)

## Validation

✅ **Timing is correct** if webhooks fire every 5 minutes during trading hours  
✅ **Signals match** if BUY/SELL webhooks align with actual trades  
✅ **Ready for live** if backtest webhook behavior matches expectations

## Troubleshooting

**No webhooks logged?**
- Check: `webhook-simulation` parameter is `"true"`
- Check: Not in warmup period (first 30 days skipped)
- Check: Trading hours (9:30 AM - 4:00 PM only)

**Wrong webhook count?**
- Expected: 79 per day for 5-minute intervals
- Check: Trading hours calculation (6.5 hours = 390 minutes / 5 = 78 + 1)

## Ready for Live Trading

When webhook logs show expected behavior:
1. Set up TradingView alert (5-minute interval)
2. Configure webhook URL in TradingView
3. Deploy algorithm to live trading
4. Compare live webhook logs to backtest logs ✅

---

**That's it!** Webhook simulation is now part of your backtesting workflow.
