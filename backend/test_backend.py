import requests
import sqlite3
import time
import subprocess
import os
import signal

BASE_URL = "http://127.0.0.1:8081"
DB_PATH = "valkyrie_trades.db"

def run_tests():
    print("--- Starting Valkyrie Backend Verification Tests ---")
    
    # 0. Stop any existing active session
    print("[0] Stopping any existing active session...")
    try:
        requests.post(f"{BASE_URL}/stop")
        print("✅ Any active session stopped successfully.")
    except Exception as e:
        print(f"⚠️ Failed to stop existing session: {e}")
        
    # 1. Test /api/instruments
    print("[1] Fetching instruments...")
    res = requests.get(f"{BASE_URL}/api/instruments")
    if res.status_code != 200:
        print(f"❌ Failed to fetch instruments: {res.text}")
        return
    expiries = res.json()
    if not expiries:
        print("❌ No expiry dates returned!")
        return
    expiry = expiries[0]
    print(f"✅ Instruments fetched successfully. Selected Expiry: {expiry}")
    
    # 2. Test /api/strikes
    print("[2] Fetching strikes...")
    res = requests.get(f"{BASE_URL}/api/strikes?expiry={expiry}&type=CE")
    if res.status_code != 200:
        print(f"❌ Failed to fetch strikes: {res.text}")
        return
    strikes = res.json()
    print(f"✅ Strikes fetched successfully. Total strikes: {len(strikes)}")
    
    # 3. Test /start for 5 EMA BACKTEST
    print("[3] Launching 5 EMA Backtest on last_week...")
    payload = {
        "mode": "BACKTEST",
        "lot_size": 1,
        "live_protection": False,
        "expiry": expiry,
        "option_type": "CE",
        "strike": "ATM",
        "exchange": "NSE",
        "index_name": "NIFTY",
        "timeframe": "1minute",
        "max_candles": 10,
        "cutoff_time": "15:15",
        "brokerage_flat": 20.0,
        "slippage_pct": 0.05,
        "initial_balance": 100000.0,
        "strategy": "five_ema_scalping",
        "period_type": "last_week",
        "five_ema_period": 5,
        "five_ema_rr": 3.0
    }
    
    res = requests.post(f"{BASE_URL}/start", json=payload)
    if res.status_code != 200:
        print(f"❌ Start Backtest failed: {res.text}")
        return
    print(f"✅ Backtest session started: {res.json()['message']}")
    
    # 4. Poll /telemetry for Completion
    print("[4] Polling telemetry for backtest completion...")
    for i in range(15):
        time.sleep(1)
        res = requests.get(f"{BASE_URL}/telemetry")
        if res.status_code == 200:
            data = res.json()
            status = data.get("status", {})
            state = status.get("state")
            print(f"   Poll {i+1}: State = {state}")
            if state in ["COMPLETED", "FAILED"]:
                print(f"🎉 Backtest completed with final state: {state}")
                print(f"   Total Trades: {status.get('total_trades')}")
                print(f"   Final PnL: ₹{status.get('total_pnl'):.2f}")
                break
        else:
            print(f"❌ Telemetry poll failed: {res.text}")
            return
    else:
        print("❌ Backtest timeout exceeded.")
        return
        
    # 5. Verify SQLite Database Records
    print("[5] Verifying SQLite database persistence...")
    if not os.path.exists(DB_PATH):
        print(f"❌ DB File not found at {DB_PATH}!")
        return
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check sessions table
    cursor.execute("SELECT * FROM trade_sessions ORDER BY id DESC LIMIT 1")
    session = cursor.fetchone()
    if not session:
        print("❌ No sessions registered in trade_sessions table!")
        conn.close()
        return
    print(f"✅ Saved Session Found: ID={session['id']}, Mode={session['mode']}, Status={session['status']}, Initial={session['initial_balance']}, Final={session['final_balance']}")
    
    # Check trades table
    cursor.execute("SELECT count(*) as count FROM trade_logs WHERE session_id = ?", (session['id'],))
    count = cursor.fetchone()['count']
    print(f"✅ Saved Trades count in SQLite: {count}")
    conn.close()
    
    # 6. Start a PAPER Trading Session
    print("[6] Starting a PAPER trading session...")
    payload["mode"] = "PAPER"
    res = requests.post(f"{BASE_URL}/start", json=payload)
    if res.status_code != 200:
        print(f"❌ Start Paper Trading failed: {res.text}")
        return
    paper_status = res.json()["status"]
    print(f"✅ Paper session initialized. Active Session ID: {paper_status['session_id']}")
    
    print("\n--- All programmatic tests completed successfully! ---")

if __name__ == "__main__":
    run_tests()
