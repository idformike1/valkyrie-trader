import sqlite3
import os

def check_db(db_path):
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        
        if 'trade_logs' not in tables:
            return
            
        cursor.execute("""
            SELECT id, session_id, instrument_key, trading_symbol, type, price, quantity, pnl, reason, timestamp, execution_source, quote_quality, fill_diagnostics
            FROM trade_logs
        """)
        rows = cursor.fetchall()
        for r in rows:
            # Let's print any trade with price close to 352/351 or exit price around 1
            is_suspicious = False
            # Check for entry price around 351/352
            if r[4] == 'BUY' and (340.0 <= r[5] <= 360.0):
                is_suspicious = True
            # Check for exit price around 1
            if r[4] == 'EXIT' and (0.0 <= r[5] <= 2.0):
                is_suspicious = True
                
            if is_suspicious:
                print(f"[{db_path}] TradeID: {r[0]} | SessionID: {r[1]} | Symbol: {r[4]} {r[3]} | Price: {r[5]} | Qty: {r[6]} | PnL: {r[7]} | Reason: {r[8]} | Time: {r[9]} | Source: {r[10]}")
    except Exception as e:
        print(f"Error checking {db_path}: {e}")

def main():
    db_files = []
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('.db'):
                db_files.append(os.path.join(root, f))
                
    for db in db_files:
        check_db(db)

if __name__ == '__main__':
    main()
