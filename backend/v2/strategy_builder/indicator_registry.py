import pandas as pd
import numpy as np
from typing import Dict, Any, Type, Union

class Indicator:
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any], col_name: str) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculates indicator values and returns a Series or a DataFrame.
        """
        raise NotImplementedError()


class EmaIndicator(Indicator):
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any], col_name: str) -> pd.Series:
        period = int(params.get("period", 9))
        source = params.get("source", "close")
        return df[source].ewm(span=period, adjust=False).mean()

class HeikinAshiIndicator(Indicator):
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any], col_name: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        
        ha_df = pd.DataFrame(index=df.index)
        ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4.0
        
        ha_opens = np.zeros(len(df))
        ha_opens[0] = df['open'].iloc[0]
        for i in range(1, len(df)):
            ha_opens[i] = (ha_opens[i-1] + ha_close.iloc[i-1]) / 2.0
            
        ha_high = np.maximum.reduce([df['high'].values, ha_opens, ha_close.values])
        ha_low = np.minimum.reduce([df['low'].values, ha_opens, ha_close.values])
        
        color = np.where(ha_close > ha_opens, "GREEN", "RED")
        
        res = pd.DataFrame(index=df.index)
        res[f"{col_name}_open"] = ha_opens
        res[f"{col_name}_high"] = ha_high
        res[f"{col_name}_low"] = ha_low
        res[f"{col_name}_close"] = ha_close
        res[f"{col_name}_color"] = color
        return res

class RsiIndicator(Indicator):
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any], col_name: str) -> pd.Series:
        period = int(params.get("period", 14))
        source = params.get("source", "close")
        delta = df[source].diff()
        gain = (delta.where(delta > 0, 0)).copy()
        loss = (-delta.where(delta < 0, 0)).copy()
        
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        # Wilder's smoothing
        if len(df) >= period:
            for i in range(period, len(df)):
                avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
                avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
                
        rs = avg_gain / avg_loss.replace(0, 0.00001)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.fillna(50.0)
        return rsi

class MacdIndicator(Indicator):
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any], col_name: str) -> pd.DataFrame:
        fast_period = int(params.get("fast_period", 12))
        slow_period = int(params.get("slow_period", 26))
        signal_period = int(params.get("signal_period", 9))
        source = params.get("source", "close")
        
        fast_ema = df[source].ewm(span=fast_period, adjust=False).mean()
        slow_ema = df[source].ewm(span=slow_period, adjust=False).mean()
        
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        res = pd.DataFrame(index=df.index)
        res[f"{col_name}_macd"] = macd_line
        res[f"{col_name}_signal"] = signal_line
        res[f"{col_name}_hist"] = histogram
        return res

class VolumeSpikeIndicator(Indicator):
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any], col_name: str) -> pd.Series:
        period = int(params.get("period", 20))
        vol_ma = df["volume"].rolling(window=period).mean()
        return df["volume"] / vol_ma.replace(0, 1.0)

class PriceActionIndicator(Indicator):
    def calculate(self, df: pd.DataFrame, params: Dict[str, Any], col_name: str) -> pd.DataFrame:
        res = pd.DataFrame(index=df.index)
        res[f"{col_name}_body"] = (df["close"] - df["open"]).abs()
        res[f"{col_name}_green"] = df["close"] > df["open"]
        res[f"{col_name}_upper_shadow"] = df["high"] - np.maximum(df["close"], df["open"])
        res[f"{col_name}_lower_shadow"] = np.minimum(df["close"], df["open"]) - df["low"]
        return res

class IndicatorRegistry:
    _registry: Dict[str, Type[Indicator]] = {}

    @classmethod
    def register(cls, name: str, indicator_cls: Type[Indicator]):
        cls._registry[name.lower()] = indicator_cls

    @classmethod
    def get(cls, name: str) -> Type[Indicator]:
        name_lower = name.lower()
        if name_lower not in cls._registry:
            raise ValueError(f"Indicator '{name}' is not registered.")
        return cls._registry[name_lower]

# Self-registration
IndicatorRegistry.register("ema", EmaIndicator)
IndicatorRegistry.register("heikin_ashi", HeikinAshiIndicator)
IndicatorRegistry.register("heikinashi", HeikinAshiIndicator)
IndicatorRegistry.register("rsi", RsiIndicator)
IndicatorRegistry.register("macd", MacdIndicator)
IndicatorRegistry.register("volume_spike", VolumeSpikeIndicator)
IndicatorRegistry.register("volume", VolumeSpikeIndicator)
IndicatorRegistry.register("price_action", PriceActionIndicator)
IndicatorRegistry.register("priceaction", PriceActionIndicator)
