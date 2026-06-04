import os
import sys
import sqlite3
import json
from datetime import datetime

# Add backend and root directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
import app as valkyrie_app
import database as db

def print_section(title):
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def main():
    db_path = valkyrie_app.DB_PATH
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

    results = {}

    # ==========================================================================
    # Verification 1 — Session Lifecycle Stress Test
    # ==========================================================================
    print_section("VERIFICATION 1: Session Lifecycle Stress Test (20 Iterations)")
    v1_passed = True
    
    with TestClient(valkyrie_app.app) as client:
        # Loop 20 times: Deploy -> Stop -> Deploy
        for i in range(20):
            print(f"  [+] Iteration {i+1}/20: Deploying strategy...")
            resp = client.post("/start", json=payload)
            if resp.status_code != 200:
                print(f"      [-] Start failed: {resp.text}")
                v1_passed = False
                break
                
            print(f"  [+] Iteration {i+1}/20: Stopping strategy...")
            resp = client.post("/stop")
            if resp.status_code != 200:
                print(f"      [-] Stop failed: {resp.text}")
                v1_passed = False
                break
        
        # Deploy one last time to end with an active session
        print("  [+] Final strategy deployment to leave session ACTIVE...")
        client.post("/start", json=payload)
        
    # Check DB
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, started_at, ended_at FROM trade_sessions ORDER BY id DESC LIMIT 5")
    recent_sessions = cursor.fetchall()
    
    print("\n  [+] Recent Sessions Table State:")
    print("  {:<5} | {:<10} | {:<25} | {:<25}".format("ID", "Status", "Started At", "Ended At"))
    print("  " + "-"*75)
    for s in recent_sessions:
        print("  {:<5} | {:<10} | {:<25} | {:<25}".format(s["id"], s["status"], str(s["started_at"]), str(s["ended_at"])))
        
    cursor.execute("SELECT COUNT(*) FROM trade_sessions WHERE status='ACTIVE'")
    active_count = cursor.fetchone()[0]
    print(f"\n  [+] Active Sessions Count in DB: {active_count}")
    
    if active_count == 1 and v1_passed:
        results["Verification 1: Session Lifecycle Stress Test"] = "PASS"
    else:
        results["Verification 1: Session Lifecycle Stress Test"] = "FAIL"

    # ==========================================================================
    # Verification 2 — Refresh Recovery
    # ==========================================================================
    print_section("VERIFICATION 2: Refresh Recovery")
    
    with TestClient(valkyrie_app.app) as client:
        # Re-start to ensure we have an active session
        valkyrie_app.SYSTEM_STATUS["state"] = "IDLE"
        client.post("/start", json=payload)
        
        # Re-query session list multiple times to simulate reload/tabs
        print("  [+] Simulating Tab 1 loading sessions...")
        client.get("/api/v2/paper/sessions")
        print("  [+] Simulating Tab 2 loading sessions...")
        client.get("/api/v2/paper/sessions")
        print("  [+] Simulating Tab 3 loading sessions...")
        client.get("/api/v2/paper/sessions")
        
        # Verify no duplicate sessions created (must query while client is active)
        cursor.execute("SELECT COUNT(*) FROM trade_sessions WHERE status='ACTIVE'")
        active_count_post = cursor.fetchone()[0]
        print(f"  [+] Active Sessions Count post-refresh: {active_count_post}")
        
        # Stop session
        client.post("/stop")
        
    if active_count_post == 1:
        results["Verification 2: Refresh Recovery"] = "PASS"
    else:
        results["Verification 2: Refresh Recovery"] = "FAIL"

    # ==========================================================================
    # Verification 3 — Restart Recovery
    # ==========================================================================
    print_section("VERIFICATION 3: Restart Recovery")
    
    # 1. Start an active session in a client context
    with TestClient(valkyrie_app.app) as client:
        # Re-start to ensure we have an active session
        valkyrie_app.SYSTEM_STATUS["state"] = "IDLE" # Force state reset to allow start
        client.post("/start", json=payload)
        active_sess_id = valkyrie_app.CURRENT_SESSION_ID
        print(f"  [+] Created Active Session ID before restart: {active_sess_id}")
        
    # 2. Simulate Backend Restart (instantiate new TestClient context and trigger startup events)
    print("  [+] Simulating backend restart / starting new server instance...")
    with TestClient(valkyrie_app.app) as client_new:
        # Reconnect frontend (query API /api/v2/paper/sessions)
        api_sess_resp = client_new.get("/api/v2/paper/sessions")
        api_sessions = api_sess_resp.json()
        
    # Verify that the session is closed and marked COMPLETED during startup recovery
    cursor.execute("SELECT status, ended_at FROM trade_sessions WHERE id = ?", (active_sess_id,))
    db_sess_state = cursor.fetchone()
    print(f"  [+] Database State for Session {active_sess_id} after restart: Status={db_sess_state['status']}, Ended At={db_sess_state['ended_at']}")
    
    # Verify no new active session was spawned
    cursor.execute("SELECT COUNT(*) FROM trade_sessions WHERE status='ACTIVE'")
    active_count_post_restart = cursor.fetchone()[0]
    print(f"  [+] Active Sessions Count post-restart: {active_count_post_restart}")
    
    if db_sess_state['status'] == "COMPLETED" and active_count_post_restart == 0:
        results["Verification 3: Restart Recovery"] = "PASS"
    else:
        results["Verification 3: Restart Recovery"] = "FAIL"

    # ==========================================================================
    # Verification 4 — Journal Consistency
    # ==========================================================================
    print_section("VERIFICATION 4: Journal Consistency")
    
    # Start a fresh session to have a consistent record
    with TestClient(valkyrie_app.app) as client:
        valkyrie_app.SYSTEM_STATUS["state"] = "IDLE"
        client.post("/start", json=payload)
        curr_session_id = valkyrie_app.CURRENT_SESSION_ID
        client.post("/stop")
        
        # Query API
        api_sess_resp = client.get("/api/v2/paper/sessions")
        api_session_list = api_sess_resp.json()
        api_sess = next((s for s in api_session_list if s["id"] == curr_session_id), None)
        
    # Query DB
    cursor.execute("SELECT * FROM trade_sessions WHERE id = ?", (curr_session_id,))
    db_sess = cursor.fetchone()
    
    print("\n  [+] API Session Fields:")
    print(f"      ID: {api_sess['id']}")
    print(f"      Status: {api_sess['status']}")
    print(f"      Initial Balance: {api_sess['initial_balance']}")
    print(f"      Final Balance: {api_sess['final_balance']}")
    print(f"      PnL: {api_sess['pnl']}")
    
    print("\n  [+] Database Session Fields:")
    print(f"      ID: {db_sess['id']}")
    print(f"      Status: {db_sess['status']}")
    print(f"      Initial Balance: {db_sess['initial_balance']}")
    print(f"      Final Balance: {db_sess['final_balance']}")
    
    if (api_sess and 
        api_sess["id"] == db_sess["id"] and 
        api_sess["status"] == db_sess["status"] and 
        api_sess["initial_balance"] == db_sess["initial_balance"]):
        results["Verification 4: Journal Consistency"] = "PASS"
    else:
        results["Verification 4: Journal Consistency"] = "FAIL"

    # ==========================================================================
    # Verification 5 — Inspector Consistency
    # ==========================================================================
    print_section("VERIFICATION 5: Inspector Consistency")
    
    with TestClient(valkyrie_app.app) as client:
        valkyrie_app.SYSTEM_STATUS["state"] = "IDLE"
        client.post("/start", json=payload)
        inspect_sess_id = valkyrie_app.CURRENT_SESSION_ID
        
        # Place manual buy and sell to have logs
        valkyrie_app.SYSTEM_STATUS["spot_price"] = 340.05
        valkyrie_app.SYSTEM_STATUS["trading_symbol"] = "MIDCPNIFTY 14725 CE 30 JUN 26"
        valkyrie_app.SYSTEM_STATUS["lot_size_multiplier"] = 75
        
        client.post("/manual/buy", json={"qty": 1, "target": 0.0, "target_type": "points", "stop_loss": 0.0, "stop_loss_type": "points", "trailing_gap": 0.0, "is_scalper": False})
        client.post("/manual/panic_exit")
        client.post("/stop")
        
        # Query API
        api_trades_resp = client.get(f"/api/v2/paper/trades?session_id={inspect_sess_id}")
        api_trades = sorted(api_trades_resp.json(), key=lambda x: x["id"])
        
    # Query DB
    cursor.execute("SELECT * FROM trade_logs WHERE session_id = ? ORDER BY id ASC", (inspect_sess_id,))
    db_trades = [dict(r) for r in cursor.fetchall()]
    
    print(f"  [+] API Trades Count: {len(api_trades)} | DB Trades Count: {len(db_trades)}")
    
    v5_match = True
    for a_t, d_t in zip(api_trades, db_trades):
        print(f"      Trade ID {a_t['id']}: API Symbol='{a_t['trading_symbol']}', Type='{a_t['type']}', Price={a_t['price']} | DB Symbol='{d_t['trading_symbol']}', Type='{d_t['type']}', Price={d_t['price']}")
        if (a_t["id"] != d_t["id"] or 
            a_t["trading_symbol"] != d_t["trading_symbol"] or 
            a_t["type"] != d_t["type"] or 
            a_t["price"] != d_t["price"]):
            v5_match = False
            
    if len(api_trades) == len(db_trades) and v5_match:
        results["Verification 5: Inspector Consistency"] = "PASS"
    else:
        results["Verification 5: Inspector Consistency"] = "FAIL"

    # ==========================================================================
    # Verification 6 — CSV Integrity
    # ==========================================================================
    print_section("VERIFICATION 6: CSV Integrity")
    
    with TestClient(valkyrie_app.app) as client:
        # Fetch Exported CSV
        export_resp = client.get(f"/api/v2/paper/export?session_id={inspect_sess_id}")
        csv_text = export_resp.text
        
    import csv
    import io
    reader = csv.reader(io.StringIO(csv_text))
    headers = next(reader)
    csv_rows = list(reader)
    
    print(f"  [+] Exported CSV Headers: {headers}")
    print(f"  [+] Exported CSV Rows count: {len(csv_rows)}")
    
    v6_match = True
    # Compare each row to db logs
    # Note: CSV groups entry and exit into single row
    if len(csv_rows) == 1:
        row = csv_rows[0]
        # entry_price is index 3, exit_price is index 4, pnl is index 6
        db_buy_price = db_trades[0]["price"]
        db_exit_price = db_trades[1]["price"]
        db_exit_pnl = round(db_trades[1]["pnl"], 2)
        
        print(f"      CSV paired row: Symbol='{row[2]}', Entry={row[3]}, Exit={row[4]}, PnL={row[6]}")
        print(f"      DB actual log:  Symbol='{db_trades[0]['trading_symbol']}', Entry={db_buy_price}, Exit={db_exit_price}, PnL={db_exit_pnl}")
        
        if (float(row[3]) != float(db_buy_price) or 
            float(row[4]) != float(db_exit_price) or 
            float(row[6]) != float(db_exit_pnl)):
            v6_match = False
    else:
        v6_match = False
        
    if v6_match:
        results["Verification 6: CSV Integrity"] = "PASS"
    else:
        results["Verification 6: CSV Integrity"] = "FAIL"

    # ==========================================================================
    # Verification 7 — Panic Exit Regression (10 Iterations)
    # ==========================================================================
    print_section("VERIFICATION 7: Panic Exit Regression (10 Iterations)")
    
    v7_all_pass = True
    panic_exit_prices = []
    
    with TestClient(valkyrie_app.app) as client:
        for i in range(10):
            valkyrie_app.SYSTEM_STATUS["state"] = "IDLE"
            client.post("/start", json=payload)
            sess_id = valkyrie_app.CURRENT_SESSION_ID
            
            # Setup buy
            valkyrie_app.SYSTEM_STATUS["spot_price"] = 340.05
            valkyrie_app.SYSTEM_STATUS["trading_symbol"] = "MIDCPNIFTY 14725 CE 30 JUN 26"
            valkyrie_app.SYSTEM_STATUS["lot_size_multiplier"] = 75
            
            client.post("/manual/buy", json={"qty": 1, "target": 0.0, "target_type": "points", "stop_loss": 0.0, "stop_loss_type": "points", "trailing_gap": 0.0, "is_scalper": False})
            
            # Simulate Quote Feed Offline
            valkyrie_app.SYSTEM_STATUS["spot_price"] = 0.0
            
            # Trigger Panic Exit
            client.post("/manual/panic_exit")
            client.post("/stop")
            
            # Query exit price
            cursor.execute("SELECT price FROM trade_logs WHERE session_id = ? AND type = 'EXIT'", (sess_id,))
            exit_price = cursor.fetchone()["price"]
            panic_exit_prices.append(exit_price)
            print(f"      Iteration {i+1}: Exit price logged as ₹{exit_price:.2f}")
            
            if exit_price == 1.0:
                v7_all_pass = False
                
    if v7_all_pass:
        results["Verification 7: Panic Exit Regression"] = "PASS"
    else:
        results["Verification 7: Panic Exit Regression"] = "FAIL"

    # ==========================================================================
    # Verification 8 — Strike Mutation Regression (Multiple Strikes)
    # ==========================================================================
    print_section("VERIFICATION 8: Strike Mutation Regression (Multiple Strikes)")
    
    strikes_to_test = ["14725", "14750", "14800", "14850", "14900"]
    v8_all_pass = True
    
    with TestClient(valkyrie_app.app) as client:
        for strike in strikes_to_test:
            valkyrie_app.SYSTEM_STATUS["state"] = "IDLE"
            # Update start payload strike
            payload["strike"] = strike
            client.post("/start", json=payload)
            sess_id = valkyrie_app.CURRENT_SESSION_ID
            
            # Setup buy
            valkyrie_app.SYSTEM_STATUS["spot_price"] = 340.05
            correct_symbol = f"MIDCPNIFTY {strike} CE 30 JUN 26"
            valkyrie_app.SYSTEM_STATUS["trading_symbol"] = correct_symbol
            valkyrie_app.SYSTEM_STATUS["lot_size_multiplier"] = 75
            
            client.post("/manual/buy", json={"qty": 1, "target": 0.0, "target_type": "points", "stop_loss": 0.0, "stop_loss_type": "points", "trailing_gap": 0.0, "is_scalper": False})
            
            # Mutate global trading symbol to wrong strike to test state leakage
            mutated_symbol = f"MIDCPNIFTY {int(strike)-25} CE 30 JUN 26"
            valkyrie_app.SYSTEM_STATUS["trading_symbol"] = mutated_symbol
            
            # Execute Exit
            client.post("/manual/panic_exit")
            client.post("/stop")
            
            # Query exit symbol
            cursor.execute("SELECT trading_symbol FROM trade_logs WHERE session_id = ? AND type = 'EXIT'", (sess_id,))
            exit_symbol = cursor.fetchone()["trading_symbol"]
            
            print(f"      Strike {strike}: Buy Symbol='{correct_symbol}' | Exit Symbol='{exit_symbol}'")
            if exit_symbol != correct_symbol:
                v8_all_pass = False
                
    if v8_all_pass:
        results["Verification 8: Strike Mutation Regression"] = "PASS"
    else:
        results["Verification 8: Strike Mutation Regression"] = "FAIL"

    conn.close()

    # ==========================================================================
    # Final Summary PASS/FAIL Table
    # ==========================================================================
    print_section("FINAL OFFLINE RUNTIME VALIDATION SUMMARY TABLE")
    print("{:<50} | {:<10}".format("Verification Target", "Result"))
    print("-" * 65)
    for k, v in results.items():
        print("{:<50} | {:<10}".format(k, v))
    print("-" * 65)

if __name__ == "__main__":
    main()
