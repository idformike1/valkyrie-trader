import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from v2.trade_explainer import TradeExplainer
import database as db

def main():
    print("Testing Trade Explainer...")
    entry_reason = TradeExplainer.explain_entry(
        strategy_name="Five EMA Aggressive",
        prev_ema=23291.5,
        curr_ema=23314.2,
        spot_price=23315.0,
        condition="Bullish Breakout"
    )
    print(f"Generated Entry Reason:\n{entry_reason}\n")

    exit_reason = TradeExplainer.explain_exit(
        reason_type="Target Hit",
        entry_premium=102.5,
        exit_premium=150.0
    )
    print(f"Generated Exit Reason:\n{exit_reason}\n")

    print("Testing Database Migrations and Log/Get Trades...")
    DB_PATH = "test_transparency_temp.db"
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Initialize DB (creates table & runs migrations)
    db.init_db(DB_PATH)

    quote_quality = {
        "bid": 102.0,
        "ask": 102.5,
        "spread": 0.5,
        "tick_age_ms": 18
    }

    fill_diagnostics = {
        "fill_price": 102.5,
        "quantity": 75,
        "premium": 7687.5,
        "brokerage": 20.0,
        "slippage_pct": 0.05,
        "execution_latency_ms": 12
    }

    # Log BUY trade
    db.log_trade(
        session_id=999,
        instrument_key="NIFTY26JUN23300CE",
        trading_symbol="NIFTY 23300 CE",
        trade_type="BUY",
        price=102.5,
        quantity=75,
        stop_loss=80.0,
        target_price=150.0,
        reason=entry_reason,
        pnl=0.0,
        execution_source="LIVE_QUOTE",
        entry_reason=entry_reason,
        quote_quality=quote_quality,
        fill_diagnostics=fill_diagnostics,
        db_path=DB_PATH
    )

    # Log EXIT trade
    db.log_trade(
        session_id=999,
        instrument_key="NIFTY26JUN23300CE",
        trading_symbol="NIFTY 23300 CE",
        trade_type="EXIT",
        price=150.0,
        quantity=75,
        stop_loss=80.0,
        target_price=150.0,
        reason=exit_reason,
        pnl=3562.5, # (150.0 - 102.5) * 75
        execution_source="LIVE_QUOTE",
        exit_reason=exit_reason,
        quote_quality=quote_quality,
        fill_diagnostics=fill_diagnostics,
        db_path=DB_PATH
    )

    # Fetch trades
    trades = db.get_session_trades(999, DB_PATH)
    print(f"Retrieved {len(trades)} trades:")
    for t in trades:
        print(f"Trade type: {t['type']}, Source: {t['execution_source']}")
        print(f"  Entry Reason: {t.get('entry_reason')}")
        print(f"  Exit Reason: {t.get('exit_reason')}")
        print(f"  Quote Quality: {t.get('quote_quality')}")
        print(f"  Fill Diagnostics: {t.get('fill_diagnostics')}")
        print("-" * 50)

    # Clean up
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    print("Test passed successfully!")

if __name__ == "__main__":
    main()
