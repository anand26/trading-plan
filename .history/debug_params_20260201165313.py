"""Check what's stored in ParametersJson field"""
import pyodbc
import json

try:
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost;'
        'DATABASE=TradingDB;'
        'Trusted_Connection=yes;'
    )
    
    cursor = conn.cursor()
    
    # Get the latest backtest result to examine
    cursor.execute("""
        SELECT TOP 1 
            b.BacktestId,
            b.ParametersJson,
            JSON_VALUE(b.ParametersJson, '$.rsi_period') as rsi_period_raw,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.rsi_period') AS INT) as rsi_period_int,
            JSON_VALUE(b.ParametersJson, '$.bb_period') as bb_period_raw,
            TRY_CAST(JSON_VALUE(b.ParametersJson, '$.bb_period') AS INT) as bb_period_int
        FROM BacktestOutcomes b
        ORDER BY b.OutcomeId DESC
    """)
    
    result = cursor.fetchone()
    if result:
        print(f"BacktestId: {result[0]}")
        print(f"\nRaw JSON_VALUE results:")
        print(f"rsi_period_raw: {result[2]} (type: {type(result[2])})")
        print(f"rsi_period_int: {result[3]} (type: {type(result[3])})")
        print(f"bb_period_raw: {result[4]} (type: {type(result[4])})")
        print(f"bb_period_int: {result[5]} (type: {type(result[5])})")
    else:
        print("No backtest results found")
    
    conn.close()
    
except Exception as e:
    print(f"Database error: {e}")