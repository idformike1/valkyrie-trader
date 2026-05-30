import os
import sys
import pandas as pd
from datetime import datetime

# Adjust path to import v2 modules
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/../.."))

from v2.replay_engine import HistoricalReplayEngine
from v2.types import Timeframe
from v2.signal_adapter import SignalAdapter
from v2.strategy_builder import StrategyDefinition, SignalPipeline
from v2.strategy_builder.rule_engine import RuleEngine

def run_diagnostic():
    db_path = os.path.abspath(os.path.dirname(__file__) + "/../../mock_db.db")
    engine = HistoricalReplayEngine(db_path)
    
    start_dt = datetime.strptime("2025-04-15", "%Y-%m-%d")
    end_dt = datetime.strptime("2025-04-20", "%Y-%m-%d")
    raw_candles = engine.spot_loader.load_candles("NIFTY", "1m", start_dt, end_dt)
    from v2.replay_engine import resample_candles
    underlying_candles = resample_candles(raw_candles, "5m")
    
    print(f"Total candles loaded for diagnostic: {len(underlying_candles)}")
    
    complex_strategy_def = StrategyDefinition(**{
        "strategy_id": "complex_ema_rsi_vol",
        "name": "EMA + RSI + Volume Spike",
        "description": "Complex strategy integrating EMA crossovers, RSI boundaries, and Volume spikes.",
        "schema_version": "2.0.0",
        "signal": {
            "indicators": {
                "ema_fast": { "type": "EMA", "params": { "period": 9, "source": "close" } },
                "ema_slow": { "type": "EMA", "params": { "period": 21, "source": "close" } },
                "rsi": { "type": "RSI", "params": { "period": 14, "source": "close" } },
                "vol_ratio": { "type": "volume_spike", "params": { "period": 20 } }
            },
            "entry_condition": {
                "operator": "AND",
                "conditions": [
                    { "type": "greater_than", "params": { "primary": "ema_fast[-1]", "secondary": "ema_slow[-1]" } },
                    { "type": "greater_than", "params": { "primary": "rsi[-1]", "value": 40.0 } },
                    { "type": "greater_than", "params": { "primary": "vol_ratio[-1]", "value": 0.8 } }
                ]
            }
        },
        "contract": {
            "underlying": "NIFTY",
            "instrument_type": "OPTION",
            "option_type": "CE_ONLY",
            "strike": { "mode": "ATM" },
            "expiry": { "mode": "CURRENT_WEEKLY", "roll_threshold_hours": 2.0 }
        },
        "risk": {
            "position_sizing": { "mode": "FIXED_LOTS", "value": 1 },
            "stop_loss": { "type": "percent", "value": 10.0 },
            "take_profit": { "type": "percent", "value": 20.0 },
            "trailing_sl": { "type": "percent", "value": 5.0 }
        },
        "exit": {
            "exit_condition": {
                "type": "less_than",
                "params": { "primary": "ema_fast[-1]", "secondary": "ema_slow[-1]" }
            },
            "exit_on_reversal": False,
            "time_exit": { "cutoff_time": "15:15" }
        }
    })
    
    pipeline = SignalPipeline(complex_strategy_def)
    
    print("\n--- Running Complex Trace ---")
    for i in range(len(underlying_candles)):
        history = underlying_candles[:i+1]
        if len(history) < 25:
            continue
        
        # Calculate manually
        df = pd.DataFrame(history)
        df["ema_fast"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=21, adjust=False).mean()
        
        # Calculate RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).copy()
        loss = (-delta.where(delta < 0, 0)).copy()
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        for idx in range(14, len(df)):
            avg_gain.iloc[idx] = (avg_gain.iloc[idx-1] * 13 + gain.iloc[idx]) / 14
            avg_loss.iloc[idx] = (avg_loss.iloc[idx-1] * 13 + loss.iloc[idx]) / 14
        rs = avg_gain / avg_loss.replace(0, 0.00001)
        df["rsi"] = 100 - (100 / (1 + rs))
        
        # Calculate Vol ratio
        df["vol_ratio"] = df["volume"] / df["volume"].rolling(window=20).mean().replace(0, 1.0)
        
        fast = df["ema_fast"].iloc[-1]
        slow = df["ema_slow"].iloc[-1]
        rsi_val = df["rsi"].iloc[-1]
        vol = df["vol_ratio"].iloc[-1]
        
        cond1 = fast > slow
        cond2 = rsi_val > 40.0
        cond3 = vol > 0.8
        
        if i < 35:
            print(f"[{underlying_candles[i]['timestamp']}] fast: {fast:.2f}, slow: {slow:.2f}, rsi: {rsi_val:.2f}, vol: {vol:.2f} | conds: {cond1}/{cond2}/{cond3}")
        
        if cond1 and cond2 and cond3:
            print(f"[{underlying_candles[i]['timestamp']}] manual match! fast: {fast:.2f}, slow: {slow:.2f}, rsi: {rsi_val:.2f}, vol: {vol:.2f}")
            
        action, info = pipeline.evaluate(history)
        if action == "BUY":
            print(f"[{underlying_candles[i]['timestamp']}] PIPELINE BUY TRIGGERED!")
            
    print("Trace complete.")

if __name__ == "__main__":
    run_diagnostic()

if __name__ == "__main__":
    run_diagnostic()
