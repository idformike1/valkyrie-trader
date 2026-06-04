import sqlite3
from collections import defaultdict

def analyze_db(db_path):
    print(f"\n================ Analyzing: {db_path} ================")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all trades
    cursor.execute("""
        SELECT id, session_id, trading_symbol, type, price, quantity, timestamp, execution_source, reason
        FROM trade_logs
        ORDER BY session_id, timestamp, id
    """)
    trades = cursor.fetchall()
    
    # Group trades by session and symbol
    session_trades = defaultdict(lambda: defaultdict(list))
    for t in trades:
        tid, sid, sym, ttype, price, qty, ts, source, reason = t
        session_trades[sid][sym].append(t)
        
    for sid, sym_dict in session_trades.items():
        for sym, t_list in sym_dict.items():
            # Find BUY and EXIT pairs
            buys = [t for t in t_list if t[3] == 'BUY']
            exits = [t for t in t_list if t[3] == 'EXIT']
            
            # Print if exit price is very low (e.g. <= 5.0) and entry price was high (e.g. >= 100)
            for e in exits:
                e_id, _, _, _, e_price, e_qty, e_ts, e_source, e_reason = e
                # Find the buy trade that occurred before this exit
                matching_buys = [b for b in buys if b[6] < e_ts]
                if matching_buys:
                    # Take the closest buy
                    b = matching_buys[-1]
                    b_id, _, _, _, b_price, b_qty, b_ts, b_source, b_reason = b
                    
                    if e_price <= 5.0 and b_price >= 200.0:
                        print(f"Match found in Session {sid} for {sym}:")
                        print(f"  BUY : ID={b_id} | Price={b_price} | Qty={b_qty} | Time={b_ts} | Source={b_source} | Reason={b_reason}")
                        print(f"  EXIT: ID={e_id} | Price={e_price} | Qty={e_qty} | Time={e_ts} | Source={e_source} | Reason={e_reason}")
                        
                        # Let's query any specific details like quote_quality and fill_diagnostics for these two trades
                        cursor.execute("SELECT quote_quality, fill_diagnostics, execution_source FROM trade_logs WHERE id IN (?, ?)", (b_id, e_id))
                        details = cursor.fetchall()
                        print(f"  Buy Details: QQ={details[0][0]}, FD={details[0][1]}, Src={details[0][2]}")
                        print(f"  Exit Details: QQ={details[1][0]}, FD={details[1][1]}, Src={details[1][2]}")

analyze_db("backend/valkyrie_trades.db")
