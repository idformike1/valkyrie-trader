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
        
        # 2. Resample base candles to requested timeframe
        tf_val = config.timeframe.value if hasattr(config.timeframe, "value") else str(config.timeframe)
        underlying_candles = resample_candles(raw_candles, tf_val)
        
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
                    pos_data = {
                        "underlying": underlying_name,
                        "strike": float(active_contract["strike"]),
                        "expiry": active_contract["expiry"],
                        "option_type": active_contract["option_type"],
                        "instrument_key": active_contract["instrument_key"],
                        "premium_price": float(exit_price),
                        "signal": "SELL_INTENT",
                        "metadata": {"exit_reason": exit_reason}
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
                    
                    self.position_manager.close_position(pos_data, current_ts)
                    adapter.reset_state()
                    active_contract = None
                    continue  # skip to next candle
            
            # Evaluate signal
            signal, info = adapter.evaluate(history)
            
            if signal == "BUY":
                if active_contract is not None:
                    continue  # Already in position, ignore new entries
                
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
                    idx_lot = 75
                    if "BANKNIFTY" in underlying_name:
                        idx_lot = 15
                    elif "FINNIFTY" in underlying_name:
                        idx_lot = 40
                    num_lots = config.execution.lot_size if (hasattr(config, "execution") and config.execution) else 1
                    quantity = num_lots * idx_lot
                    
                    pos_data = {
                        "underlying": underlying_name,
                        "strike": float(strike),
                        "expiry": expiry,
                        "option_type": option_type,
                        "instrument_key": instrument_key,
                        "premium_price": float(premium),
                        "lot_size": idx_lot,
                        "quantity": quantity,
                        "signal": "BUY_INTENT"
                    }
                    self.position_manager.open_position(pos_data, current_ts)
                    opened_this_candle = True
                    
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
                    pos_data = {
                        "underlying": underlying_name,
                        "strike": float(active_contract["strike"]),
                        "expiry": active_contract["expiry"],
                        "option_type": active_contract["option_type"],
                        "instrument_key": active_contract["instrument_key"],
                        "premium_price": float(premium),
                        "signal": "SELL_INTENT"
                    }
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

