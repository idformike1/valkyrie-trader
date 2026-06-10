import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from v2.config import BacktestConfig
from v2.signal_adapter import SignalAdapter
from v2.position_manager import PositionManager
from v2.paper_execution_adapter import PaperExecutionAdapter
from v2.telemetry_logger import TelemetryLogger

logger = logging.getLogger("Valkyrie.RealtimeSignalRunner")

class RealtimeSignalRunner:
    """
    Orchestrator for V2 real-time strategy signal processing and paper execution.
    - Manages rollings completed candle buffer in memory.
    - Performs risk validation audits (SL, Target, cutoff bounds) on active exposures.
    - Runs SignalAdapter models on candle history.
    - Executes BUY/SELL transactions synchronously.
    """
    def __init__(self, config: BacktestConfig, position_manager: PositionManager, db_path: Optional[str] = None, warmup: bool = True):
        self.config = config
        self.position_manager = position_manager
        self.execution_adapter = PaperExecutionAdapter(position_manager, config, db_path)
        
        # Setup strategy pipeline
        self.is_dynamic = False
        self.strategy_def = None
        if getattr(config, "strategy_definition", None) is not None:
            from v2.strategy_builder import StrategyDefinition, SignalPipeline
            self.strategy_def = StrategyDefinition(**config.strategy_definition)
            self.adapter = SignalPipeline(self.strategy_def)
            self.strategy_name = self.strategy_def.name
            self.is_dynamic = True
        else:
            self.adapter = SignalAdapter(config.strategy_name, config.strategy_params)
            self.strategy_name = config.strategy_name
            self.is_dynamic = False

        self.candle_buffer: List[Dict[str, Any]] = []
        self.active_contract: Optional[Dict[str, Any]] = None
        self.entry_index = 0
        self.is_paused = False
        
        # Check if we are running in a unit test environment to prevent real API calls and buffer pollution
        import sys
        is_testing = any(x in sys.modules for x in ["unittest", "pytest", "nose"])
        
        # Warmup the candle buffer to avoid Heikin Ashi cold start issues
        if warmup and not is_testing:
            self._warmup_buffer()

    def _warmup_buffer(self):
        """
        Fetches historical 1-minute candles from the data provider/API,
        interpolates them if the target timeframe is 10s/30s, and seeds
        the rolling candle buffer to avoid cold start issues.
        """
        try:
            logger.info("Initializing candle buffer warmup...")
            underlying = self.config.underlying_instrument_key
            timeframe = self.config.timeframe
            
            # Check if running in mock simulation mode to skip API call and generate synthetic candles
            is_mock = False
            try:
                import app
                if getattr(app, 'current_feed', None) is not None and getattr(app.current_feed, 'is_mock', False):
                    is_mock = True
                elif app.SYSTEM_STATUS.get("use_mock_feed", False):
                    is_mock = True
            except Exception:
                pass
                
            if is_mock:
                logger.info("Generating synthetic historical candles for Mock Mode warmup...")
                count = 60
                now = datetime.now()
                from datetime import timedelta
                delta_sec = 60
                if timeframe == "10s":
                    delta_sec = 10
                elif timeframe == "30s":
                    delta_sec = 30
                elif timeframe == "1m":
                    delta_sec = 60
                elif timeframe == "5m":
                    delta_sec = 300
                elif timeframe == "15m":
                    delta_sec = 900
                
                base_price = 22000.0
                import random
                price = base_price
                warmed_candles = []
                for i in range(count):
                    ts = now - timedelta(seconds=(count - i) * delta_sec)
                    open_p = price
                    close_p = price + random.uniform(-10.0, 10.0)
                    high_p = max(open_p, close_p) + random.uniform(0, 5.0)
                    low_p = min(open_p, close_p) - random.uniform(0, 5.0)
                    price = close_p
                    
                    warmed_candles.append({
                        'timestamp': ts.replace(microsecond=0),
                        'open': round(open_p, 2),
                        'high': round(high_p, 2),
                        'low': round(low_p, 2),
                        'close': round(close_p, 2),
                        'volume': round(random.uniform(100, 1000), 2)
                    })
                self.candle_buffer.extend(warmed_candles)
                logger.info(f"Successfully warmed up candle buffer with {len(self.candle_buffer)} synthetic candles.")
                return

            # Map short name to Upstox instrument key
            underlying_keys_map = {
                "NIFTY": "NSE_INDEX|Nifty 50",
                "BANKNIFTY": "NSE_INDEX|Nifty Bank",
                "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
                "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
                "SENSEX": "BSE_INDEX|SENSEX",
                "BANKEX": "BSE_INDEX|BANKEX"
            }
            instrument_key = underlying_keys_map.get(underlying.upper(), "NSE_INDEX|Nifty 50")
            
            # Load token
            from v2.upstox_expired_loader import load_upstox_token
            import urllib.parse
            import requests
            
            token = load_upstox_token()
            if not token:
                logger.warning("Token missing, skipping warmup.")
                return
                
            encoded_key = urllib.parse.quote(instrument_key)
            headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
            url = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded_key}/1minute"
            
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch historical candles: {resp.status_code}. Seeding skipped.")
                return
                
            data = resp.json()
            candles_raw = data.get('data', {}).get('candles', [])
            if not candles_raw:
                logger.warning("No historical candles found. Seeding skipped.")
                return
                
            # API returns newest first, reverse to chronological
            candles_raw.reverse()
            
            # Parse 1m candles
            candles_1m = []
            for c in candles_raw:
                # Convert to naive local datetime
                ts_aware = datetime.fromisoformat(c[0].replace('Z', '+00:00'))
                ts = ts_aware.astimezone(None).replace(tzinfo=None)
                candles_1m.append({
                    'timestamp': ts,
                    'open': float(c[1]),
                    'high': float(c[2]),
                    'low': float(c[3]),
                    'close': float(c[4]),
                    'volume': float(c[5]) if len(c) > 5 else 0.0
                })
                
            count = 60  # Seed with 60 candles to ensure excellent Heikin Ashi smoothing
            warmed_candles = []
            
            if timeframe not in ["10s", "30s"]:
                if timeframe == "1m":
                    warmed_candles = candles_1m[-count:]
                else:
                    tf_minutes = 5 if timeframe == "5m" else (15 if timeframe == "15m" else 1)
                    import pandas as pd
                    df = pd.DataFrame(candles_1m)
                    df.set_index('timestamp', inplace=True)
                    resampled = df.resample(f"{tf_minutes}min").agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }).dropna()
                    
                    for ts, row in resampled.iterrows():
                        warmed_candles.append({
                            'timestamp': ts.to_pydatetime(),
                            'open': row['open'],
                            'high': row['high'],
                            'low': row['low'],
                            'close': row['close'],
                            'volume': row['volume']
                        })
                    warmed_candles = warmed_candles[-count:]
            else:
                # Sub-minute interpolation
                from datetime import timedelta
                sub_candles = []
                splits = 6 if timeframe == "10s" else 2
                delta_sec = 10 if timeframe == "10s" else 30
                
                for c in candles_1m:
                    o, h, l, cl = c['open'], c['high'], c['low'], c['close']
                    ts = c['timestamp']
                    
                    for step in range(splits):
                        step_ts = ts + timedelta(seconds=step * delta_sec)
                        frac_start = step / splits
                        frac_end = (step + 1) / splits
                        sub_open = o + (cl - o) * frac_start
                        sub_close = o + (cl - o) * frac_end
                        
                        sub_high = max(sub_open, sub_close)
                        sub_low = min(sub_open, sub_close)
                        
                        if step == splits // 2:
                            sub_high = max(sub_high, h)
                            sub_low = min(sub_low, l)
                            
                        sub_candles.append({
                            'timestamp': step_ts,
                            'open': round(sub_open, 2),
                            'high': round(sub_high, 2),
                            'low': round(sub_low, 2),
                            'close': round(sub_close, 2),
                            'volume': round(c['volume'] / splits, 2)
                        })
                warmed_candles = sub_candles[-count:]
                
            self.candle_buffer.extend(warmed_candles)
            logger.info(f"Successfully warmed up candle buffer with {len(self.candle_buffer)} historical {timeframe} candles.")
        except Exception as e:
            logger.error(f"Error during candle buffer warmup: {e}")


    def on_candle(self, candle: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Invoked on each completed real-time index candle.
        1. Checks risk exits (daily cutoff, target, stop loss, trailing SL, max hold) first.
        2. Appends candle to buffer.
        3. Invokes SignalAdapter crossover rules.
        4. Fills transactions via PaperExecutionAdapter.
        
        Returns:
            Tuple[str, Dict[str, Any]] representing the execution action (BUY, SELL, or HOLD) and transaction metadata.
        """
        if self.is_paused:
            return "HOLD", {}

        current_ts = candle["timestamp"]
        if isinstance(current_ts, str):
            current_ts = datetime.fromisoformat(current_ts.replace('Z', '+00:00'))

        spot_price = float(candle["close"])

        # --- STEP 1: RISK EXITS EVALUATION ---
        if self.position_manager.active_position is not None and self.active_contract is not None:
            active = self.active_contract
            
            # 1.1 Daily Intraday cutoff time check
            cutoff_str = self.config.risk_management.cutoff_time or "15:15"
            try:
                cutoff_time = datetime.strptime(cutoff_str, "%H:%M").time()
                if current_ts.time() >= cutoff_time:
                    pos_data = self.execution_adapter.execute_sell(spot_price, current_ts, exit_reason="Intraday Cutoff Trigger")
                    self.active_contract = None
                    self.adapter.reset_state()
                    return "SELL", pos_data or {"exit_reason": "Intraday Cutoff Trigger"}
            except Exception as e:
                logger.error(f"Failed to check cutoff time: {e}")

            # 1.2 Maximum holding candles check
            candles_held = len(self.candle_buffer) - self.entry_index
            max_hold = self.config.risk_management.max_holding_candles
            if max_hold and candles_held >= max_hold:
                pos_data = self.execution_adapter.execute_sell(spot_price, current_ts, exit_reason="Maximum Holding Reached")
                self.active_contract = None
                self.adapter.reset_state()
                return "SELL", pos_data or {"exit_reason": "Maximum Holding Reached"}

            # 1.3 Premium/Spot evaluation
            held_premium = self.execution_adapter.estimate_premium(
                underlying=self.config.underlying_instrument_key,
                strike=active["strike"],
                expiry=active["expiry"],
                option_type=active["option_type"],
                spot_price=spot_price,
                timestamp=current_ts
            )
            
            active["last_premium"] = held_premium
            if held_premium > active.get("highest_premium", 0.0):
                active["highest_premium"] = held_premium

            exit_reason = None
            exit_price = held_premium

            # Dynamic strategy exits
            if self.is_dynamic and self.strategy_def is not None:
                from v2.strategy_builder.risk_engine import RiskEngine
                exit_reason, exit_price = RiskEngine.evaluate_exits(
                    self.strategy_def.risk,
                    active,
                    held_premium,
                    spot_price,
                    candles_held
                )
            else:
                # Standard risk SL / TP checking
                rm = self.config.risk_management
                entry_premium = active["entry_premium"]

                # Check Stop Loss
                if rm.stop_loss_value > 0:
                    sl_pct = rm.stop_loss_value / 100.0 if rm.stop_loss_type == "percent" else 0.0
                    sl_pts = rm.stop_loss_value if rm.stop_loss_type == "points" else (entry_premium * sl_pct)
                    
                    if held_premium <= (entry_premium - sl_pts):
                        exit_reason = "Stop Loss Hit"
                        exit_price = entry_premium - sl_pts

                # Check Target (Take Profit)
                if not exit_reason and rm.target_value > 0:
                    t_pct = rm.target_value / 100.0 if rm.target_type == "percent" else 0.0
                    t_pts = rm.target_value if rm.target_type == "points" else (entry_premium * t_pct)
                    
                    if held_premium >= (entry_premium + t_pts):
                        exit_reason = "Target Hit"
                        exit_price = entry_premium + t_pts

                # Check Trailing SL
                if not exit_reason and rm.trailing_sl_gap > 0:
                    highest = active.get("highest_premium", entry_premium)
                    if held_premium <= (highest - rm.trailing_sl_gap):
                        exit_reason = "Trailing SL Hit"
                        exit_price = highest - rm.trailing_sl_gap

            if exit_reason:
                pos_data = self.execution_adapter.execute_sell(spot_price, current_ts, exit_reason=exit_reason)
                self.active_contract = None
                self.adapter.reset_state()
                return "SELL", pos_data or {"exit_reason": exit_reason, "exit_price": exit_price}

        # --- STEP 2: SIGNAL GENERATION ---
        self.candle_buffer.append(candle)
        signal, info = self.adapter.evaluate(self.candle_buffer)

        if signal == "BUY":
            if self.position_manager.active_position is None:
                TelemetryLogger.log(
                    "SIGNAL",
                    "INFO",
                    f"BUY signal triggered by strategy logic. Spot: {spot_price}",
                    {"spot": spot_price, "timestamp": current_ts.isoformat()}
                )
                
                prev_ema = spot_price
                curr_ema = spot_price
                try:
                    close_prices = [float(c['close']) for c in self.candle_buffer]
                    if len(close_prices) >= 7:
                        import pandas as pd
                        ema_series = pd.Series(close_prices).ewm(span=5, adjust=False).mean()
                        prev_ema = float(ema_series.iloc[-2])
                        curr_ema = float(ema_series.iloc[-1])
                except Exception as e:
                    logger.debug(f"Failed to calculate EMA for trade explanation: {e}")

                from v2.trade_explainer import TradeExplainer
                entry_reason = TradeExplainer.explain_entry(
                    strategy_name=self.strategy_name,
                    prev_ema=prev_ema,
                    curr_ema=curr_ema,
                    spot_price=spot_price,
                    condition="Bullish Breakout"
                )

                pos_data = self.execution_adapter.execute_buy(
                    underlying=self.config.underlying_instrument_key,
                    spot_price=spot_price,
                    timestamp=current_ts,
                    entry_reason=entry_reason
                )
                
                self.entry_index = len(self.candle_buffer) - 1
                self.active_contract = {
                    "strike": pos_data["strike"],
                    "expiry": pos_data["expiry"],
                    "option_type": pos_data["option_type"],
                    "instrument_key": pos_data["instrument_key"],
                    "entry_premium": pos_data["premium_price"],
                    "entry_spot": spot_price,
                    "highest_premium": pos_data["premium_price"],
                    "last_premium": pos_data["premium_price"]
                }
                return "BUY", pos_data

        elif signal in ["SELL", "EXIT"]:
            if self.position_manager.active_position is not None:
                TelemetryLogger.log(
                    "SIGNAL",
                    "INFO",
                    f"SELL signal triggered by strategy logic. Spot: {spot_price}",
                    {"spot": spot_price, "timestamp": current_ts.isoformat()}
                )
                
                pos_data = self.execution_adapter.execute_sell(
                    spot_price=spot_price,
                    timestamp=current_ts,
                    exit_reason="Strategy Crossover Exit"
                )
                self.active_contract = None
                return "SELL", pos_data or {}

        # Handle Hold events
        if self.position_manager.active_position is not None and self.active_contract is not None:
            held_premium = self.active_contract["last_premium"]
            self.position_manager.hold_position({"premium_price": float(held_premium)}, current_ts)

        return "HOLD", {}
