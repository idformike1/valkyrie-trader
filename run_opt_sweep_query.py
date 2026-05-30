import os
import sys
import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(ROOT_DIR, "backend"))

from backend.app import run_v2_optimization, V2OptimizationRequest, V2BacktestRequest, V2ParameterRange

def run_opt_query():
    base_config = V2BacktestRequest(
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
    
    opt_req = V2OptimizationRequest(
        base_config=base_config,
        ranges=[
            V2ParameterRange(name="fastEma", type="int", min_val=2.0, max_val=10.0, step=1.0),
            V2ParameterRange(name="slowEma", type="int", min_val=5.0, max_val=20.0, step=1.0)
        ],
        max_workers=4
    )
    
    res = run_v2_optimization(opt_req)
    
    # Save the full optimization result for audit comparison
    with open("optimization_audit_result.json", "w") as f:
        json.dump(res, f, indent=2)
        
    print(f"Total combinations executed: {res['run_info']['executed_combinations']}")
    print("\nTop 5 combinations:")
    for idx, item in enumerate(res['top_10'][:5]):
        p = item['combination']['params']
        print(f"#{idx+1}: Fast={p.get('fastEma')}, Slow={p.get('slowEma')} | Net Profit={item['net_profit']} | Sharpe={item['sharpe_ratio']} | PF={item['profit_factor']} | Score={item['composite_score']}")

if __name__ == "__main__":
    run_opt_query()
