import math
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from v2.resolvers import HistoricalStrikeResolver, HistoricalExpiryResolver, HistoricalContractResolver
from v2.types import OptionType
from v2.telemetry_logger import TelemetryLogger

logger = logging.getLogger("Valkyrie.PaperExecutionAdapter")

class PaperExecutionAdapter:
    """
    Simulates live paper trade execution. Resolves strikes and weekly expiry dates,
    estimates filled premium based on live feeds or synthetic fallbacks, and manages positions.
    """
    def __init__(self, *args, **kwargs):
        # Auto-detect parameter order (supports both V2 engine and testing patterns)
        config = None
        position_manager = None
        db_path = "valkyrie_trades.db"
        opt_loader = None
        
        if "config" in kwargs:
            config = kwargs["config"]
        if "position_manager" in kwargs:
            position_manager = kwargs["position_manager"]
        if "db_path" in kwargs:
            db_path = kwargs["db_path"]
        if "opt_loader" in kwargs:
            opt_loader = kwargs["opt_loader"]
            
        remaining_args = list(args)
        if remaining_args:
            first = remaining_args.pop(0)
            if hasattr(first, "underlying_instrument_key") or hasattr(first, "strategy_name"):
                config = first
            else:
                position_manager = first
                
        if remaining_args:
            second = remaining_args.pop(0)
            if config is None:
                config = second
            else:
                position_manager = second
                
        if remaining_args:
            third = remaining_args.pop(0)
            if isinstance(third, str):
                db_path = third
            else:
                opt_loader = third
                
        self.config = config
        self.position_manager = position_manager
        self.db_path = db_path
        self.opt_loader = opt_loader
        self._local_state = threading.local()

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
        if not hasattr(self._local_state, 'last_source'):
            self._local_state.last_source = "SYNTHETIC_MODEL"

        # Resolve dynamic contract key
        try:
            instrument_key = HistoricalContractResolver.resolve(underlying, strike, expiry, option_type)
        except Exception:
            instrument_key = f"{underlying}_{expiry}_{int(strike)}_{option_type}"

        # --- TIER 1: LIVE WEBSOCKET OPTION QUOTE CACHE ---
        from v2.option_quote_cache import OptionQuoteCache, subscribe_option_contract
        from v2.quote_health import QuoteHealthTracker
        import time
        
        # Dynamic trigger contract subscription on WS feed thread
        subscribe_option_contract(instrument_key)

        quote = OptionQuoteCache.get(instrument_key)
        
        is_quote_valid = False
        if quote is not None:
            age_ms = int(time.time() * 1000) - quote.last_update_ms
            if age_ms <= 1500:
                is_quote_valid = True

        if not hasattr(self._local_state, 'last_quote_quality'):
            self._local_state.last_quote_quality = None

        if is_quote_valid and quote is not None:
            age_ms = int(time.time() * 1000) - quote.last_update_ms
            bid = quote.bid or quote.ltp or 0.0
            ask = quote.ask or quote.ltp or 0.0
            spread = ask - bid
            self._local_state.last_quote_quality = {
                "bid": float(bid),
                "ask": float(ask),
                "spread": float(spread),
                "tick_age_ms": int(age_ms)
            }
            QuoteHealthTracker.record_hit()
            self._local_state.last_source = "LIVE_QUOTE"
            
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
                    {"instrument_key": instrument_key, "side": side, "fill_price": fill_price, "source": "LIVE_QUOTE"}
                )
                return fill_price

        # Record a miss if we couldn't use Tier 1
        QuoteHealthTracker.record_miss()
        self._local_state.last_quote_quality = None

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
                        self._local_state.last_source = "HISTORICAL_CACHE"
                        TelemetryLogger.log(
                            "POSITION",
                            "INFO",
                            f"REAL_FILL_USED: Filled {side} order using historical Option DB cache: {c['close']}",
                            {"instrument_key": instrument_key, "side": side, "fill_price": c["close"], "source": "HISTORICAL_CACHE"}
                        )
                        return float(c["close"])
            except Exception as e:
                logger.debug(f"DB premium lookup failed, falling back: {e}")

        # --- TIER 3: SYNTHETIC ANALYTICAL MODEL FALLBACK ---
        QuoteHealthTracker.record_synthetic_fill()
        self._local_state.last_source = "SYNTHETIC_MODEL"

        TelemetryLogger.log(
            "SIGNAL",
            "WARNING",
            f"SYNTHETIC_FILL_USED: Falling back to mathematical premium model for {instrument_key}.",
            {"instrument_key": instrument_key, "side": side, "source": "SYNTHETIC_MODEL"}
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

    def execute_buy(self, underlying: str, spot_price: float, timestamp: datetime, entry_reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Fills a BUY paper order instantly at ask price (or LTP), resolved ATM/OTM options, and opens position.
        """
        opt_pref = self.config.option_type_preference
        if opt_pref == "CE_ONLY":
            option_type = "CE"
        elif opt_pref == "PE_ONLY":
            option_type = "PE"
        else:
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
        execution_source = getattr(self._local_state, 'last_source', "SYNTHETIC_MODEL")
        quote_quality = getattr(self._local_state, 'last_quote_quality', None)

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
            "signal": "BUY_INTENT",
            "execution_source": execution_source,
            "entry_reason": entry_reason,
            "metadata": {
                "quote_quality": quote_quality
            }
        }

        self.position_manager.open_position(pos_data, timestamp)

        # Compute Fill Diagnostics (Phase 6) - Hardened Real/Unavailable Diagnostics
        slippage_pct = None
        if execution_source == "LIVE_QUOTE" and quote_quality:
            ask = quote_quality.get("ask")
            if ask and ask > 0:
                slippage_pct = round(((premium - ask) / ask) * 100, 4)

        fill_diagnostics = {
            "fill_price": float(premium),
            "quantity": int(quantity),
            "premium": float(premium * quantity),
            "brokerage": None,
            "slippage_pct": slippage_pct,
            "execution_latency_ms": None
        }

        # Incrementally log trade to SQLite db
        try:
            import app
            if getattr(app, 'CURRENT_SESSION_ID', None):
                import database as db
                db.log_trade(
                    session_id=app.CURRENT_SESSION_ID,
                    instrument_key=instrument_key,
                    trading_symbol=f"{strike} {option_type} ({expiry})",
                    trade_type="BUY",
                    price=float(premium),
                    quantity=quantity,
                    stop_loss=0.0,
                    target_price=0.0,
                    reason=entry_reason or "Strategy Signal",
                    pnl=0.0,
                    execution_source=execution_source,
                    entry_reason=entry_reason,
                    quote_quality=quote_quality,
                    fill_diagnostics=fill_diagnostics,
                    timestamp=timestamp,
                    db_path=self.db_path or "valkyrie_trades.db"
                )
        except Exception as e:
            logger.error(f"Failed to log V2 BUY trade to SQLite: {e}")

        TelemetryLogger.log(
            "POSITION",
            "INFO",
            f"Opened Paper Position: {strike} {option_type} ({expiry}) | Qty: {quantity} | Premium: {premium:.2f} | Source: {execution_source} | Spot: {spot_price}",
            {
                "action": "open",
                "underlying": underlying,
                "strike": strike,
                "option_type": option_type,
                "expiry": expiry,
                "quantity": quantity,
                "premium": premium,
                "spot": spot_price,
                "execution_source": execution_source
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
        execution_source = getattr(self._local_state, 'last_source', "SYNTHETIC_MODEL")
        quote_quality = getattr(self._local_state, 'last_quote_quality', None)

        from v2.trade_explainer import TradeExplainer
        structured_exit_reason = TradeExplainer.explain_exit(exit_reason, active_pos.entry_premium, premium)

        pos_data = {
            "underlying": active_pos.underlying,
            "strike": active_pos.strike,
            "expiry": active_pos.expiry,
            "option_type": active_pos.option_type,
            "instrument_key": active_pos.instrument_key,
            "premium_price": float(premium),
            "signal": "SELL_INTENT",
            "execution_source": execution_source,
            "exit_reason": structured_exit_reason,
            "metadata": {
                "exit_reason": structured_exit_reason,
                "quote_quality": quote_quality
            }
        }

        pos_id = active_pos.position_id
        self.position_manager.close_position(pos_data, timestamp)

        # Get V2 accounting record
        accounting_record = self.position_manager.ledger.accounting_records[-1]

        # Compute Fill Diagnostics (Phase 6) - Hardened Real/Unavailable Diagnostics
        slippage_pct = None
        if execution_source == "LIVE_QUOTE" and quote_quality:
            bid = quote_quality.get("bid")
            if bid and bid > 0:
                # Real slippage relative to target bid:
                slippage_pct = round(((bid - premium) / bid) * 100, 4)

        fill_diagnostics = {
            "fill_price": float(premium),
            "quantity": int(active_pos.quantity),
            "premium": float(premium * active_pos.quantity),
            "brokerage": None,
            "slippage_pct": slippage_pct,
            "execution_latency_ms": None
        }

        # Incrementally log trade to SQLite db
        try:
            import app
            if getattr(app, 'CURRENT_SESSION_ID', None):
                import database as db
                db.log_trade(
                    session_id=app.CURRENT_SESSION_ID,
                    instrument_key=active_pos.instrument_key,
                    trading_symbol=f"{active_pos.strike} {active_pos.option_type} ({active_pos.expiry})",
                    trade_type="EXIT",
                    price=float(premium),
                    quantity=active_pos.quantity,
                    stop_loss=0.0,
                    target_price=0.0,
                    reason=structured_exit_reason,
                    pnl=accounting_record.net_pnl,
                    execution_source=execution_source,
                    exit_reason=structured_exit_reason,
                    quote_quality=quote_quality,
                    fill_diagnostics=fill_diagnostics,
                    timestamp=timestamp,
                    db_path=self.db_path or "valkyrie_trades.db"
                )
        except Exception as e:
            logger.error(f"Failed to log V2 EXIT trade to SQLite: {e}")

        TelemetryLogger.log(
            "POSITION",
            "INFO",
            f"Closed Paper Position: {active_pos.strike} {active_pos.option_type} ({active_pos.expiry}) | Premium: {premium:.2f} | Reason: {exit_reason} | Source: {execution_source} | Spot: {spot_price}",
            {
                "action": "close",
                "underlying": active_pos.underlying,
                "strike": active_pos.strike,
                "option_type": active_pos.option_type,
                "expiry": active_pos.expiry,
                "premium": premium,
                "reason": exit_reason,
                "spot": spot_price,
                "execution_source": execution_source
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
