"""
Test Webhook Simulator
======================
Verify webhook simulation works correctly before running full backtest.
"""

import sys
import os
from datetime import datetime, time, timedelta

# Add backtest folder to path
sys.path.append(os.path.dirname(__file__))

from webhook_simulator import WebhookSimulator, WebhookType


def test_scheduled_webhooks():
    """Test scheduled webhook triggers"""
    print("=" * 60)
    print("TEST 1: Scheduled Webhooks (5-minute intervals)")
    print("=" * 60)
    
    simulator = WebhookSimulator(
        interval_minutes=5,
        trading_hours=(time(9, 30), time(16, 0))
    )
    
    # Simulate trading day from 9:30 AM to 4:00 PM
    start_time = datetime(2024, 6, 15, 9, 30, 0)
    end_time = datetime(2024, 6, 15, 16, 0, 0)
    current_time = start_time
    
    webhook_count = 0
    while current_time <= end_time:
        market_data = {
            "price": 45.50,
            "rsi": 35.0,
            "vwap": 45.80
        }
        
        event = simulator.trigger_scheduled_webhook(
            current_time=current_time,
            symbol="TQQQ",
            market_data=market_data
        )
        
        if event:
            webhook_count += 1
            print(f"✓ Webhook #{webhook_count} @ {current_time.strftime('%H:%M:%S')}")
        
        # Advance time by 1 minute
        current_time += timedelta(minutes=1)
    
    summary = simulator.get_summary()
    expected_webhooks = 79  # From 9:30 AM to 4:00 PM inclusive (6.5 hours / 5 min = 78 + 1 for 4:00 PM)
    
    print(f"\nExpected: ~{expected_webhooks} webhooks")
    print(f"Actual: {summary['total_webhooks']} webhooks")
    print(f"Status: {'✓ PASS' if summary['total_webhooks'] == expected_webhooks else '✗ FAIL'}")
    
    return summary['total_webhooks'] == expected_webhooks


def test_signal_webhooks():
    """Test signal webhook triggers"""
    print("\n" + "=" * 60)
    print("TEST 2: Signal Webhooks (BUY/SELL)")
    print("=" * 60)
    
    simulator = WebhookSimulator(
        interval_minutes=5,
        enable_signal_webhooks=True
    )
    
    current_time = datetime(2024, 6, 15, 10, 35, 0)
    
    # Trigger BUY signal
    buy_event = simulator.trigger_signal_webhook(
        current_time=current_time,
        symbol="TQQQ",
        signal_type="BUY_L1",
        market_data={"price": 45.50, "rsi": 28.5},
        trigger_conditions={
            "rsi_oversold": True,
            "bb_lower_breach": True,
            "volume_spike": True
        }
    )
    
    if buy_event:
        print(f"✓ BUY signal webhook: {buy_event.trigger_reason}")
    
    # Trigger SELL signal
    current_time += timedelta(minutes=15)
    sell_event = simulator.trigger_signal_webhook(
        current_time=current_time,
        symbol="TQQQ",
        signal_type="TAKE_PROFIT",
        market_data={"price": 46.20, "rsi": 72.0},
        trigger_conditions={
            "rsi_overbought": True,
            "profit_pct": 0.015
        }
    )
    
    if sell_event:
        print(f"✓ SELL signal webhook: {sell_event.trigger_reason}")
    
    summary = simulator.get_summary()
    signal_count = summary['by_type'].get('signal', 0)
    
    print(f"\nExpected: 2 signal webhooks")
    print(f"Actual: {signal_count} signal webhooks")
    print(f"Status: {'✓ PASS' if signal_count == 2 else '✗ FAIL'}")
    
    return signal_count == 2


def test_alert_webhooks():
    """Test alert webhook triggers (stop loss)"""
    print("\n" + "=" * 60)
    print("TEST 3: Alert Webhooks (Stop Loss / Alerts)")
    print("=" * 60)
    
    simulator = WebhookSimulator(
        interval_minutes=5
    )
    
    current_time = datetime(2024, 6, 15, 11, 20, 0)
    
    # Trigger stop loss alert
    stop_loss_event = simulator.trigger_alert_webhook(
        current_time=current_time,
        symbol="TQQQ",
        alert_type="STOP_LOSS",
        market_data={"price": 44.60, "rsi": 25.0},
        alert_message="Stop loss triggered at -2.00%"
    )
    
    if stop_loss_event:
        print(f"✓ Stop loss alert: {stop_loss_event.trigger_reason}")
    
    # Trigger take profit alert
    current_time += timedelta(minutes=5)
    tp_event = simulator.trigger_alert_webhook(
        current_time=current_time,
        symbol="TQQQ",
        alert_type="TAKE_PROFIT",
        market_data={"price": 47.00, "rsi": 75.0},
        alert_message="Take profit target reached at +3.00%"
    )
    
    if tp_event:
        print(f"✓ Take profit alert: {tp_event.trigger_reason}")
    
    summary = simulator.get_summary()
    alert_count = summary['by_type'].get('alert', 0)
    
    print(f"\nExpected: 2 alert webhooks")
    print(f"Actual: {alert_count} alert webhooks")
    print(f"Status: {'✓ PASS' if alert_count == 2 else '✗ FAIL'}")
    
    return alert_count == 2


def test_trading_hours():
    """Test that webhooks only fire during trading hours"""
    print("\n" + "=" * 60)
    print("TEST 4: Trading Hours Enforcement")
    print("=" * 60)
    
    simulator = WebhookSimulator(
        interval_minutes=5,
        trading_hours=(time(9, 30), time(16, 0))
    )
    
    market_data = {"price": 45.50, "rsi": 35.0}
    
    # Before market open (9:00 AM)
    before_open = datetime(2024, 6, 15, 9, 0, 0)
    event1 = simulator.trigger_scheduled_webhook(
        before_open, "TQQQ", market_data
    )
    print(f"Before open (9:00 AM): {'✗ Fired (BAD)' if event1 else '✓ No webhook (GOOD)'}")
    
    # During trading hours (10:00 AM)
    during_hours = datetime(2024, 6, 15, 10, 0, 0)
    event2 = simulator.trigger_scheduled_webhook(
        during_hours, "TQQQ", market_data
    )
    print(f"During hours (10:00 AM): {'✓ Fired (GOOD)' if event2 else '✗ No webhook (BAD)'}")
    
    # After market close (5:00 PM)
    after_close = datetime(2024, 6, 15, 17, 0, 0)
    event3 = simulator.trigger_scheduled_webhook(
        after_close, "TQQQ", market_data
    )
    print(f"After close (5:00 PM): {'✗ Fired (BAD)' if event3 else '✓ No webhook (GOOD)'}")
    
    summary = simulator.get_summary()
    total = summary['total_webhooks']
    
    print(f"\nExpected: 1 webhook (only during hours)")
    print(f"Actual: {total} webhooks")
    print(f"Status: {'✓ PASS' if total == 1 else '✗ FAIL'}")
    
    return total == 1


def test_webhook_summary():
    """Test webhook summary generation"""
    print("\n" + "=" * 60)
    print("TEST 5: Webhook Summary")
    print("=" * 60)
    
    simulator = WebhookSimulator(interval_minutes=5)
    
    # Generate various webhook types
    current_time = datetime(2024, 6, 15, 10, 0, 0)
    market_data = {"price": 45.50, "rsi": 35.0}
    
    # 3 scheduled webhooks
    for i in range(3):
        simulator.trigger_scheduled_webhook(
            current_time + timedelta(minutes=i*5),
            "TQQQ",
            market_data
        )
    
    # 2 signal webhooks
    simulator.trigger_signal_webhook(
        current_time, "TQQQ", "BUY", market_data, {}
    )
    simulator.trigger_signal_webhook(
        current_time, "TQQQ", "SELL", market_data, {}
    )
    
    # 1 alert webhook
    simulator.trigger_alert_webhook(
        current_time, "TQQQ", "STOP_LOSS", market_data, "Stop loss hit"
    )
    
    # Get summary
    summary = simulator.get_summary()
    
    print(f"Total webhooks: {summary['total_webhooks']}")
    print(f"Scheduled: {summary['by_type'].get('scheduled', 0)}")
    print(f"Signals: {summary['by_type'].get('signal', 0)}")
    print(f"Alerts: {summary['by_type'].get('alert', 0)}")
    print(f"Interval: {summary['interval_minutes']} minutes")
    print(f"Trading hours: {summary['trading_hours']}")
    
    expected_total = 6  # 3 scheduled + 2 signal + 1 alert
    success = summary['total_webhooks'] == expected_total
    
    print(f"\nStatus: {'✓ PASS' if success else '✗ FAIL'}")
    
    return success


def main():
    """Run all webhook simulator tests"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "WEBHOOK SIMULATOR TEST SUITE" + " " * 20 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    tests = [
        ("Scheduled Webhooks", test_scheduled_webhooks),
        ("Signal Webhooks", test_signal_webhooks),
        ("Alert Webhooks", test_alert_webhooks),
        ("Trading Hours", test_trading_hours),
        ("Webhook Summary", test_webhook_summary),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n✗ ERROR in {test_name}: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print("\n" + "=" * 60)
    print(f"Total: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("✓ ALL TESTS PASSED - Webhook simulator ready for use!")
        return 0
    else:
        print("✗ SOME TESTS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    exit(main())
