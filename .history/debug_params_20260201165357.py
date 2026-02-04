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
            JSON_VALUE(b.ParametersJson, '$.rsi_period') as rsi_period_raw,
            TRY_CAST(CAST(JSON_VALUE(b.ParametersJson, '$.rsi_period') AS FLOAT) AS INT) as rsi_period_fixed,
            JSON_VALUE(b.ParametersJson, '$.bb_period') as bb_period_raw,
            TRY_CAST(CAST(JSON_VALUE(b.ParametersJson, '$.bb_period') AS FLOAT) AS INT) as bb_period_fixed
        FROM BacktestOutcomes b
        ORDER BY b.OutcomeId DESC
    """)
    
    result = cursor.fetchone()
    if result:
        print(f"BacktestId: {result[0]}")
        print(f"\nFixed casting results:")
        print(f"rsi_period_raw: {result[1]} → rsi_period_fixed: {result[2]} (type: {type(result[2])})")
        print(f"bb_period_raw: {result[3]} → bb_period_fixed: {result[4]} (type: {type(result[4])})")
    else:
        print("No backtest results found")
    
    conn.close()
    
except Exception as e:
    print(f"Database error: {e}")