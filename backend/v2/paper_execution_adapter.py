import math
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from v2.position_manager import PositionManager
from v2.resolvers import HistoricalStrikeResolver, HistoricalExpiryResolver, HistoricalContractResolver
from v2.types import StrikeMode, ExpiryMode, OptionType
from v2.config import BacktestConfig
from v2.telemetry_logger import TelemetryLogger

logger = logging.getLogger("Valkyrie.PaperExecutionAdapter")

class PaperExecutionAdapter:
    """
    Responsibilities:
    - Fill BUY instantly at ask price (fallback to LTP).
    - Fill SELL instantly at bid price (fallback to LTP).
    - Resolve option details (strike, expiry, contract key, lot sizes).
    - Checks live OptionQuoteCache for market option premiums.
    - Cascades gracefully through fallback hierarchies (Live quote -> DB cache -> Synthetic).
    - Trigger PositionManager state updates and V2 accounting logs.
    """
    def __init__(self, position_manager: PositionManager, config: BacktestConfig, db_path: Optional[str] = None):
        self.position_manager = position_manager
        self.config = config
        self.db_path = db_path
        
        # Dynamic cache option premium loader fallback
        self.opt_loader = None
        if db_path:
            try:
                from v2.cache.manager import HistoricalDataCacheManager
                from v2.data_loader import OptionHistoricalLoader
                self.cache_manager = HistoricalDataCacheManager(db_path)
                self.opt_loader = OptionHistoricalLoader(self.cache_manager)
            except Exception as e:
                logger.debug(f"Could not load OptionHistoricalLoader: {e}")

    def estimate_premium(
        self, 
        underlying: str, 
        strike: float, 
        expiry: str, 
        option_type: str, 
        spot_price: float, 
        timestamp: datetime,
        side: str = "BUY"
    ) -> float:
        """
        Calculates or retrieves the resolved option premium following our three-tier priority structure:
        1. Live OptionQuoteCache quote (BUY uses ask, SELL uses bid, fallback to LTP).
        2. Historical Option DB cache match.
        3. Synthetic Analytical Option Pricing fallback.
        """
        # Resolve dynamic contract key
        try:
            instrument_key = HistoricalContractResolver.resolve(underlying, strike, expiry, option_type)
        except Exception:
            instrument_key = f"{underlying}_{expiry}_{int(strike)}_{option_type}"

        # --- TIER 1: LIVE WEBSOCKET OPTION QUOTE CACHE ---
        from v2.option_quote_cache import OptionQuoteCache, subscribe_option_contract
        
        # Dynamic trigger contract subscription on WS feed thread
        subscribe_option_contract(instrument_key)

        quote = OptionQuoteCache.get(instrument_key)
        if quote is not None:
            TelemetryLogger.log(
                "SIGNAL",
                "INFO",
                f"QUOTE_RECEIVED: Resolved quote for option {instrument_key}. LTP: {quote.ltp}, Bid: {quote.bid}, Ask: {quote.ask}",
                {"instrument_key": instrument_key, "ltp": quote.ltp, "bid": quote.bid, "ask": quote.ask}
            )

            fill_price = None
            if side == "BUY":
                if quote.ask and quote.ask > 0.0:
                    fill_price = quote.ask
                else:
                    fill_price = quote.ltp
            else:  # SELL
                if quote.bid and quote.bid > 0.0:
                    fill_price = quote.bid
                else:
                    fill_price = quote.ltp

            if fill_price and fill_price > 0.0:
                TelemetryLogger.log(
                    "POSITION",
                    "INFO",
                    f"REAL_FILL_USED: Filled {side} order using actual market option quote: {fill_price:.2f}",
                    {"instrument_key": instrument_key, "side": side, "fill_price": fill_price, "source": "WebSocket"}
                )
                return fill_price

        # --- QUOTE MISSING EMISSION ---
        TelemetryLogger.log(
            "SIGNAL",
            "WARNING",
            f"QUOTE_MISSING: No quote available in OptionQuoteCache for option {instrument_key}.",
            {"instrument_key": instrument_key}
        )

        # --- TIER 2: HISTORICAL OPTION DB CACHE MATCH ---
        if self.opt_loader:
            try:
                day_start = datetime.combine(timestamp.date(), datetime.min.time())
                day_end = datetime.combine(timestamp.date(), datetime.max.time())
                opt_candles = self.opt_loader.load_candles(
                    index_name=underlying,
                    strike_price=strike,
                    expiry_date=expiry,
                    option_type=option_type,
                    timeframe="1m",
                    from_date=day_start,
                    to_date=day_end
                )
                sig_ts_naive = timestamp.replace(tzinfo=None) if timestamp.tzinfo else timestamp
                for c in opt_candles:
                    c_ts = c["timestamp"]
                    c_dt = datetime.fromisoformat(c_ts.replace('Z', '+00:00')) if isinstance(c_ts, str) else c_ts
                    c_dt_naive = c_dt.replace(tzinfo=None) if c_dt.tzinfo else c_dt
                    
                    if abs((c_dt_naive - sig_ts_naive).total_seconds()) < 60:
                        TelemetryLogger.log(
                            "POSITION",
                            "INFO",
                            f"REAL_FILL_USED: Filled {side} order using historical Option DB cache: {c['close']}",
                            {"instrument_key": instrument_key, "side": side, "fill_price": c["close"], "source": "HistoricalDB"}
                        )
                        return float(c["close"])
            except Exception as e:
                logger.debug(f"DB premium lookup failed, falling back: {e}")

        # --- TIER 3: SYNTHETIC ANALYTICAL MODEL FALLBACK ---
        TelemetryLogger.log(
            "SIGNAL",
            "WARNING",
            f"SYNTHETIC_FILL_USED: Falling back to mathematical premium model for {instrument_key}.",
            {"instrument_key": instrument_key, "side": side}
        )
        logger.warning("SYNTHETIC_FILL_USED")

        # High-fidelity analytical premium decay model
        atm_extrinsic = spot_price * 0.015  # 1.5% ATM extrinsic factor
        if option_type == "CE":
            if spot_price > strike:
                intrinsic = spot_price - strike
                premium = intrinsic + atm_extrinsic
            else:
                dist = strike - spot_price
                premium = atm_extrinsic * math.exp(-2.5 * dist / spot_price)
        else:  # PE
            if spot_price < strike:
                intrinsic = strike - spot_price
                premium = intrinsic + atm_extrinsic
            else:
                dist = spot_price - strike
                premium = atm_extrinsic * math.exp(-2.5 * dist / spot_price)

        return max(round(premium, 2), 1.0)

    def execute_buy(self, underlying: str, spot_price: float, timestamp: datetime) -> Dict[str, Any]:
        """
        Fills a BUY paper order instantly at ask price (or LTP), resolved ATM/OTM options, and opens position.
        """
        # Determine Option Type CE/PE preference
        opt_pref = self.config.option_type_preference
        if opt_pref == "CE_ONLY":
            option_type = "CE"
        elif opt_pref == "PE_ONLY":
            option_type = "PE"
        else:
            # Standard dynamic bullish default
            option_type = "CE"

        # Resolve Strike
        strike_mode = self.config.strike_selection.mode
        strike_res = HistoricalStrikeResolver.resolve(underlying, spot_price, strike_mode, OptionType(option_type))
        strike = strike_res["resolved_strike"]

        # Resolve Expiry
        expiry_mode = self.config.expiry_selection.mode
        roll_hrs = self.config.expiry_selection.roll_threshold_hours
        expiry = HistoricalExpiryResolver.resolve(underlying, timestamp, expiry_mode, roll_hrs)

        # Resolve Option Key
        try:
            instrument_key = HistoricalContractResolver.resolve(underlying, strike, expiry, option_type)
        except Exception:
            instrument_key = f"{underlying}_{expiry}_{int(strike)}_{option_type}"

        # Estimate Premium at Ask price
        premium = self.estimate_premium(underlying, strike, expiry, option_type, spot_price, timestamp, side="BUY")

        # Quantity logic
        idx_lot = 75
        if "BANKNIFTY" in underlying:
            idx_lot = 15
        elif "FINNIFTY" in underlying:
            idx_lot = 40
        num_lots = self.config.execution.lot_size
        quantity = num_lots * idx_lot

        pos_data = {
            "underlying": underlying,
            "strike": float(strike),
            "expiry": expiry,
            "option_type": option_type,
            "instrument_key": instrument_key,
            "premium_price": float(premium),
            "lot_size": idx_lot,
            "quantity": quantity,
            "signal": "BUY_INTENT"
        }

        self.position_manager.open_position(pos_data, timestamp)

        TelemetryLogger.log(
            "POSITION",
            "INFO",
            f"Opened Paper Position: {strike} {option_type} ({expiry}) | Qty: {quantity} | Premium: {premium:.2f} | Spot: {spot_price}",
            {
                "action": "open",
                "underlying": underlying,
                "strike": strike,
                "option_type": option_type,
                "expiry": expiry,
                "quantity": quantity,
                "premium": premium,
                "spot": spot_price
            }
        )
        return pos_data

    def execute_sell(self, spot_price: float, timestamp: datetime, exit_reason: str = "Signal Exit") -> Optional[Dict[str, Any]]:
        """
        Fills a SELL paper order instantly at bid price (or LTP), closing position, invoking PnLEngine and loggers.
        """
        active_pos = self.position_manager.active_position
        if active_pos is None:
            return None

        # Estimate Premium at Bid price
        premium = self.estimate_premium(
            active_pos.underlying,
            active_pos.strike,
            active_pos.expiry,
            active_pos.option_type,
            spot_price,
            timestamp,
            side="SELL"
        )

        pos_data = {
            "underlying": active_pos.underlying,
            "strike": active_pos.strike,
            "expiry": active_pos.expiry,
            "option_type": active_pos.option_type,
            "instrument_key": active_pos.instrument_key,
            "premium_price": float(premium),
            "signal": "SELL_INTENT",
            "metadata": {"exit_reason": exit_reason}
        }

        pos_id = active_pos.position_id
        self.position_manager.close_position(pos_data, timestamp)

        # Get V2 accounting record
        accounting_record = self.position_manager.ledger.accounting_records[-1]

        TelemetryLogger.log(
            "POSITION",
            "INFO",
            f"Closed Paper Position: {active_pos.strike} {active_pos.option_type} ({active_pos.expiry}) | Premium: {premium:.2f} | Reason: {exit_reason} | Spot: {spot_price}",
            {
                "action": "close",
                "underlying": active_pos.underlying,
                "strike": active_pos.strike,
                "option_type": active_pos.option_type,
                "expiry": active_pos.expiry,
                "premium": premium,
                "reason": exit_reason,
                "spot": spot_price
            }
        )

        TelemetryLogger.log(
            "PNL",
            "INFO",
            f"PnL Calculated for trade {pos_id}: Gross: {accounting_record.gross_pnl:.2f} | Charges: {accounting_record.charges.total_charges:.2f} | Net: {accounting_record.net_pnl:.2f}",
            {
                "position_id": pos_id,
                "gross_pnl": accounting_record.gross_pnl,
                "charges": accounting_record.charges.model_dump(),
                "net_pnl": accounting_record.net_pnl
            }
        )

        return pos_data
