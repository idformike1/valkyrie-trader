import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime
from strategy_heikin_ashi_gar import Strategy, HeikinAshiGarStrategy, HeikinAshiGarStrategyV2, FiveEmaScalpingStrategy, OneMinuteTestStrategy, TenSecondTestStrategy

class EmaCrossoverStrategy(Strategy):
    def __init__(self, fast_period: int = 9, slow_period: int = 21, cut_off_time: str = "15:15", **kwargs):
        super().__init__()
        self.fast_period = int(fast_period)
        self.slow_period = int(slow_period)
        self.cut_off_time = datetime.strptime(cut_off_time, "%H:%M").time()
        
    def evaluate(self, raw_df: pd.DataFrame) -> Tuple[str, Dict[str, Any]]:
        if len(raw_df) < self.slow_period + 2:
            return "HOLD", {}
            
        close_prices = raw_df['close']
        fast_ema = close_prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = close_prices.ewm(span=self.slow_period, adjust=False).mean()
        
        prev_fast = fast_ema.iloc[-2]
        prev_slow = slow_ema.iloc[-2]
        curr_fast = fast_ema.iloc[-1]
        curr_slow = slow_ema.iloc[-1]
        
        current_tick = raw_df.iloc[-1]
        
        # Parse timestamp safely
        ts = current_tick['timestamp']
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        else:
            dt = ts
            
        current_time = dt.time()
        
        if self.is_holding:
            # Exit on crossover down or session cutoff
            if curr_fast < curr_slow or current_time >= self.cut_off_time:
                self.reset_state()
                return "EXIT", {"reason": "CROSSOVER_DOWN" if curr_fast < curr_slow else "SESSION_END", "price": float(current_tick['close'])}
            return "HOLD", {}
        else:
            if current_time >= self.cut_off_time:
                return "HOLD", {}
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                self.is_holding = True
                self.entry_price = float(current_tick['close'])
                self.entry_timestamp = ts
                return "BUY", {
                    "entry_price": self.entry_price,
                    "timestamp": self.entry_timestamp,
                    "prev_fast": float(prev_fast),
                    "prev_slow": float(prev_slow),
                    "curr_fast": float(curr_fast),
                    "curr_slow": float(curr_slow)
                }
                
        return "HOLD", {}

class SignalAdapter:
    def __init__(self, strategy_name: str, strategy_params: Dict[str, Any]):
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params
        
        # Normalize name
        name_lower = strategy_name.lower()
        if name_lower in ["heikin_ashi_v2"]:
            self.strategy = HeikinAshiGarStrategyV2(**strategy_params)
        elif name_lower in ["heikin_ashi_gar", "heikin_ashi"]:
            self.strategy = HeikinAshiGarStrategy(**strategy_params)
        elif name_lower in ["five_ema_scalping", "five_ema"]:
            self.strategy = FiveEmaScalpingStrategy(**strategy_params)
        elif name_lower in ["ema_crossover", "ema"]:
            self.strategy = EmaCrossoverStrategy(**strategy_params)
        elif name_lower in ["one_minute_test"]:
            self.strategy = OneMinuteTestStrategy(**strategy_params)
        elif name_lower in ["ten_second_test"]:
            self.strategy = TenSecondTestStrategy(**strategy_params)
        else:
            raise ValueError(f"Unknown strategy name: {strategy_name}")
            
    def reset_state(self):
        self.strategy.reset_state()
            
    def evaluate(self, candles: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        if not candles:
            return "HOLD", {}
            
        df = pd.DataFrame(candles)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            
        action, info = self.strategy.evaluate(df)
        
        # Translate V1 signal (BUY, EXIT, HOLD) to V2 (BUY, SELL, HOLD)
        if action == "BUY":
            return "BUY", info
        elif action in ["EXIT", "SELL"]:
            return "SELL", info
        else:
            return "HOLD", info
