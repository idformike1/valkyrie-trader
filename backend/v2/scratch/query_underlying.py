import sqlite3

def main():
    conn = sqlite3.connect("backend/valkyrie_trades.db")
    cursor = conn.cursor()
    
    # Check tables in DB
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("Tables:", [t[0] for t in cursor.fetchall()])
    
    # Query underlying candles around 2026-05-28 11:40 - 11:50
    cursor.execute("""
        SELECT timestamp, open, high, low, close 
        FROM underlying_candles 
        WHERE timestamp LIKE '2026-05-28%' 
        ORDER BY timestamp 
        LIMIT 30
    """)
    rows = cursor.fetchall()
    print("\nUnderlying Candles (Spot):")
    for r in rows:
        print(r)
        
    # Check if there are option candles for MIDCPNIFTY
    cursor.execute("SELECT DISTINCT instrument_key FROM option_candles")
    keys = cursor.fetchall()
    print("\nOption candle keys:", keys)

if __name__ == '__main__':
    main()
