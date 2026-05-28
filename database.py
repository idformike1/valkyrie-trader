import sqlite3
import os
from datetime import datetime

DEFAULT_DB_PATH = "valkyrie_trades.db"

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
        FOREIGN KEY (session_id) REFERENCES trade_sessions(id)
    )
    """)
    
    conn.commit()
    conn.close()

def create_session(mode, initial_balance, db_path=DEFAULT_DB_PATH):
    init_db(db_path)
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
    cursor.execute(
        "UPDATE trade_sessions SET status = ?, final_balance = ? WHERE id = ?",
        ("COMPLETED", final_balance, session_id)
    )
    conn.commit()
    conn.close()

def log_trade(session_id, instrument_key, trading_symbol, trade_type, price, quantity, stop_loss, target_price, reason, pnl, upstox_order_id=None, timestamp=None, db_path=DEFAULT_DB_PATH):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if not timestamp:
        timestamp = datetime.now().isoformat()
    elif hasattr(timestamp, 'isoformat'):
        timestamp = timestamp.isoformat()
    else:
        timestamp = str(timestamp)
        
    cursor.execute("""
    INSERT INTO trade_logs (session_id, instrument_key, trading_symbol, type, price, quantity, stop_loss, target_price, reason, pnl, timestamp, upstox_order_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, instrument_key, trading_symbol, trade_type, price, quantity, stop_loss, target_price, reason, pnl, timestamp, upstox_order_id))
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
            "upstox_order_id": r["upstox_order_id"] or ""
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
