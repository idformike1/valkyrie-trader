import os
import sys
import sqlite3
import json

# Add backend and v2 directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
import app as valkyrie_app
import database as db

client = TestClient(valkyrie_app.app)

def print_banner(text):
    print("\n" + "="*80)
    print(f" {text}")
    print("="*80)

def main():
    db_path = "backend/valkyrie_trades.db"
    
    # ----------------------------------------------------
    # Verification 1 & 2: Strike Mutation & ₹1 Panic Exit
    # ----------------------------------------------------
    print_banner("1. RUNNING REGRESSION TESTS FOR STRIKE MUTATION & ₹1 PANIC EXIT")
    
    # Initialize session
    payload = {
        "mode": "PAPER",
        "lot_size": 1,
        "live_protection": False,
        "expiry": "2026-06-30",
        "option_type": "CE",
        "strike": "14725",
        "exchange": "NSE",
        "index_name": "MIDCPNIFTY",
        "timeframe": "1minute",
        "max_candles": 10,
        "cutoff_time": "15:15",
        "brokerage_flat": 20.0,
        "slippage_pct": 0.05,
        "initial_balance": 100000.0,
        "strategy": "heikin_ashi_gar"
    }
    
    print("[+] Starting new paper trading session via API /start...")
    resp = client.post("/start", json=payload)
    print(f"    Response Status: {resp.status_code}")
    assert resp.status_code == 200, "Failed to start engine"
    session_id = valkyrie_app.CURRENT_SESSION_ID
    print(f"    Active Session ID: {session_id}")
    
    # Set spot price to non-zero so manual buy succeeds
    valkyrie_app.SYSTEM_STATUS["spot_price"] = 340.05
    valkyrie_app.SYSTEM_STATUS["trading_symbol"] = "MIDCPNIFTY 14725 CE 30 JUN 26"
    valkyrie_app.SYSTEM_STATUS["lot_size_multiplier"] = 75
    
    # Place manual buy
    buy_payload = {
        "qty": 1,
        "target": 0.0,
        "target_type": "points",
        "stop_loss": 0.0,
        "stop_loss_type": "points",
        "trailing_gap": 0.0,
        "is_scalper": False
    }
    print("[+] Executing manual BUY via /manual/buy...")
    resp = client.post("/manual/buy", json=buy_payload)
    print(f"    Response Status: {resp.status_code}")
    assert resp.status_code == 200, "Failed manual buy"
    
    # Simulate Strike Mutation: Mutate the global ATM strike symbol
    print("[+] Simulating Strike Mutation: mutating SYSTEM_STATUS['trading_symbol'] to 14700 CE...")
    valkyrie_app.SYSTEM_STATUS["trading_symbol"] = "MIDCPNIFTY 14700 CE 30 JUN 26"
    
    # Simulate quote feed offline (zero spot price)
    print("[+] Simulating quote feed offline (spot price = 0.0)...")
    valkyrie_app.SYSTEM_STATUS["spot_price"] = 0.0
    
    # Execute panic exit
    print("[+] Executing PANIC EXIT via /manual/panic_exit...")
    resp = client.post("/manual/panic_exit")
    print(f"    Response Status: {resp.status_code}")
    assert resp.status_code == 200, "Failed panic exit"
    
    # Query database for result
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, session_id, trading_symbol, type, price, quantity, pnl, timestamp
        FROM trade_logs 
        WHERE session_id = ?
        ORDER BY id ASC
    """, (session_id,))
    rows = cursor.fetchall()
    
    print("\n[+] Raw Database Output for Trade Logs (Session ID {}):".format(session_id))
    print("{:<5} | {:<10} | {:<30} | {:<6} | {:<8} | {:<8} | {:<10} | {:<25}".format(
        "ID", "Session ID", "Symbol", "Type", "Price", "Qty", "PnL", "Timestamp"
    ))
    print("-" * 115)
    for r in rows:
        print("{:<5} | {:<10} | {:<30} | {:<6} | {:<8.2f} | {:<8} | {:<10.2f} | {:<25}".format(
            r["id"], r["session_id"], r["trading_symbol"], r["type"], r["price"], r["quantity"], r["pnl"], r["timestamp"]
        ))
    
    # Assertions for Verification 1 & 2
    buy_row = rows[0]
    exit_row = rows[1]
    
    print("\n[+] Verification 1 (Strike Mutation) Validation:")
    print(f"    - Entry Symbol: {buy_row['trading_symbol']}")
    print(f"    - Exit Symbol:  {exit_row['trading_symbol']}")
    if buy_row['trading_symbol'] == exit_row['trading_symbol']:
        print("    --> RESULT: PASS (No strike mutation occurred)")
    else:
        print("    --> RESULT: FAIL (Strike mutated!)")
        
    print("\n[+] Verification 2 (₹1 Panic Exit) Validation:")
    print(f"    - Exit Price: ₹{exit_row['price']:.2f}")
    if exit_row['price'] == 340.05:
        print("    --> RESULT: PASS (Fallback to entry price of 340.05 worked correctly instead of ₹1.00)")
    else:
        print("    --> RESULT: FAIL (Exit price fell back to ₹1.00 or incorrect value)")
        
    # ----------------------------------------------------
    # Verification 3: Session Closure Integrity
    # ----------------------------------------------------
    print_banner("2. RUNNING SESSION CLOSURE INTEGRITY TEST")
    
    # Stop Session A first
    print("[+] Stopping Session A via /stop...")
    resp = client.post("/stop")
    print(f"    Response Status: {resp.status_code}")
    
    # Session B start
    print("[+] Starting a second session (Session B) to trigger closure...")
    payload["strike"] = "14750" 
    resp = client.post("/start", json=payload)
    session_b_id = valkyrie_app.CURRENT_SESSION_ID
    print(f"    Session B ID: {session_b_id}")
    
    # Query sessions table
    cursor.execute("""
        SELECT id, status, started_at, ended_at, final_balance
        FROM trade_sessions
        WHERE id IN (?, ?)
        ORDER BY id ASC
    """, (session_id, session_b_id))
    session_rows = cursor.fetchall()
    
    print("\n[+] Raw Database Output for Trade Sessions:")
    print("{:<5} | {:<10} | {:<25} | {:<25} | {:<15}".format(
        "ID", "Status", "Started At", "Ended At", "Final Balance"
    ))
    print("-" * 88)
    for s in session_rows:
        print("{:<5} | {:<10} | {:<25} | {:<25} | {:<15.2f}".format(
            s["id"], s["status"], str(s["started_at"]), str(s["ended_at"]), s["final_balance"] or 0.0
        ))
        
    status_a = session_rows[0]["status"]
    status_b = session_rows[1]["status"]
    
    print("\n[+] Verification 3 Validation:")
    if status_a == "COMPLETED" and status_b == "ACTIVE":
        print("    --> RESULT: PASS (Session A is COMPLETED, Session B is ACTIVE. Exactly one active session.)")
    else:
        print(f"    --> RESULT: FAIL (Session A Status: {status_a}, Session B Status: {status_b})")
        
    # Terminate to leave database clean
    db.terminate_active_sessions(db_path)

    # ----------------------------------------------------
    # Verification 4: Journal Reality Check
    # ----------------------------------------------------
    print_banner("3. RUNNING JOURNAL REALITY CHECK (API VS DATABASE)")
    
    # Fetch via API
    resp = client.get("/api/v2/paper/sessions")
    api_sessions = resp.json()
    
    # Fetch latest session from API
    api_sess = next((s for s in api_sessions if s["id"] == session_id), None)
    
    cursor.execute("SELECT * FROM trade_sessions WHERE id = ?", (session_id,))
    db_sess = cursor.fetchone()
    
    print("\n[+] API Session Details:")
    print(json.dumps(api_sess, indent=4))
    
    print("\n[+] Database Session Details:")
    print(dict(db_sess))
    
    print("\n[+] Verification 4 Validation:")
    assert api_sess is not None
    if (api_sess["id"] == db_sess["id"] and 
        api_sess["status"] == db_sess["status"] and 
        api_sess["initial_balance"] == db_sess["initial_balance"]):
        print("    --> RESULT: PASS (API and Database values match exactly)")
    else:
        print("    --> RESULT: FAIL (Mismatch between API and DB)")
        
    # ----------------------------------------------------
    # Verification 5: CSV Export Reality Check
    # ----------------------------------------------------
    print_banner("4. RUNNING CSV EXPORT REALITY CHECK")
    
    resp = client.get(f"/api/v2/paper/export?session_id={session_id}")
    csv_content = resp.text
    
    print("\n[+] Exported CSV File Contents:")
    print(csv_content)
    
    # Compare against DB row values
    import csv
    import io
    reader = csv.reader(io.StringIO(csv_content))
    headers = next(reader)
    csv_rows = list(reader)
    
    print("[+] Comparing CSV trade rows against DB logs...")
    assert len(csv_rows) == 1, "Expected exactly 1 paired trade row in CSV"
    csv_trade = csv_rows[0]
    
    # Verify values mapping
    print(f"    CSV Trade Row: {csv_trade}")
    print(f"    DB Entry Log Price: {buy_row['price']}")
    print(f"    DB Exit Log Price:  {exit_row['price']}")
    print(f"    DB Exit Log PnL (rounded): {round(exit_row['pnl'], 2)}")
    
    print("\n[+] Verification 5 Validation:")
    if (csv_trade[0] == str(session_id) and 
        float(csv_trade[3]) == float(buy_row['price']) and 
        float(csv_trade[4]) == float(exit_row['price']) and 
        float(csv_trade[6]) == round(exit_row['pnl'], 2)):
        print("    --> RESULT: PASS (CSV Paired columns entry/exit price and pnl match database perfectly)")
    else:
        print("    --> RESULT: FAIL (CSV and DB mismatch)")

    # ----------------------------------------------------
    # Verification 6: Inspector Reality Check
    # ----------------------------------------------------
    print_banner("5. RUNNING INSPECTOR REALITY CHECK (API VS DATABASE)")
    
    resp = client.get(f"/api/v2/paper/trades?session_id={session_id}")
    inspector_trades = sorted(resp.json(), key=lambda x: x["id"])
    
    print("\n[+] Inspector API Trades Response:")
    print(json.dumps(inspector_trades, indent=4))
    
    # Verify inspector trades match DB rows
    db_trade_list = sorted([dict(r) for r in rows], key=lambda x: x["id"])
    print("\n[+] Database Trade Logs List:")
    print(json.dumps(db_trade_list, indent=4))
    
    print("\n[+] Verification 6 Validation:")
    if len(inspector_trades) == len(db_trade_list):
        matches = True
        for i in range(len(inspector_trades)):
            if (inspector_trades[i]["id"] != db_trade_list[i]["id"] or
                inspector_trades[i]["trading_symbol"] != db_trade_list[i]["trading_symbol"] or
                inspector_trades[i]["price"] != db_trade_list[i]["price"] or
                inspector_trades[i]["quantity"] != db_trade_list[i]["quantity"]):
                matches = False
        if matches:
            print("    --> RESULT: PASS (Inspector values exactly match stored database rows)")
        else:
            print("    --> RESULT: FAIL (Mismatch in specific trade fields)")
    else:
        print("    --> RESULT: FAIL (Mismatch in trade list length)")
        
    conn.close()

if __name__ == "__main__":
    main()
