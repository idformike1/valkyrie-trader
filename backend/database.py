import sqlite3
import os
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "valkyrie_trades.db")

def get_db_connection(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=DEFAULT_DB_PATH):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Create trade_sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        initial_balance REAL NOT NULL,
        final_balance REAL
    )
    """)
    
    # Create trade_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        instrument_key TEXT NOT NULL,
        trading_symbol TEXT NOT NULL,
        type TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        stop_loss REAL,
        target_price REAL,
        reason TEXT,
        pnl REAL,
        timestamp TEXT NOT NULL,
        upstox_order_id TEXT,
        execution_source TEXT,
        entry_reason TEXT,
        exit_reason TEXT,
        quote_quality TEXT,
        fill_diagnostics TEXT,
        FOREIGN KEY (session_id) REFERENCES trade_sessions(id)
    )
    """)
    
    # Run migrations for execution_source, entry_reason, exit_reason, quote_quality, fill_diagnostics
    for col in ["execution_source", "entry_reason", "exit_reason", "quote_quality", "fill_diagnostics"]:
        try:
            cursor.execute(f"ALTER TABLE trade_logs ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass # already exists
            
    # Run migrations for ended_at and session_statistics in trade_sessions
    for col in ["ended_at", "session_statistics"]:
        try:
            cursor.execute(f"ALTER TABLE trade_sessions ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass # already exists
        
    conn.commit()
    conn.close()

def terminate_active_sessions(db_path=DEFAULT_DB_PATH):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, initial_balance FROM trade_sessions WHERE status = 'ACTIVE'")
    active_rows = cursor.fetchall()
    
    for row in active_rows:
        session_id = row["id"]
        initial_balance = row["initial_balance"]
        
        # Calculate final balance using the sum of trade logs pnl
        cursor.execute("SELECT SUM(pnl) FROM trade_logs WHERE session_id = ?", (session_id,))
        pnl_sum = cursor.fetchone()[0] or 0.0
        final_balance = initial_balance + pnl_sum
        
        # Calculate session statistics
        cursor.execute("SELECT type, pnl FROM trade_logs WHERE session_id = ?", (session_id,))
        trades = cursor.fetchall()
        total_trades = len(trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        import json
        stats = {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(pnl_sum, 2)
        }
        
        now_str = datetime.now().isoformat()
        cursor.execute(
            "UPDATE trade_sessions SET status = ?, final_balance = ?, ended_at = ?, session_statistics = ? WHERE id = ?",
            ("COMPLETED", final_balance, now_str, json.dumps(stats), session_id)
        )
    conn.commit()
    conn.close()

def create_session(mode, initial_balance, db_path=DEFAULT_DB_PATH):
    init_db(db_path)
    terminate_active_sessions(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO trade_sessions (mode, status, started_at, initial_balance) VALUES (?, ?, ?, ?)",
        (mode, "ACTIVE", now_str, initial_balance)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def close_session(session_id, final_balance, db_path=DEFAULT_DB_PATH):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Calculate stats
    cursor.execute("SELECT type, pnl FROM trade_logs WHERE session_id = ?", (session_id,))
    trades = cursor.fetchall()
    total_trades = len(trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    
    # Get total PnL
    cursor.execute("SELECT SUM(pnl) FROM trade_logs WHERE session_id = ?", (session_id,))
    total_pnl = cursor.fetchone()[0] or 0.0
    
    import json
    stats = {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2)
    }
    
    now_str = datetime.now().isoformat()
    cursor.execute(
        "UPDATE trade_sessions SET status = ?, final_balance = ?, ended_at = ?, session_statistics = ? WHERE id = ?",
        ("COMPLETED", final_balance, now_str, json.dumps(stats), session_id)
    )
    conn.commit()
    conn.close()

def log_trade(session_id, instrument_key, trading_symbol, trade_type, price, quantity, stop_loss, target_price, reason, pnl, upstox_order_id=None, timestamp=None, execution_source=None, entry_reason=None, exit_reason=None, quote_quality=None, fill_diagnostics=None, db_path=DEFAULT_DB_PATH):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if not timestamp:
        timestamp = datetime.now().isoformat()
    elif hasattr(timestamp, 'isoformat'):
        timestamp = timestamp.isoformat()
    else:
        timestamp = str(timestamp)
        
    # Serialize to JSON if dict
    import json
    if isinstance(quote_quality, dict):
        quote_quality = json.dumps(quote_quality)
    if isinstance(fill_diagnostics, dict):
        fill_diagnostics = json.dumps(fill_diagnostics)
        
    cursor.execute("""
    INSERT INTO trade_logs (session_id, instrument_key, trading_symbol, type, price, quantity, stop_loss, target_price, reason, pnl, timestamp, upstox_order_id, execution_source, entry_reason, exit_reason, quote_quality, fill_diagnostics)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, instrument_key, trading_symbol, trade_type, price, quantity, stop_loss, target_price, reason, pnl, timestamp, upstox_order_id, execution_source, entry_reason, exit_reason, quote_quality, fill_diagnostics))
    conn.commit()
    conn.close()

def get_session_trades(session_id, db_path=DEFAULT_DB_PATH):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_logs WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    trades = []
    for r in rows:
        # Check if execution_source is present in the database row keys
        exec_src = "SYNTHETIC_MODEL"
        try:
            if "execution_source" in r.keys() and r["execution_source"] is not None:
                exec_src = r["execution_source"]
        except Exception:
            pass
            
        entry_r = None
        try:
            if "entry_reason" in r.keys():
                entry_r = r["entry_reason"]
        except Exception:
            pass
            
        exit_r = None
        try:
            if "exit_reason" in r.keys():
                exit_r = r["exit_reason"]
        except Exception:
            pass
            
        qq = None
        try:
            if "quote_quality" in r.keys() and r["quote_quality"] is not None:
                import json
                qq = json.loads(r["quote_quality"])
        except Exception:
            pass
            
        fd = None
        try:
            if "fill_diagnostics" in r.keys() and r["fill_diagnostics"] is not None:
                import json
                fd = json.loads(r["fill_diagnostics"])
        except Exception:
            pass
            
        trades.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "instrument_key": r["instrument_key"],
            "trading_symbol": r["trading_symbol"],
            "type": r["type"],
            "price": r["price"],
            "quantity": r["quantity"],
            "sl": r["stop_loss"] or 0.0,
            "target": r["target_price"] or 0.0,
            "reason": r["reason"] or "",
            "pnl": r["pnl"] if r["pnl"] is not None else 0.0,
            "timestamp": r["timestamp"],
            "upstox_order_id": r["upstox_order_id"] or "",
            "execution_source": exec_src,
            "entry_reason": entry_r,
            "exit_reason": exit_r,
            "quote_quality": qq,
            "fill_diagnostics": fd
        })
    return trades

def get_session_equity_curve(session_id, initial_balance, db_path=DEFAULT_DB_PATH):
    trades = get_session_trades(session_id, db_path)
    curve = [{"timestamp": datetime.now().isoformat(), "equity": initial_balance}] # Default start point
    balance = initial_balance
    
    # Locate matching BUY and EXIT trades to build equity curve points
    for t in trades:
        if t["type"] == "EXIT":
            balance += t["pnl"]
            curve.append({
                "timestamp": t["timestamp"],
                "equity": balance
            })
    return curve

def get_active_session(db_path=DEFAULT_DB_PATH):
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_sessions WHERE status = 'ACTIVE' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "mode": row["mode"],
            "status": row["status"],
            "started_at": row["started_at"],
            "initial_balance": row["initial_balance"]
        }
    return None

def get_all_sessions(db_path=DEFAULT_DB_PATH):
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_sessions ORDER BY id DESC")
    rows = cursor.fetchall()
    
    import json
    sessions = []
    for r in rows:
        session_id = r["id"]
        cursor.execute("SELECT COUNT(*) FROM trade_logs WHERE session_id = ?", (session_id,))
        trade_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(pnl) FROM trade_logs WHERE session_id = ?", (session_id,))
        pnl_sum = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT pnl FROM trade_logs WHERE session_id = ? AND type = 'EXIT'", (session_id,))
        exit_trades = cursor.fetchall()
        total_exits = len(exit_trades)
        wins = sum(1 for t in exit_trades if t["pnl"] > 0)
        win_rate = (wins / total_exits * 100) if total_exits > 0 else 0.0
        
        stats = {}
        if r["session_statistics"]:
            try:
                stats = json.loads(r["session_statistics"])
            except Exception:
                pass
                
        sessions.append({
            "id": r["id"],
            "mode": r["mode"],
            "status": r["status"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"] or "",
            "initial_balance": r["initial_balance"],
            "final_balance": r["final_balance"] or r["initial_balance"],
            "trades": trade_count,
            "win_rate": round(win_rate, 2),
            "pnl": round(pnl_sum, 2),
            "statistics": stats
        })
    conn.close()
    return sessions

def get_all_trades(db_path=DEFAULT_DB_PATH, session_id=None):
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if session_id:
        cursor.execute("SELECT * FROM trade_logs WHERE session_id = ? ORDER BY id DESC", (session_id,))
    else:
        cursor.execute("SELECT * FROM trade_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    trades = []
    for r in rows:
        exec_src = "SYNTHETIC_MODEL"
        try:
            if "execution_source" in r.keys() and r["execution_source"] is not None:
                exec_src = r["execution_source"]
        except Exception:
            pass
            
        entry_r = None
        try:
            if "entry_reason" in r.keys():
                entry_r = r["entry_reason"]
        except Exception:
            pass
            
        exit_r = None
        try:
            if "exit_reason" in r.keys():
                exit_r = r["exit_reason"]
        except Exception:
            pass
            
        qq = None
        try:
            if "quote_quality" in r.keys() and r["quote_quality"] is not None:
                import json
                qq = json.loads(r["quote_quality"])
        except Exception:
            pass
            
        fd = None
        try:
            if "fill_diagnostics" in r.keys() and r["fill_diagnostics"] is not None:
                import json
                fd = json.loads(r["fill_diagnostics"])
        except Exception:
            pass
            
        trades.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "instrument_key": r["instrument_key"],
            "trading_symbol": r["trading_symbol"],
            "type": r["type"],
            "price": r["price"],
            "quantity": r["quantity"],
            "sl": r["stop_loss"] or 0.0,
            "target": r["target_price"] or 0.0,
            "reason": r["reason"] or "",
            "pnl": r["pnl"] if r["pnl"] is not None else 0.0,
            "timestamp": r["timestamp"],
            "upstox_order_id": r["upstox_order_id"] or "",
            "execution_source": exec_src,
            "entry_reason": entry_r,
            "exit_reason": exit_r,
            "quote_quality": qq,
            "fill_diagnostics": fd
        })
    return trades
