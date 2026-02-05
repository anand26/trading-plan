"""
Manual Webhook Server Test
===========================
Tests the live webhook server by sending actual HTTP requests.
Requires the webhook server to be running on localhost:8080.

Usage:
    python test_webhook_manual.py
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"

def test_health():
    """Test health endpoint"""
    print("\n1. Testing /health endpoint...")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"   Status: {r.status_code}")
        data = r.json()
        print(f"   Alpaca Connected: {data.get('alpaca_connected')}")
        print(f"   Cash: ${data.get('account', {}).get('cash', 0):,.2f}")
        print(f"   Current Position: {data.get('current_position')}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_session_status():
    """Test session status endpoint"""
    print("\n2. Testing /session/status endpoint...")
    try:
        r = requests.get(f"{BASE_URL}/session/status", timeout=5)
        print(f"   Status: {r.status_code}")
        data = r.json()
        print(f"   Session: {data}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_positions():
    """Test positions endpoint"""
    print("\n3. Testing /positions endpoint...")
    try:
        r = requests.get(f"{BASE_URL}/positions", timeout=5)
        print(f"   Status: {r.status_code}")
        data = r.json()
        print(f"   Positions: {data.get('count', 0)}")
        for p in data.get('positions', []):
            print(f"     - {p['symbol']}: {p['qty']} shares, P&L: ${p['unrealized_pl']:.2f}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_webhook_test_endpoint():
    """Test the /webhook/test endpoint (no trade execution)"""
    print("\n4. Testing /webhook/test endpoint (no execution)...")
    payload = {
        "action": "BUY_TQQQ",
        "symbol": "TQQQ",
        "position_size": 0.57,
        "stop_loss_pct": 0.02,
        "zscore": -2.0,
        "price": 50.00,
        "ratio": 0.70
    }
    try:
        r = requests.post(f"{BASE_URL}/webhook/test", json=payload, timeout=5)
        print(f"   Status: {r.status_code}")
        data = r.json()
        print(f"   Response: {data.get('status')} - {data.get('message')}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_db_records():
    """Check database records after tests"""
    print("\n5. Checking database records (requires sqlcmd)...")
    import subprocess
    try:
        result = subprocess.run([
            'sqlcmd', '-S', 'localhost', '-d', 'TradingDB', '-Q',
            """SELECT 'Sessions' as Tbl, COUNT(*) as Cnt FROM Sessions WHERE SessionId LIKE 'WH-%' AND Status='active'
               UNION ALL SELECT 'Recent Trades', COUNT(*) FROM Trades WHERE CreatedAt > DATEADD(hour, -1, GETUTCDATE())
               UNION ALL SELECT 'Recent Orders', COUNT(*) FROM Orders WHERE CreatedAt > DATEADD(hour, -1, GETUTCDATE())
               UNION ALL SELECT 'Today DailyPerf', COUNT(*) FROM DailyPerformance WHERE Date = CAST(GETUTCDATE() AS DATE)"""
        ], capture_output=True, text=True, timeout=10)
        print(result.stdout)
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("WEBHOOK SERVER MANUAL TEST")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {BASE_URL}")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Session Status", test_session_status()))
    results.append(("Positions", test_positions()))
    results.append(("Webhook Test Endpoint", test_webhook_test_endpoint()))
    results.append(("Database Records", test_db_records()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n✅ All tests passed! Webhook server is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check if webhook server is running:")
        print("   cd webhooks && python webhook_server.py")

if __name__ == "__main__":
    run_all_tests()
