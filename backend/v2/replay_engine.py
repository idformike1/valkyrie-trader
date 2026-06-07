import logging
import pandas as pd
from datetime import datetime, time as datetime_time
from typing import List, Dict, Any, Optional

from v2.config import BacktestConfig
from v2.cache.database import DEFAULT_CACHE_DB_PATH
from v2.cache.manager import HistoricalDataCacheManager
from v2.data_loader import UnderlyingHistoricalLoader, OptionHistoricalLoader
from v2.resolvers import HistoricalStrikeResolver, HistoricalExpiryResolver, HistoricalContractResolver
from v2.expired_contract_provider import HistoricalContractProvider
from v2.signal_adapter import SignalAdapter
from v2.replay_models import ReplaySignalEvent, ReplayContractEvent, ReplayTradeIntent, ReplayTimeline
from v2.replay_audit import log_replay_event
from v2.types import OptionType, StrikeMode, ExpiryMode

logger = logging.getLogger("Valkyrie.ReplayEngine")
logger.setLevel(logging.INFO)

def get_index_short_name(instrument_key: str) -> str:
    key_upper = instrument_key.upper()
    if "NIFTY BANK" in key_upper or "BANKNIFTY" in key_upper:
        return "BANKNIFTY"
    elif "NIFTY FIN SERVICE" in key_upper or "FINNIFTY" in key_upper:
        return "FINNIFTY"
    elif "NIFTY MID SELECT" in key_upper or "MIDCPNIFTY" in key_upper:
        return "MIDCPNIFTY"
    elif "NIFTY 50" in key_upper or "NIFTY" in key_upper:
        return "NIFTY"
    elif "SENSEX" in key_upper:
        return "SENSEX"
    elif "BANKEX" in key_upper:
        return "BANKEX"
    return instrument_key

def resample_candles(candles: List[Dict[str, Any]], timeframe: str) -> List[Dict[str, Any]]:
    """
    Resamples candles safely into the target timeframe without look-ahead leakage.
    If target timeframe is 1m, or if it's smaller than source, return as-is.
    """
    if not candles:
        return []
        
    tf_map = {
        "10s": "10s",
        "30s": "30s",
        "1m": "1min",
        "3m": "3min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h"
    }
    
    if timeframe in ["10s", "30s", "1m"]:
        return candles
        
    offset = tf_map.get(timeframe, "1T")
    
    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    resampled = df.resample(offset, label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    res_list = []
    for ts, row in resampled.iterrows():
        res_list.append({
            "timestamp": ts.to_pydatetime(),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": int(row['volume'])
        })
    return res_list

class HistoricalReplayEngine:
    def __init__(self, db_path: str = DEFAULT_CACHE_DB_PATH):
        self.db_path = db_path
        self.cache_manager = HistoricalDataCacheManager(db_path)
        self.spot_loader = UnderlyingHistoricalLoader(self.cache_manager)
        self.opt_loader = OptionHistoricalLoader(self.cache_manager)
        
        # Initialize and register expiry calendar provider
        self.contract_provider = HistoricalContractProvider(db_path)
        HistoricalExpiryResolver.set_provider(self.contract_provider)
        
        # Position tracking attributes
        self.position_manager = None
        self.ledger = None

    def _lookup_premium(
        self,
        index_name: str,
        strike: float,
        expiry: str,
        option_type: str,
        timeframe: str,
        timestamp: datetime,
        day_date: datetime
    ) -> Optional[Dict[str, Any]]:
        # Load all option candles for that contract on the day of the signal
        day_start = datetime.combine(day_date.date(), datetime_time(9, 15))
        day_end = datetime.combine(day_date.date(), datetime_time(15, 30))
        
        try:
            opt_candles = self.opt_loader.load_candles(
                index_name=index_name,
                strike_price=strike,
                expiry_date=expiry,
                option_type=option_type,
                timeframe=timeframe,
                from_date=day_start,
                to_date=day_end
            )
            
            sig_ts_naive = timestamp.replace(tzinfo=None) if timestamp.tzinfo else timestamp
            for c in opt_candles:
                c_ts = c["timestamp"]
                c_dt = datetime.fromisoformat(c_ts.replace('Z', '+00:00')) if isinstance(c_ts, str) else c_ts
                c_dt_naive = c_dt.replace(tzinfo=None) if c_dt.tzinfo else c_dt
                
                if c_dt_naive == sig_ts_naive:
                    return c
        except Exception as e:
            logger.error(f"Failed to lookup premium candle for {index_name} {strike} {option_type}: {e}")
        return None

    def run(self, config: BacktestConfig) -> ReplayTimeline:
        from v2.position_ledger import PositionLedger
        from v2.position_manager import PositionManager

        underlying_name = get_index_short_name(config.underlying_instrument_key)
        
        # 1. Load spot candles (use 1m resolution for base data and resample if needed)
        start_dt = datetime.strptime(config.start_date, "%Y-%m-%d")
        # Ensure we cover the full day
        start_dt = datetime.combine(start_dt.date(), datetime_time(9, 15))
        end_dt = datetime.strptime(config.end_date, "%Y-%m-%d")
        end_dt = datetime.combine(end_dt.date(), datetime_time(15, 30))
        
        raw_candles = self.spot_loader.load_candles(underlying_name, "1m", start_dt, end_dt)
        from v2.telemetry_logger import TelemetryLogger
        TelemetryLogger.log(
            "SYSTEM",
            "INFO",
            f"Loaded {len(raw_candles)} spot candles at 1m resolution for {underlying_name}.",
            {"raw_candles_count": len(raw_candles), "underlying": underlying_name}
        )
        
        # 2. Resample base candles to requested timeframe
        tf_val = config.timeframe.value if hasattr(config.timeframe, "value") else str(config.timeframe)
        underlying_candles = resample_candles(raw_candles, tf_val)
        
        TelemetryLogger.log(
            "SYSTEM",
            "INFO",
            f"Replay starting. Resampled base candles to {tf_val} timeframe. Total candles to process: {len(underlying_candles)}.",
            {"resampled_candles_count": len(underlying_candles), "timeframe": tf_val}
        )
        
        logger.info(f"Replay starting for {underlying_name}. Total underlying candles: {len(underlying_candles)}")
        
        # 3. Setup Signal Adapter
        is_dynamic = False
        strategy_def = None
        if getattr(config, "strategy_definition", None) is not None:
            from v2.strategy_builder import StrategyDefinition, SignalPipeline
            strategy_def = StrategyDefinition(**config.strategy_definition)
            adapter = SignalPipeline(strategy_def)
            strategy_name = strategy_def.name
            is_dynamic = True
        else:
            adapter = SignalAdapter(config.strategy_name, config.strategy_params)
            strategy_name = config.strategy_name
        
        # 4. Walk chronological replay loop
        timeline = ReplayTimeline(
            underlying=underlying_name,
            timeframe=tf_val,
            strategy=strategy_name
        )
        
        # Initialize Position Manager & Ledger
        self.ledger = PositionLedger()
        self.position_manager = PositionManager(ledger=self.ledger)
        
        active_contract = None
        
        for i in range(len(underlying_candles)):
            # History slice to prevent look-ahead leakage
            history = underlying_candles[:i+1]
            current_candle = underlying_candles[i]
            current_ts = current_candle["timestamp"]
            spot_price = current_candle["close"]
            
            opened_this_candle = False
            
            # If position is open and strategy_definition is used, check risk exits first
            if active_contract is not None and is_dynamic and strategy_def is not None:
                # Lookup current option premium
                held_premium_candle = self._lookup_premium(
                    index_name=underlying_name,
                    strike=active_contract["strike"],
                    expiry=active_contract["expiry"],
                    option_type=active_contract["option_type"],
                    timeframe="1m",
                    timestamp=current_ts,
                    day_date=current_ts
                )
                held_premium = held_premium_candle["close"] if held_premium_candle else active_contract.get("last_premium", active_contract["strike"])
                if held_premium_candle:
                    active_contract["last_premium"] = held_premium
                    
                # Update highest premium for trailing SL
                if held_premium > active_contract.get("highest_premium", 0.0):
                    active_contract["highest_premium"] = held_premium
                    
                candles_held = i - active_contract.get("entry_index", 0)
                
                from v2.strategy_builder.risk_engine import RiskEngine
                exit_reason, exit_price = RiskEngine.evaluate_exits(
                    strategy_def.risk,
                    active_contract,
                    held_premium,
                    spot_price,
                    candles_held
                )
                
                if exit_reason:
                    # Close position due to risk exit
                    exit_reason_mapped = exit_reason
                    if exit_reason in ["STOP_LOSS", "TRAILING_STOP_LOSS"]:
                        exit_reason_mapped = "Stop Loss Hit"
                    elif exit_reason == "TARGET_LIMIT":
                        exit_reason_mapped = "Target Hit"
                    elif exit_reason == "SESSION_END":
                        exit_reason_mapped = "Cutoff Exit"
                    elif exit_reason == "MAX_DURATION":
                        exit_reason_mapped = "Max Holding Reached"

                    # Construct updated explanation metadata
                    current_exp = {}
                    if self.position_manager.active_position and self.position_manager.active_position.metadata:
                        current_exp = self.position_manager.active_position.metadata.get("explanation", {})

                    pos_data = {
                        "underlying": underlying_name,
                        "strike": float(active_contract["strike"]),
                        "expiry": active_contract["expiry"],
                        "option_type": active_contract["option_type"],
                        "instrument_key": active_contract["instrument_key"],
                        "premium_price": float(exit_price),
                        "signal": "SELL_INTENT",
                        "metadata": {
                            "exit_reason": exit_reason_mapped,
                            "explanation": {
                                **current_exp,
                                "exit_reason": exit_reason_mapped,
                                "market_snapshot": {
                                    **current_exp.get("market_snapshot", {}),
                                    "exit_premium": float(exit_price)
                                }
                            }
                        }
                    }
                    
                    intent = ReplayTradeIntent(
                        timestamp=current_ts,
                        underlying=underlying_name,
                        signal="SELL_INTENT",
                        spot_price=float(spot_price),
                        strike=float(active_contract["strike"]),
                        expiry=active_contract["expiry"],
                        option_type=active_contract["option_type"],
                        instrument_key=active_contract["instrument_key"],
                        premium_price=float(exit_price),
                        source=active_contract["source"]
                    )
                    timeline.events.append(intent)
                    log_replay_event(current_ts, "SELL_INTENT", f"{active_contract['strike']} {active_contract['option_type']} ({active_contract['expiry']})", exit_price, active_contract["source"])
                    
                    TelemetryLogger.log(
                        "POSITION",
                        "INFO",
                        f"Closed position: {active_contract['strike']} {active_contract['option_type']} ({active_contract['expiry']}) | Exit Premium: {exit_price:.2f} | Reason: {exit_reason_mapped} | Spot: {spot_price}",
                        {
                            "action": "close",
                            "strike": active_contract["strike"],
                            "option_type": active_contract["option_type"],
                            "expiry": active_contract["expiry"],
                            "exit_premium": exit_price,
                            "reason": exit_reason_mapped,
                            "spot": spot_price
                        }
                    )
                    
                    self.position_manager.close_position(pos_data, current_ts)
                    adapter.reset_state()
                    active_contract = None
                    continue  # skip to next candle
            
            # Evaluate signal
            signal, info = adapter.evaluate(history)
            
            if signal == "BUY":
                if active_contract is not None:
                    continue  # Already in position, ignore new entries
                
                TelemetryLogger.log(
                    "SIGNAL",
                    "INFO",
                    f"BUY signal generated. Strategy: {strategy_name} | Spot: {spot_price} | Time: {current_ts.isoformat()}",
                    {"strategy": strategy_name, "spot": spot_price, "timestamp": current_ts.isoformat()}
                )
                
                # Determine Option Type (CE or PE)
                if is_dynamic and strategy_def is not None:
                    opt_pref = strategy_def.contract.option_type
                else:
                    opt_pref = config.option_type_preference
                    
                if opt_pref == "DYNAMIC":
                    option_type = "CE"  # Default CE for simple replay
                elif opt_pref == "CE_ONLY":
                    option_type = "CE"
                elif opt_pref == "PE_ONLY":
                    option_type = "PE"
                else:
                    option_type = "CE"
                
                # Resolve Strike Mode
                if is_dynamic and strategy_def is not None:
                    strike_mode_str = strategy_def.contract.strike.mode
                else:
                    strike_mode_str = config.strike_selection.mode
                strike_mode = StrikeMode(strike_mode_str) if isinstance(strike_mode_str, str) else strike_mode_str
                
                strike_res = HistoricalStrikeResolver.resolve(underlying_name, spot_price, strike_mode, OptionType(option_type))
                strike = strike_res["resolved_strike"]
                
                # Resolve Expiry Mode
                if is_dynamic and strategy_def is not None:
                    expiry_mode_str = strategy_def.contract.expiry.mode
                    roll_hrs = strategy_def.contract.expiry.roll_threshold_hours
                else:
                    expiry_mode_str = config.expiry_selection.mode
                    roll_hrs = config.expiry_selection.roll_threshold_hours
                expiry_mode = ExpiryMode(expiry_mode_str) if isinstance(expiry_mode_str, str) else expiry_mode_str
                
                expiry = HistoricalExpiryResolver.resolve(underlying_name, current_ts, expiry_mode, roll_hrs)
                
                # Resolve Option Key
                try:
                    instrument_key = HistoricalContractResolver.resolve(underlying_name, strike, expiry, option_type)
                except Exception as contract_err:
                    logger.warning(f"Could not resolve contract for {underlying_name} {strike} {expiry}: {contract_err}")
                    continue
                
                # Lookup premium price
                premium_candle = self._lookup_premium(
                    index_name=underlying_name,
                    strike=strike,
                    expiry=expiry,
                    option_type=option_type,
                    timeframe="1m",  # Premium lookup uses 1m data for precision
                    timestamp=current_ts,
                    day_date=current_ts
                )
                
                if premium_candle:
                    premium = premium_candle["close"]
                    
                    # Fetch DB source info
                    source = "UPSTOX_EXPIRED_API"
                    try:
                        import sqlite3
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT source FROM historical_contracts WHERE instrument_key = ?",
                            (instrument_key,)
                        )
                        row = cursor.fetchone()
                        if row:
                            source = row[0]
                        conn.close()
                    except Exception:
                        pass
                    
                    intent = ReplayTradeIntent(
                        timestamp=current_ts,
                        underlying=underlying_name,
                        signal="BUY_INTENT",
                        spot_price=float(spot_price),
                        strike=float(strike),
                        expiry=expiry,
                        option_type=option_type,
                        instrument_key=instrument_key,
                        premium_price=float(premium),
                        source=source
                    )
                    timeline.events.append(intent)
                    log_replay_event(current_ts, "BUY_INTENT", f"{strike} {option_type} ({expiry})", premium, source)
                    
                    # Open position in PositionManager
                    idx_lot = 65
                    underlying_upper = underlying_name.upper()
                    if "BANKNIFTY" in underlying_upper:
                        idx_lot = 30
                    elif "FINNIFTY" in underlying_upper:
                        idx_lot = 60
                    elif "MIDCPNIFTY" in underlying_upper:
                        idx_lot = 120
                    elif "SENSEX" in underlying_upper:
                        idx_lot = 20
                    elif "BANKEX" in underlying_upper:
                        idx_lot = 30
                    elif "NIFTY" in underlying_upper:
                        idx_lot = 65
                    num_lots = config.execution.lot_size if (hasattr(config, "execution") and config.execution) else 1
                    quantity = num_lots * idx_lot
                    
                    # Resolve ATM strike
                    try:
                        atm_res = HistoricalStrikeResolver.resolve(underlying_name, spot_price, StrikeMode.ATM, OptionType(option_type))
                        atm_strike = float(atm_res["resolved_strike"])
                    except Exception:
                        atm_strike = float(strike)
                        
                    # Determine entry reason
                    entry_reason = "Strategy Entry Signal"
                    if "heikin" in strategy_name.lower():
                        entry_reason = "Bullish HA Candle"
                    elif "five_ema" in strategy_name.lower():
                        entry_reason = "Alert Candle Breakout"
                    elif "ema" in strategy_name.lower():
                        entry_reason = "Bullish EMA Cross"
                        
                    # Extract signal snapshot
                    signal_snapshot = {}
                    if "heikin" in strategy_name.lower():
                        signal_snapshot = {
                            "prior_ha_open": float(info.get("prior_ha_open", 0.0)),
                            "prior_ha_close": float(info.get("prior_ha_close", 0.0)),
                            "comp_ha_open": float(info.get("comp_ha_open", 0.0)),
                            "comp_ha_close": float(info.get("comp_ha_close", 0.0)),
                            "comp_ha_low": float(info.get("comp_ha_low", 0.0))
                        }
                    elif "five_ema" in strategy_name.lower():
                        signal_snapshot = {
                            "ema": float(info.get("ema", 0.0)),
                            "candle_high": float(info.get("candle_high", 0.0)),
                            "candle_low": float(info.get("candle_low", 0.0)),
                            "alert_high": float(info.get("alert_high", 0.0)),
                            "alert_low": float(info.get("alert_low", 0.0))
                        }
                    elif "ema" in strategy_name.lower():
                        signal_snapshot = {
                            "prev_fast": float(info.get("prev_fast", 0.0)),
                            "prev_slow": float(info.get("prev_slow", 0.0)),
                            "curr_fast": float(info.get("curr_fast", 0.0)),
                            "curr_slow": float(info.get("curr_slow", 0.0))
                        }
                        
                    resolver_snapshot = {
                        "strike_mode": str(strike_mode_str),
                        "expiry_mode": str(expiry_mode_str),
                        "atm_strike": atm_strike,
                        "resolved_strike": float(strike),
                        "resolved_expiry": str(expiry),
                        "option_type": str(option_type)
                    }
                    
                    risk_snapshot = {
                        "stop_loss_type": str(getattr(config.risk_management, "stop_loss_type", "percent")),
                        "stop_loss_value": float(getattr(config.risk_management, "stop_loss_value", 0.0)),
                        "target_type": str(getattr(config.risk_management, "target_type", "percent")),
                        "target_value": float(getattr(config.risk_management, "target_value", 0.0)),
                        "max_holding_candles": int(getattr(config.risk_management, "max_holding_candles", 10)),
                        "quantity": int(quantity)
                    }
                    
                    market_snapshot = {
                        "spot_price": float(spot_price),
                        "entry_premium": float(premium),
                        "exit_premium": 0.0
                    }
                    
                    explanation_data = {
                        "strategy_name": strategy_name,
                        "entry_reason": entry_reason,
                        "exit_reason": "Active Position",
                        "signal_snapshot": signal_snapshot,
                        "resolver_snapshot": resolver_snapshot,
                        "risk_snapshot": risk_snapshot,
                        "market_snapshot": market_snapshot
                    }
                    
                    pos_data = {
                        "underlying": underlying_name,
                        "strike": float(strike),
                        "expiry": expiry,
                        "option_type": option_type,
                        "instrument_key": instrument_key,
                        "premium_price": float(premium),
                        "lot_size": idx_lot,
                        "quantity": quantity,
                        "signal": "BUY_INTENT",
                        "metadata": {"explanation": explanation_data}
                    }
                    self.position_manager.open_position(pos_data, current_ts)
                    opened_this_candle = True
                    
                    TelemetryLogger.log(
                        "POSITION",
                        "INFO",
                        f"Opened position: {strike} {option_type} ({expiry}) | Entry Premium: {premium:.2f} | Spot: {spot_price} | Qty: {quantity}",
                        {
                            "action": "open",
                            "strike": strike,
                            "option_type": option_type,
                            "expiry": expiry,
                            "premium": premium,
                            "spot": spot_price,
                            "quantity": quantity
                        }
                    )
                    
                    active_contract = {
                        "strike": strike,
                        "expiry": expiry,
                        "option_type": option_type,
                        "instrument_key": instrument_key,
                        "source": source,
                        "entry_premium": float(premium),
                        "entry_spot": float(spot_price),
                        "entry_index": i,
                        "highest_premium": float(premium)
                    }
            
            elif signal == "SELL":
                if active_contract is None:
                    continue  # No position open, ignore exits
                
                # Lookup premium price for current active contract at exit timestamp
                premium_candle = self._lookup_premium(
                    index_name=underlying_name,
                    strike=active_contract["strike"],
                    expiry=active_contract["expiry"],
                    option_type=active_contract["option_type"],
                    timeframe="1m",
                    timestamp=current_ts,
                    day_date=current_ts
                )
                
                if premium_candle:
                    premium = premium_candle["close"]
                    intent = ReplayTradeIntent(
                        timestamp=current_ts,
                        underlying=underlying_name,
                        signal="SELL_INTENT",
                        spot_price=float(spot_price),
                        strike=float(active_contract["strike"]),
                        expiry=active_contract["expiry"],
                        option_type=active_contract["option_type"],
                        instrument_key=active_contract["instrument_key"],
                        premium_price=float(premium),
                        source=active_contract["source"]
                    )
                    timeline.events.append(intent)
                    log_replay_event(current_ts, "SELL_INTENT", f"{active_contract['strike']} {active_contract['option_type']} ({active_contract['expiry']})", premium, active_contract["source"])
                    
                    # Close position in PositionManager
                    exit_reason_raw = info.get("reason", "Signal Exit")
                    exit_reason_mapped = "Signal Exit"
                    if exit_reason_raw in ["STOP_LOSS", "Stop Loss Hit"]:
                        exit_reason_mapped = "Stop Loss Hit"
                    elif exit_reason_raw in ["TARGET_LIMIT", "Target Hit"]:
                        exit_reason_mapped = "Target Hit"
                    elif exit_reason_raw in ["SESSION_END", "SESSION_CUTOFF", "Cutoff Exit"]:
                        exit_reason_mapped = "Cutoff Exit"
                    elif exit_reason_raw in ["MAX_DURATION", "Max Holding Reached"]:
                        exit_reason_mapped = "Max Holding Reached"
                    elif exit_reason_raw in ["TECHNICAL_REVERSAL", "Signal Reversal"]:
                        exit_reason_mapped = "Signal Reversal"
                    else:
                        exit_reason_mapped = exit_reason_raw
                        
                    current_exp = {}
                    if self.position_manager.active_position and self.position_manager.active_position.metadata:
                        current_exp = self.position_manager.active_position.metadata.get("explanation", {})
                        
                    pos_data = {
                        "underlying": underlying_name,
                        "strike": float(active_contract["strike"]),
                        "expiry": active_contract["expiry"],
                        "option_type": active_contract["option_type"],
                        "instrument_key": active_contract["instrument_key"],
                        "premium_price": float(premium),
                        "signal": "SELL_INTENT",
                        "metadata": {
                            "exit_reason": exit_reason_mapped,
                            "explanation": {
                                **current_exp,
                                "exit_reason": exit_reason_mapped,
                                "market_snapshot": {
                                    **current_exp.get("market_snapshot", {}),
                                    "exit_premium": float(premium)
                                }
                            }
                        }
                    }
                    
                    TelemetryLogger.log(
                        "SIGNAL",
                        "INFO",
                        f"SELL signal generated. Strategy: {strategy_name} | Spot: {spot_price} | Time: {current_ts.isoformat()}",
                        {"strategy": strategy_name, "spot": spot_price, "timestamp": current_ts.isoformat()}
                    )
                    
                    TelemetryLogger.log(
                        "POSITION",
                        "INFO",
                        f"Closed position: {active_contract['strike']} {active_contract['option_type']} ({active_contract['expiry']}) | Exit Premium: {premium:.2f} | Reason: {exit_reason_mapped} | Spot: {spot_price}",
                        {
                            "action": "close",
                            "strike": active_contract["strike"],
                            "option_type": active_contract["option_type"],
                            "expiry": active_contract["expiry"],
                            "exit_premium": premium,
                            "reason": exit_reason_mapped,
                            "spot": spot_price
                        }
                    )
                    
                    self.position_manager.close_position(pos_data, current_ts)
                    active_contract = None
            
            # Record hold state event if a position is held over this candle
            if active_contract is not None and not opened_this_candle:
                held_premium_candle = self._lookup_premium(
                    index_name=underlying_name,
                    strike=active_contract["strike"],
                    expiry=active_contract["expiry"],
                    option_type=active_contract["option_type"],
                    timeframe="1m",
                    timestamp=current_ts,
                    day_date=current_ts
                )
                held_premium = held_premium_candle["close"] if held_premium_candle else active_contract.get("last_premium", active_contract["strike"])
                if held_premium_candle:
                    active_contract["last_premium"] = held_premium
                
                pos_data = {
                    "premium_price": float(held_premium)
                }
                self.position_manager.hold_position(pos_data, current_ts)
                    
        return timeline

