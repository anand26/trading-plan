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
            JSON_VALUE(b.ParametersJson, '$.rsi_period') as rsi_period_extracted,
            JSON_VALUE(b.ParametersJson, '$.bb_period') as bb_period_extracted
        FROM BacktestOutcomes b
        ORDER BY b.OutcomeId DESC
    """)
    
    result = cursor.fetchone()
    if result:
        print(f"BacktestId: {result[0]}")
        print(f"ParametersJson raw content:")
        print(result[1])
        print(f"\nTrying to parse as JSON:")
        if result[1]:
            try:
                params = json.loads(result[1])
                print(json.dumps(params, indent=2))
                print(f"\nRSI period from dict: {params.get('rsi_period')}")
                print(f"BB period from dict: {params.get('bb_period')}")
            except Exception as e:
                print(f"JSON parse error: {e}")
        
        print(f"\nExtracted via JSON_VALUE:")
        print(f"rsi_period: {result[2]}")
        print(f"bb_period: {result[3]}")
    else:
        print("No backtest results found")
    
    conn.close()
    
except Exception as e:
    print(f"Database error: {e}")