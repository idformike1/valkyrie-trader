import requests
import json

payload = {
    "underlying_instrument_key": "NSE_INDEX|Nifty 50",
    "timeframe": "5m",
    "start_date": "2025-04-15",
    "end_date": "2025-04-15",
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
    "slippage_pct": 0.05
}

print("Sending run backtest request to http://localhost:8081/api/v2/backtest/run...")
response = requests.post("http://localhost:8081/api/v2/backtest/run", json=payload)
print(f"Status Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("Keys in response:", list(data.keys()))
    trades = data.get("trades", [])
    print(f"Total trades returned: {len(trades)}")
    if trades:
        first_trade = trades[0]
        print("\nFirst trade keys:")
        print(list(first_trade.keys()))
        if "explanation" in first_trade:
            print("\nFirst trade explanation:")
            print(json.dumps(first_trade["explanation"], indent=2))
        else:
            print("\nWARNING: 'explanation' not found in trade object!")
else:
    print(response.text)
