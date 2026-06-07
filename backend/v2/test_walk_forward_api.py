import urllib.request
import json
import time

api_payload = {
    "underlying_instrument_key": "NSE_INDEX|Nifty 50",
    "timeframe": "5m",
    "start_date": "2025-04-15",
    "end_date": "2025-04-22",
    "strategy_name": "EMA",
    "strategy_params": {
        "fastEma": 2,
        "slowEma": 3,
        "cut_off_time": "15:25"
    },
    "option_type_preference": "CE_ONLY",
    "strike_mode": "ATM",
    "expiry_mode": "CURRENT_WEEKLY",
    "initial_capital": 100000.0,
    "lot_multiplier": 1,
    "brokerage_flat": 20.0,
    "slippage_pct": 0.05,
    "execution_model": "REALISTIC",
    "walk_forward_enabled": True,
    "walk_forward_train_days": 2,
    "walk_forward_test_days": 1,
    "walk_forward_step_days": 1,
    "walk_forward_ranges": [
        {"name": "fastEma", "type": "int", "min_val": 2, "max_val": 4, "step": 2},
        {"name": "slowEma", "type": "int", "min_val": 3, "max_val": 5, "step": 2}
    ]
}

print("Running API validation for Walk Forward testing...")
req_data = json.dumps(api_payload).encode('utf-8')
req = urllib.request.Request("http://localhost:8081/api/v2/backtest/run", data=req_data, headers={"Content-Type": "application/json"})

t0 = time.perf_counter()
try:
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode('utf-8'))
        
    print(f"API response received in {time.perf_counter() - t0:.2f} seconds.")
    if "walk_forward_analysis" in res and res["walk_forward_analysis"] is not None:
        wf = res["walk_forward_analysis"]
        print("PASS: walk_forward_analysis present.")
        print(f"Walk Forward Score: {wf['walk_forward_score']} | Classification: {wf['classification']}")
        print("Stability:", wf["stability"])
        print(f"Windows count: {len(wf['windows'])}")
        for w in wf["windows"]:
            print(f"  Window {w['window_index']}: Train {w['train_start']}->{w['train_end']} (Score: {w['train_robustness_score']}) | Test {w['test_start']}->{w['test_end']} (Score: {w['test_robustness_score']})")
    else:
        print("FAIL: walk_forward_analysis missing or null.")
except Exception as e:
    print("FAIL: Request error:", e)
