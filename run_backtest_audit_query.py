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
        start_date="2025-04-15",
        end_date="2025-05-14",
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
    res = run_v2_backtest(backtest_req)
    
    # Save the full result for audit comparison
    with open("backtest_audit_result.json", "w") as f:
        json.dump(res, f, indent=2, cls=DateTimeEncoder)
        
    print(f"Trade Count: {res['report']['trade_stats']['total_trades']}")
    print(f"Net Profit: {res['report']['performance']['net_profit']}")
    print(f"Win Rate: {res['report']['trade_stats']['win_rate']}%")
    print(f"Profit Factor: {res['report']['performance']['profit_factor']}")
    print(f"Expectancy: {res['report']['performance']['expectancy']}")
    print(f"Sharpe Ratio: {res['report']['sharpe_ratio']}")
    print(f"Sortino Ratio: {res['report']['sortino_ratio']}")
    print(f"Max Drawdown: {res['report']['max_drawdown']}")
    print(f"Max Drawdown Pct: {res['report']['max_drawdown_pct']}%")

if __name__ == "__main__":
    run_query()
