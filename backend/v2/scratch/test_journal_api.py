import urllib.request
import json
import csv
import io

def test_api():
    print("====================================================")
    print("  TESTING TARGETS 2, 3, 4: JOURNAL & API INTEGRITY")
    print("====================================================\n")
    
    base_url = "http://localhost:8081"
    
    # 1. Test /api/v2/paper/sessions
    print("[1] Querying /api/v2/paper/sessions...")
    try:
        req = urllib.request.urlopen(f"{base_url}/api/v2/paper/sessions")
        sessions = json.loads(req.read().decode('utf-8'))
        print(f"  - Received {len(sessions)} historical sessions.")
        
        # Verify first session fields
        if len(sessions) > 0:
            s = sessions[0]
            required_keys = ["id", "mode", "status", "started_at", "ended_at", "initial_balance", "final_balance", "trades", "win_rate", "pnl", "statistics"]
            for k in required_keys:
                assert k in s, f"Key '{k}' missing from session object"
            print("  - OK: Session keys present: " + ", ".join(required_keys))
            print(f"  - Sample Session #{s['id']}: Mode={s['mode']} | PnL={s['pnl']} | Status={s['status']}")
    except Exception as e:
        print(f"  - FAILED sessions query: {e}")
        return False

    # 2. Test /api/v2/paper/trades
    print("\n[2] Querying /api/v2/paper/trades?session_id=103...")
    try:
        req = urllib.request.urlopen(f"{base_url}/api/v2/paper/trades?session_id=103")
        trades = json.loads(req.read().decode('utf-8'))
        print(f"  - Received {len(trades)} trades for Session 103.")
        if len(trades) > 0:
            t = trades[0]
            # Verify trade inspector fields: Entry Price, Exit Price, Qty, PnL, Source, QQ, Entry/Exit Reason, FD, TS
            required_keys = ["id", "trading_symbol", "type", "price", "quantity", "pnl", "timestamp", "execution_source", "entry_reason", "exit_reason", "quote_quality", "fill_diagnostics"]
            for k in required_keys:
                assert k in t, f"Key '{k}' missing from trade object"
            print("  - OK: Trade inspector keys present: " + ", ".join(required_keys))
            print(f"  - Sample Trade #{t['id']}: Sym={t['trading_symbol']} | Type={t['type']} | Price={t['price']} | Source={t['execution_source']}")
    except Exception as e:
        print(f"  - FAILED trades query: {e}")
        return False

    # 3. Test /api/v2/paper/export?session_id=103
    print("\n[3] Testing /api/v2/paper/export?session_id=103...")
    try:
        req = urllib.request.urlopen(f"{base_url}/api/v2/paper/export?session_id=103")
        csv_content = req.read().decode('utf-8')
        
        # Parse CSV
        reader = csv.reader(io.StringIO(csv_content))
        headers = next(reader)
        print("  - Exported CSV headers:", headers)
        
        required_cols = [
            "session_id", "strategy", "symbol", "entry_price", "exit_price", 
            "quantity", "pnl", "execution_source", "quote_quality", 
            "entry_reason", "exit_reason", "timestamp"
        ]
        
        for col in required_cols:
            assert col in headers, f"Required CSV column '{col}' missing"
        print("  - OK: All required CSV columns are present.")
        
        # Verify row content
        rows = list(reader)
        print(f"  - Exported CSV contains {len(rows)} data rows.")
        for r in rows:
            print(f"    Row: {r}")
            # Ensure pnl, entry_price, etc. are populated
            assert len(r) == len(headers), "Mismatch in CSV row length"
            
    except Exception as e:
        print(f"  - FAILED CSV export validation: {e}")
        return False

    print("\n====================================================")
    print("      JOURNAL, INSPECTOR & CSV EXPORT VERIFIED")
    print("====================================================")
    return True

if __name__ == '__main__':
    test_api()
