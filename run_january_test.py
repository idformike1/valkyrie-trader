import os
import sys
import json
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(ROOT_DIR, "backend"))

from backend.app import run_v2_backtest, V2BacktestRequest

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def run_query():
    backtest_req = V2BacktestRequest(
        underlying_instrument_key="NSE_INDEX|Nifty 50",
        timeframe="5m",
        start_date="2026-01-01",
        end_date="2026-01-31",
        strategy_name="EMA",
        strategy_params={
            "fastEma": 2,
            "slowEma": 3
        },
        option_type_preference="CE_ONLY",
        strike_mode="ATM",
        expiry_mode="CURRENT_WEEKLY",
        initial_capital=100000.0,
        lot_multiplier=1,
        brokerage_flat=20.0,
        slippage_pct=0.05
    )
    try:
        res = run_v2_backtest(backtest_req)
        print("Success! Results:")
        print(f"Trade Count: {res['report']['trade_stats']['total_trades']}")
        print(f"Net Profit: {res['report']['performance']['net_profit']}")
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_query()
