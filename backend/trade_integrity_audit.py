import sys
import os
import argparse
import sqlite3
import json
from datetime import datetime

# Add root/backend to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DEFAULT_DB_PATH

def audit_trades(limit=20):
    print("==================================================================================")
    print(f"               VALKYRIE TRADE INTEGRITY AUDIT (Last {limit} Logs)")
    print("==================================================================================\n")
    
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query latest trade logs
    cursor.execute("""
        SELECT * FROM trade_logs 
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    
    if not rows:
        print("No trade logs found in the database.")
        conn.close()
        return
        
    for r in rows:
        log_id = r["id"]
        session_id = r["session_id"]
        inst_key = r["instrument_key"]
        symbol = r["trading_symbol"]
        t_type = r["type"]
        price = r["price"]
        qty = r["quantity"]
        pnl = r["pnl"] if r["pnl"] is not None else 0.0
        ts = r["timestamp"]
        reason = r["reason"] or ""
        exec_source = r["execution_source"] or "SYNTHETIC_MODEL"
        entry_r = r["entry_reason"] or ""
        exit_r = r["exit_reason"] or ""
        
        # Parse JSON columns
        qq = {}
        if r["quote_quality"]:
            try:
                qq = json.loads(r["quote_quality"])
            except Exception:
                pass
                
        fd = {}
        if r["fill_diagnostics"]:
            try:
                fd = json.loads(r["fill_diagnostics"])
            except Exception:
                pass
                
        # Parse Strike/Expiry from symbol or query database
        cursor.execute("SELECT strike, expiry_date, source FROM historical_contracts WHERE instrument_key = ?", (inst_key,))
        contract_info = cursor.fetchone()
        
        strike = contract_info["strike"] if contract_info else "Unknown"
        expiry = contract_info["expiry_date"] if contract_info else "Unknown"
        contract_source = contract_info["source"] if contract_info else "Unknown"
        
        print(f"LOG ID: {log_id} | Session: {session_id} | {ts}")
        print(f"  Symbol: {symbol} | Type: {t_type} | Qty: {qty} | Price: Rs {price:.2f} | PnL: Rs {pnl:.2f}")
        print(f"  Contract: Strike={strike} | Expiry={expiry} | Key={inst_key} | Resolution Source={contract_source}")
        print(f"  Execution Source: {exec_source}")
        print(f"  Reason: {reason} | Entry Reason: {entry_r} | Exit Reason: {exit_r}")
        
        # Quote Quality Audit
        bid = qq.get("bid", 0.0)
        ask = qq.get("ask", 0.0)
        spread = qq.get("spread", 0.0)
        age_ms = qq.get("tick_age_ms", "N/A")
        print(f"  Quote Quality: Bid=Rs {bid:.2f} | Ask=Rs {ask:.2f} | Spread=Rs {spread:.2f} | Age={age_ms}ms")
        
        # Fill Diagnostics
        diagnostics_str = json.dumps(fd) if fd else "None"
        print(f"  Fill Diagnostics: {diagnostics_str}")
        
        # Flag Anomalies
        anomalies = []
        if exec_source == "SYNTHETIC_MODEL":
            anomalies.append("[WARNING] Using SYNTHETIC_MODEL pricing fallback.")
        if contract_source == "FALLBACK_API":
            anomalies.append("[WARNING] Contract key resolved via generated dummy FALLBACK_API.")
        if bid == 0.0 and ask == 0.0 and exec_source == "LIVE_QUOTE":
            anomalies.append("[ERROR] Bid/Ask are zero in live quote fill.")
        if age_ms != "N/A" and isinstance(age_ms, (int, float)) and age_ms > 1500:
            anomalies.append(f"[WARNING] Stale quote tick age: {age_ms}ms (limit is 1500ms).")
        if t_type == "EXIT" and price <= 1.0 and pnl < -100:
            anomalies.append(f"[CRITICAL] Abnormal exit execution: exited at Rs {price:.2f} with PnL Rs {pnl:.2f} (Possible contract rollover / stale quote / zero bid error).")
            
        if anomalies:
            print("  Anomalies Flagged:")
            for a in anomalies:
                print(f"    {a}")
        else:
            print("  Anomalies Flagged: None (Execution Integrity Healthy)")
            
        print("-" * 80)
        
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Valkyrie Trade Integrity Audit CLI Utility")
    parser.add_argument("-n", "--num", type=int, default=20, help="Number of recent trade logs to inspect")
    args = parser.parse_args()
    audit_trades(args.num)
