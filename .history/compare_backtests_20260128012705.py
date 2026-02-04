"""
Simple script to compare backtests using SQL query
"""
import pyodbc
import sys
from tabulate import tabulate

def compare_backtests(session_ids):
    """Compare multiple backtest sessions"""
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost;'
        'DATABASE=TradingDB;'
        'Trusted_Connection=yes'
    )
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(session_ids))
    query = f"""
    SELECT 
        BacktestId,
        TotalReturn,
        SharpeRatio,
        MaxDrawdown,
        WinRate,
        ProfitFactor,
        TotalTrades,
        WinningTrades,
        LosingTrades,
        AverageWin,
        AverageLoss,
        LargestWin,
        LargestLoss
    FROM BacktestOutcomes 
    WHERE BacktestId IN ({placeholders})
    ORDER BY CreatedAt DESC
    """
    
    cursor.execute(query, session_ids)
    columns = [col[0] for col in cursor.description]
    results = cursor.fetchall()
    
    if not results:
        print("No backtests found!")
        return
    
    # Convert to list of dicts for better display
    data = []
    for row in results:
        data.append(dict(zip(columns, row)))
    
    # Print comparison table
    print("\n" + "="*120)
    print("BACKTEST COMPARISON")
    print("="*120 + "\n")
    
    print(tabulate(data, headers="keys", tablefmt="grid", floatfmt=".4f"))
    
    # Print parameter differences
    print("\n" + "="*120)
    print("PARAMETER COMPARISON")
    print("="*120 + "\n")
    
    cursor.execute(f"""
    SELECT BacktestId, CAST(ParametersJson AS VARCHAR(MAX)) AS Parameters
    FROM BacktestOutcomes 
    WHERE BacktestId IN ({placeholders})
    ORDER BY CreatedAt DESC
    """, session_ids)
    
    for row in cursor.fetchall():
        print(f"\n{row[0]}:")
        print(f"  {row[1]}")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compare_backtests.py SESSION_ID1 SESSION_ID2 [SESSION_ID3 ...]")
        print("\nExample:")
        print("  python compare_backtests.py BT_20260128_011523_48e7577a BT_20260128_011028_9975ada7")
        sys.exit(1)
    
    session_ids = sys.argv[1:]
    compare_backtests(session_ids)
