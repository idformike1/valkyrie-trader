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
    if 'volume' in df.columns:
        ha_df['volume'] = df['volume']
    return ha_df

class Strategy:
    def __init__(self):
        self.is_holding = False
        self.entry_price = 0.0
        self.stop_loss_level = 0.0
        self.target_level = 0.0
        self.candles_held = 0
        self.entry_timestamp = None

    def reset_state(self):
        self.is_holding = False
        self.entry_price = 0.0
        self.stop_loss_level = 0.0
        self.target_level = 0.0
        self.candles_held = 0
        self.entry_timestamp = None

    def evaluate(self, raw_df: pd.DataFrame) -> tuple:
        raise NotImplementedError("Strategies must implement evaluate()")

class HeikinAshiGarStrategy(Strategy):
    def __init__(self, candle_limit: int = 10, cut_off_time: str = "15:15", **kwargs):
        super().__init__()
        self.candle_limit = int(candle_limit)
        self.cut_off_time = datetime.strptime(cut_off_time, "%H:%M").time()

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
                return "EXIT", {"reason": "TECHNICAL_REVERSAL", "price": current_tick['close'], "ha_open": candle_completed['open'], "ha_close": candle_completed['close']}
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
                return "BUY", {
                    "entry_price": self.entry_price,
                    "stop_loss": self.stop_loss_level,
                    "timestamp": self.entry_timestamp,
                    "prior_ha_open": candle_prior['open'],
                    "prior_ha_close": candle_prior['close'],
                    "comp_ha_open": candle_completed['open'],
                    "comp_ha_close": candle_completed['close'],
                    "comp_ha_low": candle_completed['low']
                }
                
        return "HOLD", {}

class FiveEmaScalpingStrategy(Strategy):
    def __init__(self, ema_period: int = 5, rr_ratio: float = 3.0, cut_off_time: str = "15:15", **kwargs):
        super().__init__()
        self.ema_period = int(ema_period)
        self.rr_ratio = float(rr_ratio)
        self.cut_off_time = datetime.strptime(cut_off_time, "%H:%M").time()
        
        # Alert candle tracking
        self.alert_high = 0.0
        self.alert_low = 0.0
        self.alert_time = None
        self.alert_age = 0
        self.last_processed_timestamp = None

    def reset_state(self):
        super().reset_state()
        self.alert_high = 0.0
        self.alert_low = 0.0
        self.alert_time = None
        self.alert_age = 0
        self.last_processed_timestamp = None

    def evaluate(self, raw_df: pd.DataFrame) -> tuple:
        if len(raw_df) < self.ema_period + 2:
            return "HOLD", {}

        # Calculate EMA
        close_prices = raw_df['close']
        ema_series = close_prices.ewm(span=self.ema_period, adjust=False).mean()
        
        # Attach EMA to temporary dataframe copy to safely locate indices
        df = raw_df.copy()
        df['ema'] = ema_series
        
        candle_completed = df.iloc[-2]
        current_tick = df.iloc[-1]
        
        tick_time_str = str(current_tick['timestamp']).split()[-1][:5]
        current_time = datetime.strptime(tick_time_str, "%H:%M").time()
        
        # Track when a new candle closes to increment alert candle age
        if self.last_processed_timestamp != candle_completed['timestamp']:
            self.last_processed_timestamp = candle_completed['timestamp']
            if self.alert_high > 0.0:
                self.alert_age += 1
                if self.alert_age > 3: # Alert candle is valid for 3 candles
                    self.alert_high = 0.0
                    self.alert_low = 0.0
                    self.alert_time = None
                    self.alert_age = 0
            
            # Check if this completed candle is a new Alert Candle (Low is above EMA, wait, for LONG we look for High below EMA, or Low above EMA?
            # Standard 5 EMA is typically SHORT (Selling) when Low is above 5 EMA, and LONG (Buying) when High is below 5 EMA.
            # Since options trading is long-only in this system, if we are trading the option chart directly, we buy when the option chart breaks out.
            # Let's support the LONG setup: Alert candle has High below 5 EMA.
            if candle_completed['high'] < candle_completed['ema']:
                self.alert_high = candle_completed['high']
                self.alert_low = candle_completed['low']
                self.alert_time = candle_completed['timestamp']
                self.alert_age = 0

        # EXITS
        if self.is_holding:
            self.candles_held += 1
            # Stop loss hit
            if current_tick['close'] <= self.stop_loss_level:
                self.reset_state()
                return "EXIT", {"reason": "STOP_LOSS", "price": current_tick['close']}
            # Target hit
            if current_tick['close'] >= self.target_level:
                self.reset_state()
                return "EXIT", {"reason": "TARGET_LIMIT", "price": current_tick['close']}
            # Cutoff hit
            if current_time >= self.cut_off_time:
                self.reset_state()
                return "EXIT", {"reason": "SESSION_END", "price": current_tick['close']}
            return "HOLD", {}

        # ENTRIES
        else:
            if current_time >= self.cut_off_time:
                return "HOLD", {}
                
            # If we have an active alert candle and price crosses above its high
            if self.alert_high > 0.0 and current_tick['close'] > self.alert_high:
                self.is_holding = True
                self.entry_price = current_tick['close']
                self.stop_loss_level = self.alert_low
                
                # Prevent tiny or invalid stop losses
                risk = self.entry_price - self.stop_loss_level
                if risk <= 0.5:
                    risk = 0.5
                    self.stop_loss_level = self.entry_price - risk
                    
                self.target_level = self.entry_price + (risk * self.rr_ratio)
                self.candles_held = 0
                self.entry_timestamp = current_tick['timestamp']
                
                # Clear alert candle
                self.alert_high = 0.0
                self.alert_low = 0.0
                self.alert_time = None
                self.alert_age = 0
                
                return "BUY", {
                    "entry_price": self.entry_price,
                    "stop_loss": self.stop_loss_level,
                    "target_price": self.target_level,
                    "timestamp": self.entry_timestamp
                }

        return "HOLD", {}
