import sqlite3

def run_query(db_path):
    print(f"\n================ SQL Query: {db_path} ================")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Let's search for any BUY trades with price near 351-352
    cursor.execute("""
        SELECT id, session_id, trading_symbol, type, price, quantity, pnl, timestamp, reason 
        FROM trade_logs 
        WHERE price BETWEEN 350.0 AND 355.0 AND type='BUY'
    """)
    buys = cursor.fetchall()
    print(f"BUY trades near 351-352: {len(buys)}")
    for b in buys:
        print(f"  {b}")
        
    # Let's search for any EXIT trades with price near 1.0
    cursor.execute("""
        SELECT id, session_id, trading_symbol, type, price, quantity, pnl, timestamp, reason 
        FROM trade_logs 
        WHERE price BETWEEN 0.9 AND 1.2 AND type='EXIT'
    """)
    exits = cursor.fetchall()
    print(f"EXIT trades near 1.0: {len(exits)}")
    for e in exits:
        print(f"  {e}")

run_query("./backend/valkyrie_trades.db")
run_query("./valkyrie_trades.db")
