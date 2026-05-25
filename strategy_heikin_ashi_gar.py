import pandas as pd
import numpy as np
from datetime import datetime

def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    ha_df = pd.DataFrame(index=df.index)
    ha_df['timestamp'] = df['timestamp'] if 'timestamp' in df.columns else df.index
    
    ha_df['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4.0
    
    ha_opens = np.zeros(len(df))
    ha_opens[0] = df['open'].iloc[0]
    for i in range(1, len(df)):
        ha_opens[i] = (ha_opens[i-1] + ha_df['close'].iloc[i-1]) / 2.0
    ha_df['open'] = ha_opens
    
    ha_df['high'] = np.maximum.reduce([df['high'].values, ha_df['open'].values, ha_df['close'].values])
    ha_df['low'] = np.minimum.reduce([df['low'].values, ha_df['open'].values, ha_df['close'].values])
    ha_df['raw_open'] = df['open']
    return ha_df

class HeikinAshiGarStrategy:
    def __init__(self, candle_limit: int = 10, cut_off_time: str = "14:00"):
        self.candle_limit = candle_limit
        self.cut_off_time = datetime.strptime(cut_off_time, "%H:%M").time()
        self.reset_state()
        
    def reset_state(self):
        self.is_holding = False
        self.entry_price = 0.0
        self.stop_loss_level = 0.0
        self.candles_held = 0
        self.entry_timestamp = None

    def evaluate(self, raw_df: pd.DataFrame) -> tuple:
        if len(raw_df) < 3:
            return "HOLD", {}
            
        ha_df = calculate_heikin_ashi(raw_df)
        candle_prior = ha_df.iloc[-3]     # Candle [-2]
        candle_completed = ha_df.iloc[-2] # Candle [-1]
        current_tick = raw_df.iloc[-1]    # Current Live Ticks
        
        tick_time_str = str(current_tick['timestamp']).split()[-1][:5]
        current_time = datetime.strptime(tick_time_str, "%H:%M").time()
        
        # EXITS
        if self.is_holding:
            self.candles_held += 1
            if current_tick['close'] <= self.stop_loss_level:
                self.reset_state()
                return "EXIT", {"reason": "STOP_LOSS", "price": current_tick['close']}
            if current_time >= self.cut_off_time:
                self.reset_state()
                return "EXIT", {"reason": "SESSION_END", "price": current_tick['close']}
            if self.candles_held >= self.candle_limit:
                self.reset_state()
                return "EXIT", {"reason": "MAX_DURATION", "price": current_tick['close']}
            if candle_completed['close'] < candle_completed['open']:
                self.reset_state()
                return "EXIT", {"reason": "TECHNICAL_REVERSAL", "price": current_tick['close']}
            return "HOLD", {}
            
        # ENTRIES
        else:
            prior_is_red = candle_prior['close'] < candle_prior['open']
            completed_is_green = candle_completed['close'] > candle_completed['open']
            is_strong_green = abs(candle_completed['open'] - candle_completed['low']) <= 0.05
            
            if current_time >= self.cut_off_time:
                return "HOLD", {}
                
            if prior_is_red and completed_is_green and is_strong_green:
                self.is_holding = True
                self.entry_price = current_tick['close']
                self.stop_loss_level = candle_prior['raw_open'] # Fixed structural anchoring
                self.candles_held = 0
                self.entry_timestamp = current_tick['timestamp']
                return "BUY", {"entry_price": self.entry_price, "stop_loss": self.stop_loss_level, "timestamp": self.entry_timestamp}
                
        return "HOLD", {}
