import sys
import os
import time
from datetime import datetime

# Setup paths to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from v2.expired_contract_provider import HistoricalContractProvider
from v2.option_quote_cache import OptionQuoteCache
from v2.paper_execution_adapter import PaperExecutionAdapter

def run_audit():
    print("====================================================")
    print("   FORENSIC AUDIT: VALKYRIE OPTION FILL INTEGRITY")
    print("====================================================\n")

    # Step 1: Initialize historical contract provider & clean up database to test resolution
    provider = HistoricalContractProvider()
    print("[1] Contract Resolution Verification:")
    try:
        resolved_key = provider.resolve_contract("NIFTY", "2026-06-09", 23400.0, "CE")
        print(f"  - Successfully resolved contract: NIFTY 23400 CE (2026-06-09) -> {resolved_key}")
        
        # Verify that it is saved as LEGACY_CSV
        conn = provider._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT source FROM historical_contracts WHERE instrument_key = ?", (resolved_key,))
        source = cursor.fetchone()[0]
        print(f"  - Saved Cache Source in DB: {source}")
        assert source == "LEGACY_CSV", f"Expected LEGACY_CSV but got {source}"
        print("  - OK: Contract Master Cache successfully maps resolved expiries to active keys.")
    except Exception as e:
        print(f"  - FAILED contract resolution: {e}")
        sys.exit(1)

    # Step 2: Initialize Paper Execution Adapter
    adapter = PaperExecutionAdapter(db_path="valkyrie_trades.db")
    print(f"\n[2] Adapter Path Verification:")
    print(f"  - Adapter DB path resolved to absolute path: {adapter.db_path}")
    assert os.path.isabs(adapter.db_path), f"Expected absolute DB path but got {adapter.db_path}"
    print("  - OK: Database path bifurcation resolved.")

    # Step 3: Test Tier 1 - Live Option Quote cache fill
    print(f"\n[3] Tier 1 Execution Source Audit (Live Quote Cache):")
    # Set a valid quote in OptionQuoteCache
    now_ms = int(time.time() * 1000)
    OptionQuoteCache.update(
        instrument_key=resolved_key,
        ltp=150.0,
        bid=149.0,
        ask=151.0,
        volume=1000,
        oi=5000.0,
        timestamp=datetime.now()
    )
    
    # Retrieve and calculate premium (BUY)
    buy_price = adapter.estimate_premium(
        underlying="NIFTY",
        strike=23400.0,
        expiry="2026-06-09",
        option_type="CE",
        spot_price=23420.0,
        timestamp=datetime.now(),
        side="BUY"
    )
    source = adapter._local_state.last_source
    print(f"  - BUY order: Fill Price = {buy_price}, Source = {source}")
    assert buy_price == 151.0, f"Expected ask price 151.0 but got {buy_price}"
    assert source == "LIVE_QUOTE", f"Expected source LIVE_QUOTE but got {source}"

    # Retrieve and calculate premium (SELL)
    sell_price = adapter.estimate_premium(
        underlying="NIFTY",
        strike=23400.0,
        expiry="2026-06-09",
        option_type="CE",
        spot_price=23420.0,
        timestamp=datetime.now(),
        side="SELL"
    )
    source = adapter._local_state.last_source
    print(f"  - SELL order: Fill Price = {sell_price}, Source = {source}")
    assert sell_price == 149.0, f"Expected bid price 149.0 but got {sell_price}"
    assert source == "LIVE_QUOTE", f"Expected source LIVE_QUOTE but got {source}"
    print("  - OK: Live quote consumption verified and prioritized over synthetic models.")

    # Step 4: Test Tier 3 - Fallback to Synthetic Pricing model (when live quote is stale/missing)
    print(f"\n[4] Tier 3 Execution Source Fallback (Stale Quote / Cache Miss):")
    # Clear the quote cache
    OptionQuoteCache.clear()
    
    # Retrieve and calculate premium (should fallback to synthetic analytical pricing)
    fallback_price = adapter.estimate_premium(
        underlying="NIFTY",
        strike=23400.0,
        expiry="2026-06-09",
        option_type="CE",
        spot_price=23420.0,
        timestamp=datetime.now(),
        side="BUY"
    )
    source = adapter._local_state.last_source
    print(f"  - Fallback BUY order: Fill Price = {fallback_price:.2f}, Source = {source}")
    assert source == "SYNTHETIC_MODEL", f"Expected fallback to SYNTHETIC_MODEL but got {source}"
    print("  - OK: Dynamic fallback to SYNTHETIC_MODEL functions correctly when live quotes are missing.")

    print("\n====================================================")
    print("           AUDIT COMPLETED SUCCESSFULLY")
    print("====================================================")

if __name__ == "__main__":
    run_audit()
