import sqlite3
import os
import sys

# Setup paths to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import database as db

def main():
    print("====================================================")
    print("   TESTING TARGET 1: SESSION CLOSURE INTEGRITY")
    print("====================================================\n")
    
    db_path = "backend/valkyrie_trades.db"
    
    # Clean up any current active sessions first
    db.terminate_active_sessions(db_path)
    
    # 1. Create Session A (which should be ACTIVE)
    print("[1] Creating Session A...")
    session_a_id = db.create_session("PAPER", 100000.0, db_path)
    print(f"  - Created Session A ID: {session_a_id}")
    
    # Verify Session A is ACTIVE
    conn = db.get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM trade_sessions WHERE id = ?", (session_a_id,))
    status_a = cursor.fetchone()[0]
    print(f"  - Session A Status: {status_a}")
    assert status_a == "ACTIVE", f"Expected Session A to be ACTIVE, got {status_a}"
    
    # 2. Create Session B (which should automatically terminate Session A)
    print("\n[2] Creating Session B...")
    session_b_id = db.create_session("PAPER", 100000.0, db_path)
    print(f"  - Created Session B ID: {session_b_id}")
    
    # Verify Session A is now COMPLETED (or terminated status)
    cursor.execute("SELECT status, ended_at, final_balance FROM trade_sessions WHERE id = ?", (session_a_id,))
    row_a = cursor.fetchone()
    print(f"  - Session A Status after B creation: {row_a['status']}")
    print(f"  - Session A End Timestamp: {row_a['ended_at']}")
    print(f"  - Session A Final Balance: {row_a['final_balance']}")
    
    assert row_a['status'] == "COMPLETED", f"Expected Session A to be COMPLETED, got {row_a['status']}"
    assert row_a['ended_at'] is not None, "Expected Session A ended_at to be populated"
    assert row_a['final_balance'] == 100000.0, f"Expected final balance to be 100000.0, got {row_a['final_balance']}"
    
    # Verify Session B is ACTIVE
    cursor.execute("SELECT status FROM trade_sessions WHERE id = ?", (session_b_id,))
    status_b = cursor.fetchone()[0]
    print(f"  - Session B Status: {status_b}")
    assert status_b == "ACTIVE", f"Expected Session B to be ACTIVE, got {status_b}"
    
    # 3. Clean up: terminate active sessions to leave DB clean
    db.terminate_active_sessions(db_path)
    
    # Verify both are now COMPLETED
    cursor.execute("SELECT id, status FROM trade_sessions WHERE id IN (?, ?)", (session_a_id, session_b_id))
    rows = cursor.fetchall()
    for r in rows:
        print(f"  - Session {r['id']} Status: {r['status']}")
        assert r['status'] == "COMPLETED", f"Expected completed, got {r['status']}"
        
    conn.close()
    print("\n====================================================")
    print("      SESSION CLOSURE PASS CRITERIA VERIFIED")
    print("====================================================")

if __name__ == '__main__':
    main()
