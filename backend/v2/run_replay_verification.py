import sys
import os
from datetime import datetime

# Add parent directory to path to resolve imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig
from v2.types import StrikeMode, ExpiryMode, Timeframe
from v2.replay_engine import HistoricalReplayEngine

def run_verification():
    engine = HistoricalReplayEngine()
    
    # Configure parameters to generate frequent signals for verification density
    config = BacktestConfig(
        underlying_instrument_key="NSE_INDEX|Nifty 50",
        timeframe=Timeframe.MIN_5,
        start_date="2025-04-15",
        end_date="2025-04-15",
        strategy_name="EMA",
        strategy_params={
            "fast_period": 2, 
            "slow_period": 3, 
            "cut_off_time": "15:25"
        },
        option_type_preference="CE_ONLY",
        strike_selection=StrikeConfig(mode=StrikeMode.ATM),
        expiry_selection=ExpiryConfig(mode=ExpiryMode.CURRENT_WEEKLY, roll_threshold_hours=2.0)
    )
    
    print("Running historical replay engine verification...")
    timeline = engine.run(config)
    
    print(f"\nReplay completed. Generated {len(timeline.events)} events.")
    
    print("\n" + "="*90)
    print(f"{'Timestamp':<20} | {'Signal':<11} | {'Spot':<8} | {'Strike':<6} | {'Expiry':<10} | {'Premium':<7} | {'Instrument Key':<25}")
    print("="*90)
    for event in timeline.events:
        ts_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{ts_str:<20} | {event.signal:<11} | {event.spot_price:<8.2f} | {event.strike:<6.1f} | {event.expiry:<10} | {event.premium_price:<7.2f} | {event.instrument_key:<25}")
    print("="*90)
    
    # Save the output to a text file for the report
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verification_timeline_output.txt")
    with open(out_path, "w") as f:
        f.write(f"Generated {len(timeline.events)} events.\n")
        f.write("="*90 + "\n")
        f.write(f"{'Timestamp':<20} | {'Signal':<11} | {'Spot':<8} | {'Strike':<6} | {'Expiry':<10} | {'Premium':<7} | {'Instrument Key':<25}\n")
        f.write("="*90 + "\n")
        for event in timeline.events:
            ts_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{ts_str:<20} | {event.signal:<11} | {event.spot_price:<8.2f} | {event.strike:<6.1f} | {event.expiry:<10} | {event.premium_price:<7.2f} | {event.instrument_key:<25}\n")
        f.write("="*90 + "\n")

if __name__ == "__main__":
    run_verification()
