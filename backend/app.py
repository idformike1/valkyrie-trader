import os
import sys
import json
import asyncio
import threading
import time
from datetime import datetime, timedelta
import socket
import urllib.parse
import urllib3.util.connection as urllib3_connection
import pandas as pd
import numpy as np
import requests
import httpx
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Force requests library to use IPv4 exclusively (resolves static IP mismatch on IPv6 networks)
def allowed_gai_family():
    return socket.AF_INET

urllib3_connection.allowed_gai_family = allowed_gai_family

# Resolve path mapping
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)
sys.path.append(os.path.join(ROOT_DIR, "backend"))

import database as db
import auth
from strategy_heikin_ashi_gar import HeikinAshiGarStrategy, FiveEmaScalpingStrategy, calculate_heikin_ashi
import MarketDataFeed_pb2 as pb

TOKEN_FILE = os.path.join(ROOT_DIR, "token.txt")
CSV_PATH = os.path.join(ROOT_DIR, "nifty_options.csv")
DB_PATH = os.path.join(ROOT_DIR, "valkyrie_trades.db")

# Proxy configuration for Upstox order API
PROXIES = {
    "http": "http://USER:PASS@STATIC_PROXY_IP:PORT",
    "https": "http://USER:PASS@STATIC_PROXY_IP:PORT",
}

STRATEGY_REGISTRY = {
    "heikin_ashi_gar": HeikinAshiGarStrategy,
    "five_ema_scalping": FiveEmaScalpingStrategy
}

CURRENT_SESSION_ID = None
current_v2_runner = None  # Active V2 RealtimeSignalRunner instance (set when engine_version=="v2")

# Initialize FastAPI App
app = FastAPI(title="Valkyrie Trading Strategy Daemon", version="2.0.0")

# Enable CORS for Next.js App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins or specify client url
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global System Telemetry State
SYSTEM_STATUS = {
    "state": "IDLE", 
    "mode": "NONE", 
    "balance": 100000.0,
    "initial_balance": 100000.0,
    "position": None,
    "instrument_key": None,
    "trading_symbol": None,
    "strike": None,
    "expiry": None,
    "option_type": None,
    "exchange": "NSE",
    "index_name": "NIFTY",
    "live_protection": False,
    "is_real_execution": False,
    "lot_size": 1,
    "lot_size_multiplier": 75,
    "spot_price": 0.0,
    "total_pnl": 0.0,
    "return_percent": 0.0,
    "max_drawdown": 0.0,
    "profit_factor": 0.0,
    "total_trades": 0,
    "win_rate": 0.0,
    "chart_interval": "1minute",
    "chart_type": "heikin_ashi",
    
    # Scalper targets
    "scalper_instrument_key": None,
    "scalper_trading_symbol": None,
    "scalper_lot_multiplier": 75,
    "scalper_option_type": None,
    "scalper_strike": None,
    "scalper_spot_price": 0.0,
    "option_chain": [],
    "quote_health": {
        "subscribed_contracts": 0,
        "live_quotes": 0,
        "stale_quotes": 0,
        "hit_rate": 100.0,
        "miss_rate": 0.0,
        "synthetic_fills": 0
    },
    "session_id": None,
    "session_start_timestamp": None,
    "current_server_time": None,
    "last_heartbeat": None
}

TRADE_LOGS = []
EVENT_LOGS = []
EQUITY_CURVE = []
HEIKIN_ASHI_CANDLES = []
GTT_ORDERS = []
ACTIVE_HEDGES = {}  # instrument_key -> {"stop_loss": SL, "target": TP, "qty": qty, "product": product, "side": side}

# List to keep track of active WebSocket connections for telemetry broadcasting
ws_connections: List[WebSocket] = []

def get_unix_timestamp(ts):
    if hasattr(ts, 'timestamp'):
        return int(ts.timestamp())
    elif isinstance(ts, str):
        try:
            return int(pd.to_datetime(ts).timestamp())
        except:
            return 0
    else:
        return 0

def log_event(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] [{level}] {msg}"
    EVENT_LOGS.append(formatted_msg)
    print(formatted_msg)
    # Trigger an async broadcast task
    asyncio.run_coroutine_threadsafe(broadcast_telemetry(), main_event_loop)

async def broadcast_telemetry():
    if not ws_connections:
        return
    
    update_telemetry_metrics()
    
    # Dynamically inject Option Chain and Quote Health info
    try:
        from v2.option_quote_cache import OptionQuoteCache
        from v2.quote_health import QuoteHealthTracker
        from v2.option_chain_manager import OptionChainManager
        import time
        
        chain_mgr = OptionChainManager()
        active_index = SYSTEM_STATUS.get("index_name", "NIFTY")
        
        live_chain = []
        if active_index in chain_mgr.current_atms:
            atm_strike = chain_mgr.current_atms[active_index]
            step = chain_mgr.STRIKE_STEPS.get(active_index, 100)
            strikes = [atm_strike + (offset * step) for offset in range(-2, 3)]
            
            from v2.resolvers import HistoricalExpiryResolver
            expiry_date = HistoricalExpiryResolver.resolve(active_index, datetime.now(), chain_mgr.expiry_mode)
            
            from v2.expired_contract_provider import HistoricalContractProvider
            provider = HistoricalContractProvider()
            
            now_ms = int(time.time() * 1000)
            
            for strike in strikes:
                ce_ltp = 0.0
                ce_age_ms = 0
                try:
                    ce_key = provider.resolve_contract(active_index, expiry_date, strike, "CE")
                    ce_quote = OptionQuoteCache.get(ce_key)
                    if ce_quote:
                        ce_ltp = ce_quote.ltp
                        ce_age_ms = max(0, now_ms - ce_quote.last_update_ms)
                except Exception:
                    pass
                
                pe_ltp = 0.0
                pe_age_ms = 0
                try:
                    pe_key = provider.resolve_contract(active_index, expiry_date, strike, "PE")
                    pe_quote = OptionQuoteCache.get(pe_key)
                    if pe_quote:
                        pe_ltp = pe_quote.ltp
                        pe_age_ms = max(0, now_ms - pe_quote.last_update_ms)
                except Exception:
                    pass
                
                live_chain.append({
                    "strike": float(strike),
                    "ce_ltp": float(ce_ltp),
                    "ce_age_ms": int(ce_age_ms),
                    "pe_ltp": float(pe_ltp),
                    "pe_age_ms": int(pe_age_ms)
                })
                
        SYSTEM_STATUS["option_chain"] = live_chain
        SYSTEM_STATUS["quote_health"] = QuoteHealthTracker.get_stats()
    except Exception as e:
        print(f"[Telemetry Warning] Option chain or quote health compute error: {e}")

    SYSTEM_STATUS["current_server_time"] = datetime.now().isoformat()
    SYSTEM_STATUS["last_heartbeat"] = datetime.now().isoformat()

    payload = {
      "status": SYSTEM_STATUS,
      "trades": TRADE_LOGS,
      "logs": EVENT_LOGS[-100:],  # Limit logs size in websocket transmission
      "candles": HEIKIN_ASHI_CANDLES[-300:],
      "gtt_orders": GTT_ORDERS,
      "equity_curve": EQUITY_CURVE
    }
    
    dead_connections = []
    for ws in ws_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            dead_connections.append(ws)
            
    for ws in dead_connections:
        if ws in ws_connections:
            ws_connections.remove(ws)

def load_upstox_token():
    paths = [
        os.path.join(ROOT_DIR, "backend", "token.txt"),
        os.path.join(ROOT_DIR, "token.txt")
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    tok = f.read().strip()
                    if tok:
                        return tok
            except Exception:
                pass
    return os.getenv("UPSTOX_ACCESS_TOKEN", "")

def sync_nifty_options_csv(force=False):
    stale = False
    if not os.path.exists(CSV_PATH):
        stale = True
    else:
        try:
            df = pd.read_csv(CSV_PATH)
            required_indices = {'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX'}
            existing_indices = set(df['name'].unique()) if 'name' in df.columns else set()
            if df.empty or 'expiry' not in df.columns or not required_indices.issubset(existing_indices):
                stale = True
            else:
                max_expiry_ts = df['expiry'].max()
                max_expiry_date = pd.to_datetime(max_expiry_ts, unit='ms')
                if max_expiry_date.date() < datetime.now().date():
                    stale = True
        except Exception:
            stale = True
            
    if stale or force:
        log_event("Local nifty_options.csv is missing or expired. Fetching fresh options chain...", "SYSTEM")
        try:
            url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
            df = pd.read_json(url, compression='gzip')
            options_df = df.loc[
                (df['segment'].isin(['NSE_FO', 'BSE_FO'])) & 
                (df['instrument_type'].isin(['CE', 'PE'])) &
                (df['name'].isin(['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX']))
            ].copy()
            # Exclude expired contracts
            options_df = options_df[pd.to_datetime(options_df['expiry'], unit='ms').dt.date >= datetime.now().date()]
            options_df.to_csv(CSV_PATH, index=False)
            log_event(f"Successfully saved {len(options_df)} active options to nifty_options.csv", "SYSTEM")
        except Exception as e:
            log_event(f"Failed to synchronize instruments: {e}", "ERROR")

def get_index_spot_price(underlying_key):
    token = load_upstox_token()
    if not token or not underlying_key:
        return 0.0
    encoded_key = urllib.parse.quote(underlying_key)
    url = f"https://api.upstox.com/v2/market-quote/ltp?instrument_key={encoded_key}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            colon_key = underlying_key.replace("|", ":")
            pipe_key = underlying_key.replace(":", "|")
            price = data.get(colon_key, {}).get("last_price", 0.0) or data.get(pipe_key, {}).get("last_price", 0.0)
            return float(price)
    except Exception as e:
        log_event(f"Error fetching spot price for {underlying_key}: {e}", "ERROR")
    return 0.0

def get_instrument_details(index_name, strike, expiry_str, option_type):
    if not os.path.exists(CSV_PATH):
        sync_nifty_options_csv()
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    mask = (df['name'] == index_name) & (df['strike_price'] == float(strike)) & (df['expiry_date'] == expiry_str) & (df['instrument_type'] == option_type)
    matches = df[mask]
    if matches.empty:
        raise ValueError(f"No contract matching {index_name} strike {strike}, expiry {expiry_str}, type {option_type}")
    row = matches.iloc[0]
    lot_sz = int(row.get('lot_size', 75))
    if pd.isna(lot_sz):
        lot_sz = 75
    return row['instrument_key'], row['trading_symbol'], lot_sz

def execute_order(instrument_token, quantity, transaction_type):
    token = load_upstox_token()
    if not token:
        log_event("Failed to place order: Missing access token.", "ERROR")
        return {"status": "ERROR", "message": "Access token missing"}
        
    url = "https://api.upstox.com/v2/order/place"
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json", 
        "Accept": "application/json"
    }
    payload = {
        "quantity": int(quantity),
        "product": "MIS",
        "validity": "DAY",
        "price": 0.0,
        "tag": "HA-GAR-ENGINE",
        "instrument_token": instrument_token,
        "order_type": "MARKET",
        "transaction_type": transaction_type,
        "disclosed_quantity": 0,
        "trigger_price": 0.0,
        "is_amo": False
    }
    try:
        log_event(f"Sending real Upstox market order: {transaction_type} {quantity} units of {instrument_token}", "ORDER")
        resp = requests.post(url, json=payload, headers=headers, timeout=10, proxies=PROXIES)
        data = resp.json()
        log_event(f"Upstox API Response Code: {resp.status_code} | Body: {json.dumps(data)}", "ORDER")
        return data
    except Exception as e:
        log_event(f"Order transmission exception: {e}", "ERROR")
        return {"status": "error", "message": str(e)}

def update_telemetry_metrics():
    global SYSTEM_STATUS, TRADE_LOGS, EQUITY_CURVE, EVENT_LOGS, current_v2_runner
    
    if current_v2_runner:
        from v2.position_models import PositionStatus
        from v2.metrics_engine import MetricsEngine
        from v2.telemetry_logger import TelemetryLogger
        
        v2_ledger = current_v2_runner.position_manager.ledger
        
        # 1. Active Position Mapping
        active_pos = current_v2_runner.position_manager.active_position
        if active_pos is not None:
            ltp = active_pos.metadata.get("last_premium", active_pos.entry_premium)
            rm = current_v2_runner.config.risk_management
            entry_premium = active_pos.entry_premium
            
            stop_loss_price = 0.0
            if rm.stop_loss_value > 0:
                sl_pct = rm.stop_loss_value / 100.0 if rm.stop_loss_type == "percent" else 0.0
                sl_pts = rm.stop_loss_value if rm.stop_loss_type == "points" else (entry_premium * sl_pct)
                stop_loss_price = entry_premium - sl_pts
                
            target_price = 0.0
            if rm.target_value > 0:
                t_pct = rm.target_value / 100.0 if rm.target_type == "percent" else 0.0
                t_pts = rm.target_value if rm.target_type == "points" else (entry_premium * t_pct)
                target_price = entry_premium + t_pts
                
            SYSTEM_STATUS["position"] = {
                "instrument_key": active_pos.instrument_key,
                "trading_symbol": f"{active_pos.strike} {active_pos.option_type} ({active_pos.expiry})",
                "entry_price": active_pos.entry_premium,
                "timestamp": active_pos.entry_time.isoformat() if hasattr(active_pos.entry_time, 'isoformat') else str(active_pos.entry_time),
                "stop_loss": stop_loss_price,
                "target_price": target_price,
                "trailing_gap": rm.trailing_sl_gap,
                "highest_price": active_pos.metadata.get("highest_premium", entry_premium),
                "total_qty": active_pos.quantity,
                "qty": active_pos.quantity,
                "ltp": ltp,
                "pnl": round((ltp - entry_premium) * active_pos.quantity, 2),
                "side": "BUY"
            }
        else:
            SYSTEM_STATUS["position"] = None
            
        # 2. Trade Mapping
        temp_trades = []
        for pos in v2_ledger.positions:
            buy_time = pos.entry_time.isoformat() if hasattr(pos.entry_time, 'isoformat') else str(pos.entry_time)
            temp_trades.append({
                "id": f"v2_buy_{pos.position_id}",
                "session_id": CURRENT_SESSION_ID or 0,
                "instrument_key": pos.instrument_key,
                "trading_symbol": f"{pos.strike} {pos.option_type} ({pos.expiry})",
                "type": "BUY",
                "price": pos.entry_premium,
                "quantity": pos.quantity,
                "sl": 0.0,
                "target": 0.0,
                "reason": "Strategy Signal",
                "pnl": 0.0,
                "timestamp": buy_time,
                "upstox_order_id": ""
            })
            
            if pos.status == PositionStatus.CLOSED or pos.exit_time is not None:
                matching = next((r for r in v2_ledger.accounting_records if r.position_id == pos.position_id), None)
                net_pnl = matching.net_pnl if matching else 0.0
                exit_time = pos.exit_time.isoformat() if hasattr(pos.exit_time, 'isoformat') else str(pos.exit_time)
                temp_trades.append({
                    "id": f"v2_exit_{pos.position_id}",
                    "session_id": CURRENT_SESSION_ID or 0,
                    "instrument_key": pos.instrument_key,
                    "trading_symbol": f"{pos.strike} {pos.option_type} ({pos.expiry})",
                    "type": "EXIT",
                    "price": pos.exit_premium if pos.exit_premium is not None else 0.0,
                    "quantity": pos.quantity,
                    "sl": 0.0,
                    "target": 0.0,
                    "reason": pos.exit_signal or "Target/SL Hit",
                    "pnl": net_pnl,
                    "timestamp": exit_time,
                    "upstox_order_id": ""
                })
        TRADE_LOGS = temp_trades
        
        # 3. Metrics & Equity Curve Mapping
        initial_capital = SYSTEM_STATUS["initial_balance"]
        metrics_engine = MetricsEngine(initial_capital=initial_capital)
        report = metrics_engine.calculate_metrics(v2_ledger.positions, v2_ledger.accounting_records)
        
        SYSTEM_STATUS["balance"] = initial_capital + report.performance.net_profit
        SYSTEM_STATUS["total_pnl"] = report.performance.net_profit
        SYSTEM_STATUS["return_percent"] = (report.performance.net_profit / initial_capital) * 100
        SYSTEM_STATUS["max_drawdown"] = report.max_drawdown
        SYSTEM_STATUS["win_rate"] = report.trade_stats.win_rate
        SYSTEM_STATUS["profit_factor"] = report.performance.profit_factor
        SYSTEM_STATUS["total_trades"] = report.trade_stats.total_trades
        SYSTEM_STATUS["sharpe_ratio"] = report.sharpe_ratio
        SYSTEM_STATUS["sortino_ratio"] = report.sortino_ratio
        
        EQUITY_CURVE = [
            {
                "timestamp": pt.timestamp.isoformat() if hasattr(pt.timestamp, 'isoformat') else str(pt.timestamp),
                "equity": pt.equity_value
            } for pt in report.equity_curve
        ]
        
        # 4. Runtime Logs Mapping
        v2_raw_logs = TelemetryLogger.get_logs()
        v2_formatted = []
        for log in v2_raw_logs:
            try:
                time_part = log.timestamp.split('T')[1][:8]
            except Exception:
                time_part = datetime.now().strftime("%H:%M:%S")
            v2_formatted.append(f"[{time_part}] [{log.category}:{log.severity}] {log.message}")
        EVENT_LOGS = v2_formatted
        return

    if CURRENT_SESSION_ID:
        TRADE_LOGS = db.get_session_trades(CURRENT_SESSION_ID, DB_PATH)
        EQUITY_CURVE = db.get_session_equity_curve(CURRENT_SESSION_ID, SYSTEM_STATUS["initial_balance"], DB_PATH)
        
    if not TRADE_LOGS:
        return
    
    total_pnl = sum(t['pnl'] for t in TRADE_LOGS if 'pnl' in t)
    SYSTEM_STATUS["total_pnl"] = total_pnl
    SYSTEM_STATUS["return_percent"] = (total_pnl / SYSTEM_STATUS["initial_balance"]) * 100
    
    # Calculate Max Drawdown
    peak = SYSTEM_STATUS["initial_balance"]
    max_dd = 0.0
    for pt in EQUITY_CURVE:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    SYSTEM_STATUS["max_drawdown"] = max_dd
    
    # Win rate & Profit factor
    exits = [t for t in TRADE_LOGS if t['type'] == 'EXIT']
    total_trades = len(exits)
    SYSTEM_STATUS["total_trades"] = total_trades
    
    pnl_list = [t['pnl'] for t in exits if 'pnl' in t]
    
    if total_trades > 0:
        wins = sum(1 for t in exits if t['pnl'] > 0)
        SYSTEM_STATUS["win_rate"] = (wins / total_trades) * 100
        
        gains = sum(t['pnl'] for t in exits if t['pnl'] > 0)
        losses = abs(sum(t['pnl'] for t in exits if t['pnl'] < 0))
        SYSTEM_STATUS["profit_factor"] = (gains / losses) if losses > 0 else (gains if gains > 0 else 0.0)
        
        # Sharpe ratio
        if len(pnl_list) >= 2:
            std_val = np.std(pnl_list)
            SYSTEM_STATUS["sharpe_ratio"] = float(np.mean(pnl_list) / std_val) if std_val > 0 else 0.0
        else:
            SYSTEM_STATUS["sharpe_ratio"] = 0.0
            
        # Consecutive win/loss streaks
        consec_wins = 0
        consec_losses = 0
        max_wins = 0
        max_losses = 0
        for pnl in pnl_list:
            if pnl > 0:
                consec_wins += 1
                consec_losses = 0
                if consec_wins > max_wins:
                    max_wins = consec_wins
            elif pnl < 0:
                consec_losses += 1
                consec_wins = 0
                if consec_losses > max_losses:
                    max_losses = consec_losses
        SYSTEM_STATUS["max_consec_wins"] = max_wins
        SYSTEM_STATUS["max_consec_losses"] = max_losses
    else:
        SYSTEM_STATUS["sharpe_ratio"] = 0.0
        SYSTEM_STATUS["max_consec_wins"] = 0
        SYSTEM_STATUS["max_consec_losses"] = 0

class EngineAccount:
    def __init__(self, initial_balance=100000.0, is_real=False, lot_size=1, lot_size_multiplier=75, brokerage_flat=20.0, slippage_pct=0.05):
        self.is_real = is_real
        self.lot_size = lot_size
        self.lot_size_multiplier = lot_size_multiplier
        self.qty = lot_size * lot_size_multiplier
        self.position = None
        self.entry_price = 0.0
        self.brokerage_flat = brokerage_flat
        self.slippage_pct = slippage_pct
        self.buy_cost = 0.0
        self.buy_reject_reason = ""
        
    def buy(self, instrument_key, price, timestamp, stop_loss=0.0, details=""):
        if self.position and self.position != instrument_key:
            reason = f"Already in {self.position}. Close it first before switching instruments."
            log_event(f"REJECTED: {reason}", "WARNING")
            self.buy_reject_reason = reason
            return False
            
        new_qty = self.qty
        buy_cost = self.brokerage_flat + (price * (self.slippage_pct / 100.0) * new_qty)
        required_capital = (price * new_qty) + buy_cost
        
        if SYSTEM_STATUS["balance"] < required_capital:
            reason = f"Insufficient funds. Required: ₹{required_capital:.2f}, Available: ₹{SYSTEM_STATUS['balance']:.2f}"
            log_event(f"REJECTED: {reason}", "WARNING")
            self.buy_reject_reason = reason
            return False
            
        if self.position:
            # Scale in / average entry price
            total_qty = self.qty + new_qty
            self.entry_price = ((self.entry_price * self.qty) + (price * new_qty)) / total_qty
            self.qty = total_qty
            self.buy_cost += buy_cost
            log_msg = f"Position scaled in. Total Qty: {self.qty} @ Avg Price: ₹{self.entry_price:.2f}"
        else:
            self.position = instrument_key
            self.entry_price = price
            self.qty = new_qty
            self.buy_cost = buy_cost
            log_msg = f"Position opened. BUY {self.qty} @ ₹{price:.2f} | Cost: ₹{self.buy_cost:.2f} | SL: ₹{stop_loss:.2f}"
            
        SYSTEM_STATUS["balance"] -= buy_cost
        
        SYSTEM_STATUS["position"] = {
            "instrument_key": instrument_key,
            "entry_price": self.entry_price,
            "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
            "stop_loss": stop_loss
        }
        
        if CURRENT_SESSION_ID:
            db.log_trade(
                session_id=CURRENT_SESSION_ID,
                instrument_key=instrument_key,
                trading_symbol=SYSTEM_STATUS.get("trading_symbol", "UNKNOWN"),
                trade_type="BUY",
                price=price,
                quantity=new_qty,
                stop_loss=stop_loss,
                target_price=0.0,
                reason="SIGNAL_TRIGGER",
                pnl=0.0,
                timestamp=timestamp,
                db_path=DB_PATH
            )
            global TRADE_LOGS
            TRADE_LOGS = db.get_session_trades(CURRENT_SESSION_ID, DB_PATH)
        else:
            TRADE_LOGS.append({
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, 'strftime') else str(timestamp),
                "type": "BUY",
                "price": price,
                "sl": stop_loss,
                "reason": "SIGNAL_TRIGGER",
                "details": details
            })
        log_event(log_msg, "TRADE")
        
        if self.is_real:
            execute_order(instrument_key, new_qty, "BUY")
        return True

    def sell(self, instrument_key, price, timestamp, reason, details=""):
        if not self.position or self.position != instrument_key:
            return False
            
        sell_cost = self.brokerage_flat + (price * (self.slippage_pct / 100.0) * self.qty)
        SYSTEM_STATUS["balance"] -= sell_cost
        
        gross_pnl = (price - self.entry_price) * self.qty
        SYSTEM_STATUS["balance"] += gross_pnl
        net_pnl = gross_pnl - (self.buy_cost + sell_cost)
        
        if CURRENT_SESSION_ID:
            db.log_trade(
                session_id=CURRENT_SESSION_ID,
                instrument_key=instrument_key,
                trading_symbol=SYSTEM_STATUS.get("trading_symbol", "UNKNOWN"),
                trade_type="EXIT",
                price=price,
                quantity=self.qty,
                stop_loss=0.0,
                target_price=0.0,
                reason=reason,
                pnl=net_pnl,
                timestamp=timestamp,
                db_path=DB_PATH
            )
            global TRADE_LOGS, EQUITY_CURVE
            TRADE_LOGS = db.get_session_trades(CURRENT_SESSION_ID, DB_PATH)
            EQUITY_CURVE = db.get_session_equity_curve(CURRENT_SESSION_ID, SYSTEM_STATUS["initial_balance"], DB_PATH)
        else:
            TRADE_LOGS.append({
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, 'strftime') else str(timestamp),
                "type": "EXIT",
                "price": price,
                "reason": reason,
                "pnl": net_pnl,
                "details": details
            })
            EQUITY_CURVE.append({
                "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                "equity": SYSTEM_STATUS["balance"]
            })
        log_event(f"Position closed. SELL {self.qty} @ ₹{price:.2f} | Net P&L: ₹{net_pnl:.2f} (Gross: ₹{gross_pnl:.2f}, Cost: ₹{self.buy_cost + sell_cost:.2f}) | Reason: {reason}", "TRADE")
        
        if self.is_real:
            execute_order(instrument_key, self.qty, "SELL")
            
        self.position = None
        self.entry_price = 0.0
        SYSTEM_STATUS["position"] = None
        
        update_telemetry_metrics()
        return True

class LiveFeed:
    def __init__(self, instrument_key, strategy_engine, account, scalper_key=None):
        self.instrument_key = instrument_key
        self.scalper_key = scalper_key or instrument_key
        self.strategy = strategy_engine
        self.account = account
        self.current_candle = None
        self.candles_history = []
        self.running = True
        self.ws = None
        self.interval = SYSTEM_STATUS.get("chart_interval", "1minute")
        # Candle observer registry — thread-safe list of callables
        self._candle_listeners = []
        self._candle_listeners_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Candle Observer API
    # ------------------------------------------------------------------
    def register_candle_listener(self, callback):
        """Register a callable to be notified on every completed candle.

        The callback signature must be: callback(candle: dict) -> None
        Callbacks are invoked synchronously inside on_candle_close before
        V1 strategy evaluation, so they should be fast and non-blocking.
        """
        with self._candle_listeners_lock:
            if callback not in self._candle_listeners:
                self._candle_listeners.append(callback)
                log_event(f"Candle listener registered: {getattr(callback, '__qualname__', repr(callback))}", "ENGINE")

    def unregister_candle_listener(self, callback):
        """Remove a previously registered candle listener."""
        with self._candle_listeners_lock:
            if callback in self._candle_listeners:
                self._candle_listeners.remove(callback)
                log_event(f"Candle listener unregistered: {getattr(callback, '__qualname__', repr(callback))}", "ENGINE")

    def _notify_candle_listeners(self, candle):
        """Fan-out a completed candle to all registered listeners."""
        with self._candle_listeners_lock:
            listeners = list(self._candle_listeners)
        for cb in listeners:
            try:
                cb(candle)
            except Exception as exc:
                log_event(f"Candle listener error in {getattr(cb, '__qualname__', repr(cb))}: {exc}", "ERROR")

    async def get_websocket_uri(self):
        token = load_upstox_token()
        if not token:
            raise Exception("Access token missing in token.txt")
        url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data['data']['authorizedRedirectUri'] or data['data']['authorized_redirect_uri']

    async def connect(self):
        try:
            uri = await self.get_websocket_uri()
        except Exception as e:
            log_event(f"WebSocket auth failed: {e}", "ERROR")
            SYSTEM_STATUS["state"] = "FAILED"
            return
            
        log_event("Connecting to Upstox Market Stream...", "WS")
        async with websockets.connect(uri, max_size=2**25) as ws:
            self.ws = ws
            
            try:
                to_date = datetime.now()
                from_date = to_date - timedelta(days=3)
                active_int = SYSTEM_STATUS.get("chart_interval", "1minute")
                hist = fetch_historical_candles(self.instrument_key, '1minute', from_date, to_date)
                if active_int in ["5minute", "15minute"]:
                    hist = resample_candles(hist, active_int)
                self.candles_history = hist[-100:]
                
                rebuild_telemetry_candles()
                log_event(f"Pre-populated {len(HEIKIN_ASHI_CANDLES)} candles from history ({active_int}).", "WS")
            except Exception as e:
                log_event(f"Failed to pre-populate candles: {e}", "WARNING")

            keys_to_subscribe = list(filter(None, list(set([self.instrument_key, self.scalper_key]))))
            subscribe_msg = {
                "guid": "valkyrie_heikin_ashi_gar",
                "method": "sub",
                "data": {"mode": "full", "instrumentKeys": keys_to_subscribe}
            }
            await ws.send(json.dumps(subscribe_msg).encode('utf-8'))
            log_event(f"Subscribed to market feed for: {keys_to_subscribe}", "WS")
            SYSTEM_STATUS["state"] = "LIVE_MONITORING"
            
            # Record connect time
            global SESSION_START_TIME
            SESSION_START_TIME = time.time()
            
            while self.running:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    await self.process_message(message)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    log_event("WebSocket closed, attempting reconnection...", "WARNING")
                    break

    async def subscribe_to_keys(self, keys_list):
        if self.ws and self.ws.state.name == 'OPEN':
            subscribe_msg = {
                "guid": "valkyrie_heikin_ashi_gar",
                "method": "sub",
                "data": {"mode": "full", "instrumentKeys": keys_list}
            }
            await self.ws.send(json.dumps(subscribe_msg).encode('utf-8'))
            log_event(f"Subscribed dynamically to market feeds: {keys_list}", "WS")
        else:
            log_event(f"Cannot subscribe to keys {keys_list}: WebSocket is closed or not initialized.", "WARNING")

    async def unsubscribe_from_keys(self, keys_list):
        if self.ws and self.ws.state.name == 'OPEN':
            unsubscribe_msg = {
                "guid": "valkyrie_heikin_ashi_gar",
                "method": "unsub",
                "data": {"mode": "full", "instrumentKeys": keys_list}
            }
            await self.ws.send(json.dumps(unsubscribe_msg).encode('utf-8'))
            log_event(f"Unsubscribed dynamically from market feeds: {keys_list}", "WS")
        else:
            log_event(f"Cannot unsubscribe from keys {keys_list}: WebSocket is closed or not initialized.", "WARNING")


    async def process_message(self, raw_message):
        try:
            feed = pb.FeedResponse()
            feed.ParseFromString(raw_message)
            for key, feed_data in feed.feeds.items():
                price = None
                bid = None
                ask = None
                vol = None
                oi = None
                ltt = None

                if feed_data.HasField("fullFeed"):
                    full_feed = feed_data.fullFeed
                    if full_feed.HasField("marketFF"):
                        market_ff = full_feed.marketFF
                        price = market_ff.ltpc.ltp
                        ltt = market_ff.ltpc.ltt
                        vol = int(market_ff.vtt) if hasattr(market_ff, 'vtt') and market_ff.vtt else None
                        oi = float(market_ff.oi) if hasattr(market_ff, 'oi') and market_ff.oi else None
                        if market_ff.HasField("marketLevel") and market_ff.marketLevel.bidAskQuote:
                            first_q = market_ff.marketLevel.bidAskQuote[0]
                            bid = float(first_q.bidP) if first_q.bidP else None
                            ask = float(first_q.askP) if first_q.askP else None
                    elif full_feed.HasField("indexFF"):
                        price = full_feed.indexFF.ltpc.ltp
                        ltt = full_feed.indexFF.ltpc.ltt
                elif feed_data.HasField("firstLevelWithGreeks"):
                    flg = feed_data.firstLevelWithGreeks
                    price = flg.ltpc.ltp
                    ltt = flg.ltpc.ltt
                    vol = int(flg.vtt) if hasattr(flg, 'vtt') and flg.vtt else None
                    oi = float(flg.oi) if hasattr(flg, 'oi') and flg.oi else None
                    if flg.HasField("firstDepth"):
                        bid = float(flg.firstDepth.bidP) if flg.firstDepth.bidP else None
                        ask = float(flg.firstDepth.askP) if flg.firstDepth.askP else None
                elif feed_data.HasField("ltpc"):
                    price = feed_data.ltpc.ltp
                    ltt = feed_data.ltpc.ltt

                if price is not None:
                    # Update option quote cache
                    dt_ts = None
                    if ltt:
                        try:
                            dt_ts = datetime.fromtimestamp(ltt / 1000.0)
                        except Exception:
                            pass
                    
                    from v2.option_quote_cache import OptionQuoteCache
                    OptionQuoteCache.update(
                        instrument_key=key,
                        ltp=float(price),
                        bid=bid,
                        ask=ask,
                        volume=vol,
                        oi=oi,
                        timestamp=dt_ts
                    )

                if price:
                    if key == self.instrument_key:
                        SYSTEM_STATUS["spot_price"] = price
                        self.on_tick(price, datetime.now())
                        try:
                            from v2.option_chain_manager import OptionChainManager
                            OptionChainManager().on_spot_update(key, price)
                        except Exception as e:
                            log_event(f"OptionChainManager spot update error: {e}", "WARNING")
                    if key == self.scalper_key:
                        SYSTEM_STATUS["scalper_spot_price"] = price
                        self.on_scalper_tick(price, datetime.now())
        except Exception as e:
            log_event(f"Protobuf processing error: {e}", "ERROR")

    def on_scalper_tick(self, price, timestamp):
        if self.account.position and SYSTEM_STATUS.get("position"):
            pos = SYSTEM_STATUS["position"]
            if pos.get("is_scalper") and pos["instrument_key"] == self.scalper_key:
                target_price = pos.get("target_price", 0.0)
                stop_loss_price = pos.get("stop_loss", 0.0)
                
                if stop_loss_price > 0.0 and price <= stop_loss_price:
                    details = f"Stop Loss triggered. LTP ₹{price:.2f} touched SL level of ₹{stop_loss_price:.2f}."
                    self.account.sell(self.scalper_key, price, timestamp, "STOP_LOSS", details=details)
                    self.strategy.reset_state()
                elif target_price > 0.0 and price >= target_price:
                    details = f"Target Limit triggered. LTP ₹{price:.2f} touched Target level of ₹{target_price:.2f}."
                    self.account.sell(self.scalper_key, price, timestamp, "TARGET_LIMIT", details=details)
                    self.strategy.reset_state()

    def on_tick(self, price, timestamp):
        interval = getattr(self, "interval", "1minute")
        if interval == "10s":
            current_bucket = timestamp.replace(second=(timestamp.second // 10) * 10, microsecond=0)
        elif interval == "30s":
            current_bucket = timestamp.replace(second=(timestamp.second // 30) * 30, microsecond=0)
        elif interval == "1minute":
            current_bucket = timestamp.replace(second=0, microsecond=0)
        elif interval == "5minute":
            current_bucket = timestamp.replace(minute=(timestamp.minute // 5) * 5, second=0, microsecond=0)
        elif interval == "15minute":
            current_bucket = timestamp.replace(minute=(timestamp.minute // 15) * 15, second=0, microsecond=0)
        else:
            current_bucket = timestamp.replace(second=0, microsecond=0)
        
        # Check targets/stop-losses
        if self.account.position and SYSTEM_STATUS.get("position"):
            pos = SYSTEM_STATUS["position"]
            if not pos.get("is_scalper") and pos["instrument_key"] == self.instrument_key:
                trailing_gap = pos.get("trailing_gap", 0.0)
                if trailing_gap > 0.0:
                    highest_price = pos.get("highest_price", 0.0)
                    if highest_price <= 0.0:
                        highest_price = pos.get("entry_price", price)
                        pos["highest_price"] = highest_price
                    
                    if price > highest_price:
                        steps = int((price - highest_price) / trailing_gap)
                        if steps > 0:
                            pos["highest_price"] = highest_price + steps * trailing_gap
                            pos["stop_loss"] = pos.get("stop_loss", 0.0) + steps * trailing_gap
                            log_event(f"Trailing SL adjusted to ₹{pos['stop_loss']:.2f} (LTP: ₹{price:.2f})", "SYSTEM")

                target_price = pos.get("target_price", 0.0)
                stop_loss_price = pos.get("stop_loss", 0.0)
                
                if stop_loss_price > 0.0 and price <= stop_loss_price:
                    details = f"Stop Loss triggered. LTP ₹{price:.2f} touched SL level of ₹{stop_loss_price:.2f}."
                    self.account.sell(self.instrument_key, price, timestamp, "STOP_LOSS", details=details)
                    self.strategy.reset_state()
                elif target_price > 0.0 and price >= target_price:
                    details = f"Target Limit triggered. LTP ₹{price:.2f} touched Target level of ₹{target_price:.2f}."
                    self.account.sell(self.instrument_key, price, timestamp, "TARGET_LIMIT", details=details)
                    self.strategy.reset_state()
        elif self.account.position and not SYSTEM_STATUS.get("position", {}).get("is_scalper"):
            if price <= self.strategy.stop_loss_level:
                entry_sl = self.strategy.stop_loss_level
                details = f"Stop Loss triggered. Live price ₹{price:.2f} touched SL level of ₹{entry_sl:.2f}."
                self.account.sell(self.instrument_key, price, timestamp, "STOP_LOSS", details=details)
                self.strategy.reset_state()
                
        # Check pending GTT orders
        global GTT_ORDERS
        for order in GTT_ORDERS:
            if order["status"] == "PENDING":
                trigger_met = False
                tp = order["trigger_price"]
                direction = order.get("direction", "ABOVE")
                
                if direction == "ABOVE" and price >= tp:
                    trigger_met = True
                elif direction == "BELOW" and price <= tp:
                    trigger_met = True
                    
                if trigger_met:
                    order["status"] = "TRIGGERED"
                    log_event(f"GTT Trigger Met: {order['side']} {order['qty']} Lots at LTP ₹{price:.2f}", "SYSTEM")
                    if order["side"] == "BUY":
                        self.account.lot_size = order["qty"]
                        self.account.qty = order["qty"] * self.account.lot_size_multiplier
                        SYSTEM_STATUS["lot_size"] = order["qty"]
                        
                        success = self.account.buy(
                            instrument_key=self.instrument_key,
                            price=price,
                            timestamp=timestamp,
                            stop_loss=0.0,
                            details="GTT_TRIGGER"
                        )
                        if success:
                            target_price = 0.0
                            stop_loss_price = 0.0
                            target = order["target"]
                            target_type = order["target_type"]
                            stop_loss = order["stop_loss"]
                            stop_loss_type = order["stop_loss_type"]
                            
                            if target > 0.0:
                                if target_type == "points":
                                    target_price = price + target
                                elif target_type == "percent":
                                    target_price = price * (1.0 + target / 100.0)
                                    
                            if stop_loss > 0.0:
                                if stop_loss_type == "points":
                                    stop_loss_price = price - stop_loss
                                elif stop_loss_type == "percent":
                                    stop_loss_price = price * (1.0 - stop_loss / 100.0)
                                    
                            if SYSTEM_STATUS["position"]:
                                SYSTEM_STATUS["position"]["target_price"] = target_price
                                SYSTEM_STATUS["position"]["stop_loss"] = stop_loss_price
                                SYSTEM_STATUS["position"]["trailing_gap"] = order.get("trailing_gap", 0.0)
                                SYSTEM_STATUS["position"]["highest_price"] = price
                    else:
                        self.account.sell(
                            instrument_key=self.instrument_key,
                            price=price,
                            timestamp=timestamp,
                            reason="GTT_EXIT",
                            details="GTT Trigger Exit"
                        )
            
        if self.current_candle is None or self.current_candle['timestamp'] != current_bucket:
            if self.current_candle is not None:
                self.on_candle_close(self.current_candle)
            self.current_candle = {
                'timestamp': current_bucket,
                'open': price,
                'high': price,
                'low': price,
                'close': price
            }
        else:
            self.current_candle['high'] = max(self.current_candle['high'], price)
            self.current_candle['low'] = min(self.current_candle['low'], price)
            self.current_candle['close'] = price
            
        rebuild_telemetry_candles()

    def on_candle_close(self, candle):
        self.candles_history.append(candle)
        interval = getattr(self, "interval", "1minute")
        log_event(f"Candle closed ({interval}): {candle['timestamp'].strftime('%H:%M:%S')} | O: {candle['open']} H: {candle['high']} L: {candle['low']} C: {candle['close']}", "ENGINE")
        
        rebuild_telemetry_candles()

        # --- CANDLE OBSERVER NOTIFICATION ---
        # Notify all registered listeners (e.g. V2 RealtimeSignalRunner) FIRST.
        # Listeners receive the closed candle dict directly and execute their own
        # signal/risk logic independently from the V1 strategy path.
        self._notify_candle_listeners(candle)

        if len(self.candles_history) < 3:
            return
            
        df = pd.DataFrame(self.candles_history)
        
        if SYSTEM_STATUS["mode"] == "MANUAL":
            return

        # --- V1 STRATEGY EVALUATION ---
        # Only executed when the active engine is V1 (no V2 runner attached).
        # If a V2 runner is registered as a listener, we skip V1 to prevent
        # double execution and conflicting account state.
        global current_v2_runner
        if current_v2_runner is not None:
            return
            
        signal, meta = self.strategy.evaluate(df)
        
        if signal == "BUY":
            stop_loss = meta.get("stop_loss", 0.0)
            target = meta.get("target_price", 0.0)
            details = meta.get("details", "")
            
            if not details:
                if isinstance(self.strategy, HeikinAshiGarStrategy):
                    prior_ha_open = meta.get("prior_ha_open", 0.0)
                    prior_ha_close = meta.get("prior_ha_close", 0.0)
                    comp_ha_open = meta.get("comp_ha_open", 0.0)
                    comp_ha_close = meta.get("comp_ha_close", 0.0)
                    comp_ha_low = meta.get("comp_ha_low", 0.0)
                    comp_ha_open_low_diff = abs(comp_ha_open - comp_ha_low)
                    details = (
                        f"GAR Pattern confirmed. Prior RED HA candle closed (O: ₹{prior_ha_open:.2f}, C: ₹{prior_ha_close:.2f}). "
                        f"Completed GREEN HA candle closed (O: ₹{comp_ha_open:.2f}, C: ₹{comp_ha_close:.2f}) "
                        f"with bottom-wick low deviation of {comp_ha_open_low_diff:.3f}. "
                        f"Stop Loss anchored at prior raw candle open (₹{stop_loss:.2f})."
                    )
                else:
                    details = f"5 EMA Scalping entry at ₹{candle['close']:.2f}. SL: ₹{stop_loss:.2f}, Target: ₹{target:.2f}."
            
            self.account.buy(self.instrument_key, candle['close'], candle['timestamp'], stop_loss=stop_loss, details=details)
            self.strategy.stop_loss_level = stop_loss
            if target > 0.0:
                self.strategy.target_level = target
                
        elif signal == "EXIT":
            reason = meta.get("reason", "TECHNICAL_REVERSAL")
            details = meta.get("details", "")
            if not details:
                if reason == "TECHNICAL_REVERSAL":
                    details = (
                        f"Technical trend reversal detected. Completed Heikin Ashi candle closed RED "
                        f"(Open: ₹{meta.get('ha_open', 0.0):.2f}, Close: ₹{meta.get('ha_close', 0.0):.2f})."
                    )
                elif reason == "MAX_DURATION":
                    details = f"Maximum candle limit reached. Position held for {self.strategy.candles_held} candles."
                elif reason == "SESSION_END":
                    details = f"Intraday cutoff triggered at candle close time {candle['timestamp'].strftime('%H:%M')}."
                elif reason == "STOP_LOSS":
                    details = f"Stop Loss triggered at ₹{candle['close']:.2f}."
                elif reason == "TARGET_LIMIT":
                    details = f"Target Limit hit at ₹{candle['close']:.2f}."
                    
            self.account.sell(self.instrument_key, candle['close'], candle['timestamp'], reason, details=details)

    def stop(self):
        self.running = False

def fetch_historical_candles(instrument_key, interval, from_date, to_date):
    if not instrument_key:
        return []
    token = load_upstox_token()
    if not token:
        raise Exception("Access token missing in token.txt")
    
    encoded_key = urllib.parse.quote(instrument_key)
    candles = []
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    
    # 1. Fetch live intraday candles (includes today's current day candles)
    url_intra = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded_key}/{interval}"
    try:
        resp = requests.get(url_intra, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            candles_data = data.get('data', {}).get('candles', [])
            for c in candles_data:
                ts = datetime.fromisoformat(c[0].replace('Z', '+00:00'))
                candles.append({
                    'timestamp': ts,
                    'open': float(c[1]),
                    'high': float(c[2]),
                    'low': float(c[3]),
                    'close': float(c[4]),
                    'volume': float(c[5]) if len(c) > 5 else 0.0
                })
    except Exception as e:
        log_event(f"Intraday candle fetch failed: {e}", "WARNING")

    # 2. Fetch historical candles for past days
    url_hist = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/{interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
    try:
        resp = requests.get(url_hist, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            candles_data = data.get('data', {}).get('candles', [])
            for c in candles_data:
                ts = datetime.fromisoformat(c[0].replace('Z', '+00:00'))
                # Avoid duplicates
                if not any(x['timestamp'] == ts for x in candles):
                    candles.append({
                        'timestamp': ts,
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': float(c[5]) if len(c) > 5 else 0.0
                    })
        else:
            if "Invalid Instrument key" in resp.text or "UDAPI100011" in resp.text:
                log_event("Historical candles not supported for expired/invalid contract.", "WARNING")
    except Exception as e:
        log_event(f"Historical candle fetch failed: {e}", "WARNING")

    # Sort candles ascending by timestamp
    candles = sorted(candles, key=lambda x: x['timestamp'])
    return candles

def resample_candles(candles, target_interval):
    if target_interval not in ['5minute', '15minute']:
        return candles
    rule_map = {'5minute': '5min', '15minute': '15min'}
    rule = rule_map[target_interval]
    df = pd.DataFrame(candles)
    df.set_index('timestamp', inplace=True)
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }
    if 'volume' in df.columns:
        agg_dict['volume'] = 'sum'
    ohlc = df.resample(rule).agg(agg_dict).dropna()
    ohlc.reset_index(inplace=True)
    return ohlc.to_dict('records')

def parse_predefined_period(period_type, start_date_str=None, end_date_str=None):
    today = datetime.now()
    if period_type == 'last_week':
        start = today - timedelta(days=7)
        return start, today
    elif period_type == 'last_month':
        start = today - timedelta(days=30)
        return start, today
    elif period_type == 'last_3_months':
        start = today - timedelta(days=90)
        return start, today
    elif period_type == 'last_6_months':
        start = today - timedelta(days=180)
        return start, today
    elif period_type == 'ytd':
        start = datetime(today.year, 1, 1)
        return start, today
    elif period_type == 'custom' or not period_type:
        if start_date_str:
            if isinstance(start_date_str, datetime):
                start = start_date_str
            else:
                start = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            start = today - timedelta(days=7)
        if end_date_str:
            if isinstance(end_date_str, datetime):
                end = end_date_str
            else:
                end = datetime.strptime(end_date_str, "%Y-%m-%d")
            end = end.replace(hour=23, minute=59, second=59)
        else:
            end = today
        return start, end
    return today - timedelta(days=7), today

def run_historical_backtest(instrument_key, lot_size, start_date, end_date, timeframe, max_candles, cutoff_time, brokerage_flat, slippage_pct, initial_balance, strategy_name="heikin_ashi_gar", strategy_params=None):
    global TRADE_LOGS, EQUITY_CURVE, HEIKIN_ASHI_CANDLES, CURRENT_SESSION_ID
    log_event(f"Historical backtest sequence started for strategy: {strategy_name}...", "BACKTEST")
    
    CURRENT_SESSION_ID = db.create_session("BACKTEST", initial_balance, DB_PATH)
    SYSTEM_STATUS["session_id"] = CURRENT_SESSION_ID
    SYSTEM_STATUS["initial_balance"] = initial_balance
    SYSTEM_STATUS["balance"] = initial_balance
    
    try:
        candles = fetch_historical_candles(instrument_key, '1minute', start_date, end_date)
    except Exception as e:
        log_event(f"Failed to retrieve historical candles: {e}", "ERROR")
        return
        
    if not candles:
        log_event("No historical candles returned.", "WARNING")
        return
        
    if timeframe != '1minute':
        log_event(f"Resampling candles to {timeframe}...", "BACKTEST")
        candles = resample_candles(candles, timeframe)
        
    log_event(f"Loaded {len(candles)} candles. Starting optimized replay...", "BACKTEST")
    
    raw_df = pd.DataFrame(candles)
    ha_df = calculate_heikin_ashi(raw_df)
    
    lot_multiplier = 75
    try:
        df = pd.read_csv(CSV_PATH)
        matches = df[df['instrument_key'] == instrument_key]
        if not matches.empty:
            lot_multiplier = int(matches.iloc[0].get('lot_size', 75))
            if pd.isna(lot_multiplier):
                lot_multiplier = 75
    except Exception:
        pass
    SYSTEM_STATUS["lot_size_multiplier"] = lot_multiplier
    
    backtest_account = EngineAccount(initial_balance=initial_balance, is_real=False, lot_size=lot_size, lot_size_multiplier=lot_multiplier, brokerage_flat=brokerage_flat, slippage_pct=slippage_pct)
    
    strategy_class = STRATEGY_REGISTRY.get(strategy_name, HeikinAshiGarStrategy)
    backtest_strategy = strategy_class(**(strategy_params or {}))
    
    for i in range(2, len(raw_df)):
        slice_df = raw_df.iloc[:i+1]
        current_tick = raw_df.iloc[i]
        
        signal, meta = backtest_strategy.evaluate(slice_df)
        
        if signal == "BUY":
            stop_loss = meta.get("stop_loss", 0.0)
            target = meta.get("target_price", 0.0)
            details = ""
            if isinstance(backtest_strategy, HeikinAshiGarStrategy):
                raw_prior_open = raw_df.iloc[i-2]['open']
                candle_prior = ha_df.iloc[i-2]
                candle_completed = ha_df.iloc[i-1]
                details = (
                    f"GAR Pattern confirmed. "
                    f"Prior RED HA candle closed (O: ₹{candle_prior['open']:.2f}, C: ₹{candle_prior['close']:.2f}). "
                    f"Completed GREEN HA candle closed (O: ₹{candle_completed['open']:.2f}, C: ₹{candle_completed['close']:.2f}) "
                    f"with low deviation of {abs(candle_completed['open'] - candle_completed['low']):.3f}. "
                    f"Stop Loss anchored at prior raw candle open (₹{raw_prior_open:.2f})."
                )
            else:
                details = f"5 EMA Scalping entry at ₹{current_tick['close']:.2f}. SL: ₹{stop_loss:.2f}, Target: ₹{target:.2f}."
                
            backtest_account.buy(instrument_key, current_tick['close'], current_tick['timestamp'], stop_loss=stop_loss, details=details)
            backtest_strategy.stop_loss_level = stop_loss
            if target > 0.0:
                backtest_strategy.target_level = target
                
        elif signal == "EXIT":
            reason = meta.get("reason", "TECHNICAL_REVERSAL")
            details = ""
            if reason == "TECHNICAL_REVERSAL" and isinstance(backtest_strategy, HeikinAshiGarStrategy):
                candle_completed = ha_df.iloc[i-1]
                details = (
                    f"Technical trend reversal detected. Completed Heikin Ashi candle closed RED "
                    f"(Open: ₹{candle_completed['open']:.2f}, Close: ₹{candle_completed['close']:.2f})."
                )
            elif reason == "MAX_DURATION":
                details = f"Max holding limit reached. Position held for {backtest_strategy.candles_held} candles."
            elif reason == "SESSION_END":
                details = f"Session cutoff triggered. Intraday position automatically closed."
            elif reason == "STOP_LOSS":
                details = f"Stop Loss triggered. Low price of current candle touched SL: ₹{backtest_strategy.stop_loss_level:.2f}."
            elif reason == "TARGET_LIMIT":
                details = f"Target Limit hit at ₹{backtest_strategy.target_level:.2f}."
                
            exit_price = current_tick['close']
            if reason == "STOP_LOSS":
                exit_price = backtest_strategy.stop_loss_level
            elif reason == "TARGET_LIMIT":
                exit_price = backtest_strategy.target_level
                
            backtest_account.sell(instrument_key, exit_price, current_tick['timestamp'], reason, details=details)
            backtest_strategy.reset_state()
            
    HEIKIN_ASHI_CANDLES = []
    for idx, row in ha_df.iterrows():
        HEIKIN_ASHI_CANDLES.append({
            'time': get_unix_timestamp(row['timestamp']),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close'])
        })
        
    db.close_session(CURRENT_SESSION_ID, SYSTEM_STATUS["balance"], DB_PATH)
    log_event("Historical backtest sequence execution complete.", "BACKTEST")

def rebuild_telemetry_candles():
    global HEIKIN_ASHI_CANDLES, current_feed, SYSTEM_STATUS
    if not current_feed:
        return
        
    merged = list(current_feed.candles_history)
    if current_feed.current_candle:
        merged.append(current_feed.current_candle)
        
    if not merged:
        HEIKIN_ASHI_CANDLES = []
        return
        
    def safe_float(val, default=0.0):
        try:
            f = float(val)
            import math
            if math.isnan(f):
                return default
            return f
        except Exception:
            return default

    candle_type = SYSTEM_STATUS.get("chart_type", "heikin_ashi")
    
    if candle_type == "heikin_ashi":
        try:
            df = pd.DataFrame(merged)
            ha_df = calculate_heikin_ashi(df)
            new_candles = []
            for idx, row in ha_df.iterrows():
                new_candles.append({
                    'time': get_unix_timestamp(row['timestamp']),
                    'open': round(safe_float(row['open']), 2),
                    'high': round(safe_float(row['high']), 2),
                    'low': round(safe_float(row['low']), 2),
                    'close': round(safe_float(row['close']), 2),
                    'volume': safe_float(row.get('volume', 0.0))
                })
            HEIKIN_ASHI_CANDLES = new_candles
        except Exception as e:
            log_event(f"Failed to calculate Heikin Ashi: {e}", "ERROR")
            HEIKIN_ASHI_CANDLES = []
    else:
        HEIKIN_ASHI_CANDLES = []
        for c in merged:
            HEIKIN_ASHI_CANDLES.append({
                'time': get_unix_timestamp(c['timestamp']),
                'open': round(safe_float(c['open']), 2),
                'high': round(safe_float(c['high']), 2),
                'low': round(safe_float(c['low']), 2),
                'close': round(safe_float(c['close']), 2),
                'volume': safe_float(c.get('volume', 0.0))
            })

current_feed = None
current_strategy = None
active_thread = None
running_loop = None
main_event_loop = asyncio.get_event_loop()

LAST_NIFTY_SPOT_TIME = 0.0
CACHED_NIFTY_SPOT = 0.0
SESSION_START_TIME = 9999999999.0

# -------------------------------
# FastAPI REST Endpoint Implementations
# -------------------------------

@app.get('/api/instruments')
def get_expiry_dates(exchange: str = 'NSE', index: str = 'NIFTY'):
    sync_nifty_options_csv()
    segment = "NSE_FO" if exchange == "NSE" else "BSE_FO"
    if not os.path.exists(CSV_PATH):
        raise HTTPException(status_code=404, detail="Instruments catalog missing.")
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    today_str = datetime.now().strftime('%Y-%m-%d')
    filtered = df[
        (df['segment'] == segment) & 
        (df['name'] == index) & 
        (df['expiry_date'] >= today_str)
    ]
    expiries = sorted(filtered['expiry_date'].dropna().unique())
    return expiries

@app.get('/api/strikes')
def get_strikes(expiry: str, type: str = 'CE', exchange: str = 'NSE', index: str = 'NIFTY'):
    segment = "NSE_FO" if exchange == "NSE" else "BSE_FO"
    if not os.path.exists(CSV_PATH):
        raise HTTPException(status_code=404, detail="Instruments catalog missing.")
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    filtered = df[
        (df['segment'] == segment) & 
        (df['name'] == index) & 
        (df['expiry_date'] == expiry) & 
        (df['instrument_type'] == type)
    ]
    strikes = sorted(filtered['strike_price'].dropna().unique())
    return strikes

@app.get('/api/atr')
def get_atr(period: int = 14):
    global current_feed
    if not current_feed or not current_feed.candles_history:
        return {"atr": 1.0, "error": "No candles data available."}
        
    candles = list(current_feed.candles_history)
    if len(candles) < 3:
        return {"atr": 1.0, "warning": "Too few candles."}
        
    trs = []
    for i in range(1, len(candles)):
        h = candles[i].get('high', candles[i].get('close', 0.0))
        l = candles[i].get('low', candles[i].get('close', 0.0))
        pc = candles[i-1].get('close', 0.0)
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
        
    if not trs:
        return {"atr": 1.0}
        
    if len(trs) < period:
        atr = sum(trs) / len(trs)
    else:
        atr = sum(trs[:period]) / period
        for i in range(period, len(trs)):
            atr = (atr * (period - 1) + trs[i]) / period
            
    return {"atr": round(atr, 2)}

@app.get('/api/options/metadata')
def get_options_metadata(exchange: str = 'NSE', index: str = 'NIFTY'):
    sync_nifty_options_csv()
    if not os.path.exists(CSV_PATH):
        raise HTTPException(status_code=404, detail="CSV file missing")
        
    df = pd.read_csv(CSV_PATH)
    segment = "NSE_FO" if exchange == "NSE" else "BSE_FO"
    
    sub_df = df[(df['segment'] == segment) & (df['name'] == index)].copy()
    if sub_df.empty:
        return {"expiries": [], "spot_price": 0.0, "atm_strike": 0.0, "strikes": []}
        
    sub_df['expiry_date'] = pd.to_datetime(sub_df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    today_str = datetime.now().strftime('%Y-%m-%d')
    sub_df = sub_df[sub_df['expiry_date'] >= today_str]
    expiries = sorted(sub_df['expiry_date'].dropna().unique())
    
    underlying_keys_map = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
        "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
        "SENSEX": "BSE_INDEX|SENSEX",
        "BANKEX": "BSE_INDEX|BANKEX"
    }
    
    underlying_key = underlying_keys_map.get(index, "NSE_INDEX|Nifty 50")
    spot_price = get_index_spot_price(underlying_key)
    
    atm_strike = 0.0
    if spot_price > 0:
        step = 100
        if index in ["NIFTY", "MIDCPNIFTY"]:
            step = 50
        atm_strike = round(spot_price / step) * step
        
    strikes = sorted([float(x) for x in sub_df['strike_price'].dropna().unique()])
    
    return {
        "expiries": expiries,
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "strikes": strikes
    }

@app.get('/api/options/chain')
def get_options_chain(expiry: str, index: str = 'NIFTY', exchange: str = 'NSE'):
    """
    Options Chain with full analytics — sourced from Upstox /v2/option/chain.

    Upstox API endpoint: GET https://api.upstox.com/v2/option/chain
    Query params: instrument_key (underlying index key), expiry_date (YYYY-MM-DD)

    Response per strike contains:
      market_data:  ltp, volume, oi, close_price, bid_price, bid_qty, ask_price, ask_qty, prev_oi
      option_greeks: delta, gamma, theta, vega, iv, pop
      pcr (put/call ratio) at strike level

    This endpoint aggregates both CE and PE into per-strike rows for the frontend table.
    ATM is computed server-side using standard rounding to the index step size.
    Spot price comes from underlying_spot_price in the response (first row).
    """
    underlying_keys_map = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
        "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
        "SENSEX": "BSE_INDEX|SENSEX",
        "BANKEX": "BSE_INDEX|BANKEX"
    }
    underlying_key = underlying_keys_map.get(index, "NSE_INDEX|Nifty 50")

    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")

    url = "https://api.upstox.com/v2/option/chain"
    params = {
        "instrument_key": underlying_key,
        "expiry_date": expiry
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    raw_data = []
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            raw_data = resp.json().get("data", [])
        else:
            log_event(f"Upstox option chain status {resp.status_code}, falling back to CSV", "WARNING")
    except Exception as e:
        log_event(f"Error calling Upstox option chain: {e}, falling back to CSV", "WARNING")

    if not raw_data:
        # Fallback to local CSV matching
        try:
            if os.path.exists(CSV_PATH):
                df_csv = pd.read_csv(CSV_PATH)
                df_csv['expiry_date'] = pd.to_datetime(df_csv['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
                mask = (df_csv['name'] == index) & (df_csv['expiry_date'] == expiry)
                filtered = df_csv[mask]
                if not filtered.empty:
                    strikes_map = {}
                    for _, row in filtered.iterrows():
                        strike = float(row['strike_price'])
                        if strike not in strikes_map:
                            strikes_map[strike] = {
                                "strike_price": strike,
                                "pcr": 1.0,
                                "underlying_spot_price": 53600.0 if index == "BANKNIFTY" else 23400.0,
                                "call_options": None,
                                "put_options": None
                            }
                        opt_type = row['instrument_type']
                        opt_obj = {
                            "instrument_key": row['instrument_key'],
                            "market_data": {
                                "ltp": 100.0,
                                "volume": 5000,
                                "oi": 10000,
                                "prev_oi": 9500,
                                "bid_price": 99.5,
                                "bid_qty": 1500,
                                "ask_price": 100.5,
                                "ask_qty": 1200
                            },
                            "option_greeks": {
                                "delta": 0.5 if opt_type == "CE" else -0.5,
                                "gamma": 0.002,
                                "theta": -10.0,
                                "vega": 15.0,
                                "iv": 22.5
                            }
                        }
                        if opt_type == "CE":
                            strikes_map[strike]["call_options"] = opt_obj
                        else:
                            strikes_map[strike]["put_options"] = opt_obj
                    raw_data = [strikes_map[s] for s in sorted(strikes_map.keys())]
        except Exception as e:
            log_event(f"Mock option chain generation failed: {e}", "ERROR")

    if not raw_data:
        return {"spot_price": 0.0, "atm_strike": 0.0, "strikes": []}

    spot_price = float(raw_data[0].get("underlying_spot_price", 0.0) or 0.0)

    def _md(opt: dict) -> dict:
        """Extract market_data block safely."""
        return opt.get("market_data", {}) if opt else {}

    def _gr(opt: dict) -> dict:
        """Extract option_greeks block safely."""
        return opt.get("option_greeks", {}) if opt else {}

    # Load CSV options file to map instrument_keys to human-readable trading symbols
    key_to_symbol = {}
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            # Make sure we don't have NaNs in keys or symbols
            df = df.dropna(subset=['instrument_key', 'trading_symbol'])
            key_to_symbol = dict(zip(df['instrument_key'], df['trading_symbol']))
        except Exception as e:
            log_event(f"Error loading CSV for option symbol mapping: {e}", "WARNING")

    strikes = []
    for row in raw_data:
        strike = float(row.get("strike_price", 0))
        pcr = float(row.get("pcr", 0.0) or 0.0)

        ce = row.get("call_options", {}) or {}
        pe = row.get("put_options", {}) or {}

        ce_md = _md(ce)
        pe_md = _md(pe)
        ce_gr = _gr(ce)
        pe_gr = _gr(pe)

        ce_oi = int(ce_md.get("oi", 0) or 0)
        pe_oi = int(pe_md.get("oi", 0) or 0)
        ce_prev_oi = int(ce_md.get("prev_oi", 0) or 0)
        pe_prev_oi = int(pe_md.get("prev_oi", 0) or 0)

        # Total buy/sell qty from bid/ask qty as proxy for DOM
        ce_bid_qty = int(ce_md.get("bid_qty", 0) or 0)
        ce_ask_qty = int(ce_md.get("ask_qty", 0) or 0)
        pe_bid_qty = int(pe_md.get("bid_qty", 0) or 0)
        pe_ask_qty = int(pe_md.get("ask_qty", 0) or 0)

        # DOM signal per side: BUY_QTY / (BUY_QTY + SELL_QTY)
        ce_total = ce_bid_qty + ce_ask_qty
        pe_total = pe_bid_qty + pe_ask_qty
        ce_dom_ratio = round(ce_bid_qty / ce_total, 4) if ce_total > 0 else 0.5
        pe_dom_ratio = round(pe_bid_qty / pe_total, 4) if pe_total > 0 else 0.5

        def _dom_signal(ratio: float) -> str:
            if ratio >= 0.6:
                return "BULLISH"
            elif ratio <= 0.4:
                return "BEARISH"
            return "NEUTRAL"

        ce_key = ce.get("instrument_key")
        pe_key = pe.get("instrument_key")

        # Human-readable symbols (lookup in CSV or format fallback)
        ce_symbol = key_to_symbol.get(ce_key)
        if not ce_symbol and ce_key:
            ce_symbol = f"{index} {expiry} {int(strike)} CE"

        pe_symbol = key_to_symbol.get(pe_key)
        if not pe_symbol and pe_key:
            pe_symbol = f"{index} {expiry} {int(strike)} PE"

        strikes.append({
            "strike": strike,
            "pcr": pcr,
            # CE fields
            "ce_key": ce_key,
            "ce_symbol": ce_symbol,
            "ce_ltp": float(ce_md.get("ltp", 0.0) or 0.0),
            "ce_volume": int(ce_md.get("volume", 0) or 0),
            "ce_oi": ce_oi,
            "ce_oi_change": ce_oi - ce_prev_oi,
            "ce_oi_pct": round((ce_oi - ce_prev_oi) / ce_prev_oi * 100, 2) if ce_prev_oi > 0 else 0.0,
            "ce_bid": float(ce_md.get("bid_price", 0.0) or 0.0),
            "ce_bid_qty": ce_bid_qty,
            "ce_ask": float(ce_md.get("ask_price", 0.0) or 0.0),
            "ce_ask_qty": ce_ask_qty,
            "ce_spread": round(float(ce_md.get("ask_price", 0.0) or 0.0) - float(ce_md.get("bid_price", 0.0) or 0.0), 2),
            "ce_delta": float(ce_gr.get("delta", 0.0) or 0.0),
            "ce_gamma": float(ce_gr.get("gamma", 0.0) or 0.0),
            "ce_theta": float(ce_gr.get("theta", 0.0) or 0.0),
            "ce_vega": float(ce_gr.get("vega", 0.0) or 0.0),
            "ce_iv": float(ce_gr.get("iv", 0.0) or 0.0),
            "ce_dom_ratio": ce_dom_ratio,
            "ce_dom_signal": _dom_signal(ce_dom_ratio),
            # PE fields
            "pe_key": pe_key,
            "pe_symbol": pe_symbol,
            "pe_ltp": float(pe_md.get("ltp", 0.0) or 0.0),
            "pe_volume": int(pe_md.get("volume", 0) or 0),
            "pe_oi": pe_oi,
            "pe_oi_change": pe_oi - pe_prev_oi,
            "pe_oi_pct": round((pe_oi - pe_prev_oi) / pe_prev_oi * 100, 2) if pe_prev_oi > 0 else 0.0,
            "pe_bid": float(pe_md.get("bid_price", 0.0) or 0.0),
            "pe_bid_qty": pe_bid_qty,
            "pe_ask": float(pe_md.get("ask_price", 0.0) or 0.0),
            "pe_ask_qty": pe_ask_qty,
            "pe_spread": round(float(pe_md.get("ask_price", 0.0) or 0.0) - float(pe_md.get("bid_price", 0.0) or 0.0), 2),
            "pe_delta": float(pe_gr.get("delta", 0.0) or 0.0),
            "pe_gamma": float(pe_gr.get("gamma", 0.0) or 0.0),
            "pe_theta": float(pe_gr.get("theta", 0.0) or 0.0),
            "pe_vega": float(pe_gr.get("vega", 0.0) or 0.0),
            "pe_iv": float(pe_gr.get("iv", 0.0) or 0.0),
            "pe_dom_ratio": pe_dom_ratio,
            "pe_dom_signal": _dom_signal(pe_dom_ratio),
        })

    # Filter to ±8 strikes around ATM for performance
    step_map = {"NIFTY": 50, "MIDCPNIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 100, "SENSEX": 100, "BANKEX": 100}
    step = step_map.get(index, 50)
    atm_strike = round(spot_price / step) * step if spot_price > 0 else 0.0

    if spot_price > 0 and strikes:
        sorted_strikes = sorted(strikes, key=lambda x: x["strike"])
        atm_idx = min(range(len(sorted_strikes)), key=lambda i: abs(sorted_strikes[i]["strike"] - spot_price))
        start = max(0, atm_idx - 8)
        end = min(len(sorted_strikes), atm_idx + 9)
        strikes = sorted_strikes[start:end]

    return {
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "strikes": strikes
    }

@app.get('/api/broker/profile')
def get_broker_profile():
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/user/profile"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

@app.get('/api/broker/funds')
def get_broker_funds():
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/user/get-funds-and-margin?segment=SEC"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

@app.get('/api/broker/positions')
def get_broker_positions():
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/portfolio/short-term-positions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

@app.get('/api/broker/orders')
def get_broker_orders():
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/order/retrieve-all"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

@app.delete('/api/broker/cancel_order')
def cancel_broker_order(order_id: str):
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = f"https://api.upstox.com/v2/order/cancel?order_id={order_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.delete(url, headers=headers, timeout=10)
        resp_json = resp.json()
        if resp.status_code != 200:
            log_event(f"Failed to cancel order {order_id}: {resp_json}", "ERROR")
            raise HTTPException(status_code=resp.status_code, detail=str(resp_json))
        log_event(f"Successfully cancelled order {order_id}", "INFO")
        return resp_json
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

class ModifyOrderModel(BaseModel):
    order_id: str
    quantity: int
    price: float
    order_type: str = "LIMIT"
    trigger_price: float = 0.0
    validity: str = "DAY"

@app.put('/api/broker/modify_order')
def modify_broker_order(payload: ModifyOrderModel):
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/order/modify"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    body = {
        "order_id": payload.order_id,
        "quantity": payload.quantity,
        "price": payload.price,
        "order_type": payload.order_type,
        "trigger_price": payload.trigger_price,
        "validity": payload.validity
    }
    
    try:
        resp = requests.put(url, json=body, headers=headers, timeout=10)
        resp_json = resp.json()
        if resp.status_code != 200:
            log_event(f"Failed to modify order {payload.order_id}: {resp_json}", "ERROR")
            raise HTTPException(status_code=resp.status_code, detail=str(resp_json))
        log_event(f"Successfully modified order {payload.order_id}", "INFO")
        return resp_json
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

@app.get('/api/broker/trades')
def get_broker_trades():
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/order/trades/get-trades-for-day"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

@app.get('/api/broker/holdings')
def get_broker_holdings():
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/portfolio/long-term-holdings"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

class MarginRequestModel(BaseModel):
    instrument_key: str
    quantity: int
    transaction_type: str
    product: str

class BrokerOrderModel(BaseModel):
    instrument_key: str
    quantity: int
    transaction_type: str  # BUY or SELL
    order_type: str         # MARKET or LIMIT
    product: str            # MIS, NRML, CNC
    price: float = 0.0      # 0 for MARKET
    trigger_price: float = 0.0
    validity: str = "DAY"
    tag: str = "valkyrie_manual"
    stop_loss: float = 0.0
    target: float = 0.0

@app.post('/api/broker/place_order')
def place_broker_order(req: BrokerOrderModel):
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")

    # Pre-flight Daily Loss Guard Check
    try:
        daily_limit = float(os.getenv("DAILY_LOSS_LIMIT", "20000"))
        # Fetch current broker positions to calculate realized PnL
        positions_url = "https://api.upstox.com/v2/portfolio/short-term-positions"
        pos_resp = requests.get(positions_url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=10)
        if pos_resp.status_code == 200:
            pos_data = pos_resp.json().get("data", []) or []
            total_realized_pnl = sum(float(pos.get("realised", 0.0) or 0.0) for pos in pos_data)
            if total_realized_pnl <= -daily_limit:
                error_msg = f"Order Blocked: Daily Realized Loss Limit of ₹{daily_limit:,.2f} has been hit or exceeded (Current: ₹{total_realized_pnl:,.2f})."
                log_event(error_msg, "WARNING")
                raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        log_event(f"Error checking daily loss limit: {e}", "WARNING")

    # Map product codes to Upstox format
    prod_map = {"MIS": "I", "NRML": "D", "CNC": "D"}
    upstox_product = prod_map.get(req.product, req.product)

    url = "https://api.upstox.com/v2/order/place"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "instrument_token": req.instrument_key,
        "quantity": req.quantity,
        "transaction_type": req.transaction_type,
        "order_type": req.order_type,
        "product": upstox_product,
        "price": req.price,
        "trigger_price": req.trigger_price,
        "validity": req.validity,
        "tag": req.tag,
        "is_amo": False,
        "slice": False
    }
    log_event(f"Placing broker order: {payload}", "INFO")
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp_json = resp.json()
        if resp.status_code != 200:
            log_event(f"Broker order failed: {resp_json}", "ERROR")
            raise HTTPException(status_code=resp.status_code, detail=str(resp_json))
        log_event(f"Broker order placed: {resp_json}", "INFO")

        # Register Active Hedge Protection
        if req.stop_loss > 0 or req.target > 0:
            ACTIVE_HEDGES[req.instrument_key] = {
                "stop_loss": req.stop_loss,
                "target": req.target,
                "qty": req.quantity,
                "product": req.product,
                "side": req.transaction_type
            }
            log_event(f"Registered active protection hedge for {req.instrument_key}. SL: ₹{req.stop_loss}, Target: ₹{req.target}", "SYSTEM")

        return resp_json
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")



@app.post('/api/broker/margin')
def get_broker_order_margin(req: MarginRequestModel):
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = "https://api.upstox.com/v2/charges/margin"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    prod = req.product
    if prod == "MIS":
        upstox_product = "I"
    elif prod in ["NRML", "CNC"]:
        upstox_product = "D"
    else:
        upstox_product = req.product
        
    payload = {
        "instruments": [
            {
                "instrument_key": req.instrument_key,
                "quantity": req.quantity,
                "transaction_type": req.transaction_type,
                "product": upstox_product
            }
        ]
    }
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

@app.post('/api/broker/panic_exit')
def broker_panic_exit():
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Step 1: Cancel all pending/open orders
    orders_url = "https://api.upstox.com/v2/order/retrieve-all"
    cancelled_count = 0
    try:
        orders_resp = requests.get(orders_url, headers=headers, timeout=10)
        if orders_resp.status_code == 200:
            orders_data = orders_resp.json().get("data", [])
            for order in orders_data:
                status_lower = str(order.get("status", "")).lower()
                if status_lower in ["open", "validation pending", "trigger pending", "modify validation pending"]:
                    order_id = order.get("order_id")
                    cancel_url = f"https://api.upstox.com/v2/order/cancel?order_id={order_id}"
                    cancel_resp = requests.delete(cancel_url, headers=headers, timeout=10)
                    if cancel_resp.status_code == 200:
                        cancelled_count += 1
                        log_event(f"Broker Order Cancelled via Panic Exit: {order_id}", "SYSTEM")
                    else:
                        log_event(f"Failed to cancel order {order_id} via Panic Exit: {cancel_resp.text}", "ERROR")
    except Exception as e:
        log_event(f"Error retrieving/cancelling orders in Panic Exit: {e}", "ERROR")

    # Step 2: Fetch all live positions and square off
    positions_url = "https://api.upstox.com/v2/portfolio/short-term-positions"
    exited_positions = []
    try:
        pos_resp = requests.get(positions_url, headers=headers, timeout=10)
        if pos_resp.status_code == 200:
            positions_data = pos_resp.json().get("data", [])
            for pos in positions_data:
                qty = int(pos.get("quantity", 0))
                if qty != 0:
                    instrument_key = pos.get("instrument_key")
                    product = pos.get("product")
                    side = "SELL" if qty > 0 else "BUY"
                    abs_qty = abs(qty)

                    place_url = "https://api.upstox.com/v2/order/place"
                    payload = {
                        "instrument_token": instrument_key,
                        "quantity": abs_qty,
                        "transaction_type": side,
                        "order_type": "MARKET",
                        "product": product,
                        "price": 0.0,
                        "trigger_price": 0.0,
                        "validity": "DAY",
                        "tag": "valkyrie_panic",
                        "is_amo": False,
                        "slice": False
                    }
                    place_resp = requests.post(place_url, json=payload, headers=headers, timeout=10)
                    if place_resp.status_code == 200:
                        exited_positions.append(f"{side} {abs_qty} {pos.get('trading_symbol', instrument_key)}")
                        log_event(f"Broker Position Squared Off via Panic Exit: {side} {abs_qty} {instrument_key}", "SYSTEM")
                    else:
                        log_event(f"Failed to square off position for {instrument_key}: {place_resp.text}", "ERROR")
    except Exception as e:
        log_event(f"Error retrieving/squaring positions in Panic Exit: {e}", "ERROR")

    msg = f"Panic Exit Completed: Cancelled {cancelled_count} pending orders."
    if exited_positions:
        msg += f" Exited positions: {', '.join(exited_positions)}."
    else:
        msg += " No open positions to exit."

    log_event(msg, "SYSTEM")
    return {"status": "success", "message": msg}

TF_TO_UPSTOX = {
    "1m": "1minute",
    "3m": "1minute",    # fetch 1m then resample to 3m
    "5m": "1minute",    # fetch 1m then resample to 5m
    "15m": "1minute",   # fetch 1m then resample to 15m
    "1h": "1minute",    # fetch 1m then resample to 1h
    "1d": "day"
}
TF_RESAMPLE = {
    "3m": "3min", "5m": "5min", "15m": "15min", "1h": "60min"
}

@app.get('/api/broker/candles')
def get_broker_candles(instrument_key: str, timeframe: str = "1m", days: int = 10):
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    upstox_tf = TF_TO_UPSTOX.get(timeframe, "1minute")
    to_date = datetime.now()
    from_date = to_date - timedelta(days=max(days, 1))
    try:
        candles = fetch_historical_candles(instrument_key, upstox_tf, from_date, to_date)
        if timeframe in TF_RESAMPLE and candles:
            import pandas as pd
            df = pd.DataFrame(candles)
            df.set_index("timestamp", inplace=True)
            agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            df = df.resample(TF_RESAMPLE[timeframe]).agg({k: v for k, v in agg.items() if k in df.columns}).dropna()
            df.reset_index(inplace=True)
            candles = df.to_dict("records")
        formatted = []
        for c in candles:
            ts = c["timestamp"]
            if hasattr(ts, "timestamp"):
                epoch = int(ts.timestamp())
            else:
                epoch = int(ts)
            formatted.append({
                "time": epoch,
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c.get("volume", 0))
            })
        return {"status": "success", "data": formatted, "count": len(formatted)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/broker/instrument_info')
def get_broker_instrument_info(instrument_key: str):
    # Try looking up in nifty_options.csv
    try:
        if os.path.exists(CSV_PATH):
            df = pd.read_csv(CSV_PATH)
            matches = df[df['instrument_key'] == instrument_key]
            if not matches.empty:
                row = matches.iloc[0]
                lot_size = int(row.get('lot_size', 1))
                if pd.isna(lot_size):
                    lot_size = 1
                return {"status": "success", "lot_size": lot_size, "trading_symbol": row.get("trading_symbol")}
    except Exception as e:
        pass
        
    # Standard index/contract fallbacks
    key_upper = instrument_key.upper()
    if "BANK" in key_upper:
        return {"status": "success", "lot_size": 15}
    elif "FIN" in key_upper:
        return {"status": "success", "lot_size": 40}
    elif "MID" in key_upper:
        return {"status": "success", "lot_size": 75}
    elif "NIFTY" in key_upper:
        return {"status": "success", "lot_size": 75}
    # Equities / stocks
    return {"status": "success", "lot_size": 1}


@app.get('/api/broker/quotes')

def get_broker_quotes(instrument_key: str):
    token = load_upstox_token()
    if not token:
        raise HTTPException(status_code=401, detail="Token Expired: No upstox token found.")
    
    url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={urllib.parse.quote(instrument_key)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err_detail = resp.json()
            except:
                err_detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=str(err_detail))
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstox connection failed: {e}")

class ChartConfigModel(BaseModel):
    interval: str = "1minute"
    candle_type: str = "heikin_ashi"

@app.post('/api/chart/config')
def set_chart_config(config: ChartConfigModel):
    global current_feed, SYSTEM_STATUS, HEIKIN_ASHI_CANDLES
    interval = config.interval
    candle_type = config.candle_type
    
    SYSTEM_STATUS["chart_interval"] = interval
    SYSTEM_STATUS["chart_type"] = candle_type
    
    if current_feed:
        current_feed.interval = interval
        current_feed.candles_history = []
        current_feed.current_candle = None
        
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=3)
            hist = fetch_historical_candles(current_feed.instrument_key, '1minute', from_date, to_date)
            if interval in ["5minute", "15minute"]:
                hist = resample_candles(hist, interval)
            current_feed.candles_history = hist[-100:]
            
            rebuild_telemetry_candles()
            log_event(f"Chart interval updated to {interval}.", "SYSTEM")
        except Exception as e:
            log_event(f"Failed to fetch historical candles for interval {interval}: {e}", "WARNING")
            
    return {"status": "success", "chart_interval": interval, "chart_type": candle_type}

class UnifiedTargetUpdateModel(BaseModel):
    expiry: str
    option_type: str = "CE"
    strike: str = "ATM"
    exchange: str = "NSE"
    index_name: str = "NIFTY"
    index: Optional[str] = None

def handle_unified_target_update(req_data: UnifiedTargetUpdateModel):
    global SYSTEM_STATUS, current_feed, running_loop
    expiry = req_data.expiry
    option_type = req_data.option_type
    strike = req_data.strike
    exchange = req_data.exchange
    index_name = req_data.index or req_data.index_name
    
    sync_nifty_options_csv()
    
    if strike == "ATM":
        underlying_keys_map = {
            "NIFTY": "NSE_INDEX|Nifty 50",
            "BANKNIFTY": "NSE_INDEX|Nifty Bank",
            "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
            "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
            "SENSEX": "BSE_INDEX|SENSEX",
            "BANKEX": "BSE_INDEX|BANKEX"
        }
        underlying_key = underlying_keys_map.get(index_name, "NSE_INDEX|Nifty 50")
        spot_price = get_index_spot_price(underlying_key)
        if spot_price == 0.0:
            strike_price = 22000.0
        else:
            step = 100
            if index_name in ["NIFTY", "MIDCPNIFTY"]:
                step = 50
            strike_price = round(spot_price / step) * step
    else:
        strike_price = float(strike)
        
    try:
        standard_key, standard_symbol, standard_multiplier = get_instrument_details(index_name, strike_price, expiry, option_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Instrument lookup failed: {e}")
        
    SYSTEM_STATUS.update({
        "instrument_key": standard_key,
        "trading_symbol": standard_symbol,
        "lot_size_multiplier": standard_multiplier,
        "option_type": option_type,
        "strike": strike_price,
        "expiry": expiry,
        "exchange": exchange,
        "index_name": index_name,
        "spot_price": 0.0,
        
        "scalper_instrument_key": standard_key,
        "scalper_trading_symbol": standard_symbol,
        "scalper_lot_multiplier": standard_multiplier,
        "scalper_option_type": option_type,
        "scalper_strike": strike_price,
        "scalper_spot_price": 0.0
    })
    
    if current_feed and running_loop:
        current_feed.instrument_key = standard_key
        current_feed.scalper_key = standard_key
        current_feed.candles_history = []
        current_feed.current_candle = None
        
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=3)
            active_int = SYSTEM_STATUS.get("chart_interval", "1minute")
            hist = fetch_historical_candles(standard_key, '1minute', from_date, to_date)
            if active_int in ["5minute", "15minute"]:
                hist = resample_candles(hist, active_int)
            current_feed.candles_history = hist[-100:]
            
            rebuild_telemetry_candles()
            log_event(f"Dynamically pre-populated candles for target: {standard_symbol}", "SYSTEM")
        except Exception as e:
            log_event(f"Failed to pre-populate candles: {e}", "WARNING")
            
        future = asyncio.run_coroutine_threadsafe(
            current_feed.subscribe_to_keys([standard_key]),
            running_loop
        )
        try:
            future.result(timeout=2.0)
        except Exception as e:
            log_event(f"Error subscribing dynamically to {standard_key}: {e}", "ERROR")
        log_event(f"Updated Target Option dynamically: {standard_symbol}", "SYSTEM")
        
    return {"message": f"Target updated to {standard_symbol}", "status": SYSTEM_STATUS}

@app.post('/api/scalper/update_target')
def update_scalper_target(req_data: UnifiedTargetUpdateModel):
    return handle_unified_target_update(req_data)

@app.post('/api/standard/update_target')
def update_standard_target(req_data: UnifiedTargetUpdateModel):
    return handle_unified_target_update(req_data)

class StartEngineModel(BaseModel):
    mode: str = "BACKTEST"
    lot_size: int = 1
    live_protection: bool = False
    expiry: str
    option_type: str = "CE"
    strike: str = "ATM"
    exchange: str = "NSE"
    index_name: Optional[str] = None
    index: Optional[str] = None
    
    scalper_expiry: Optional[str] = None
    scalper_option_type: str = "CE"
    scalper_strike: str = "ATM"
    
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    timeframe: str = "1minute"
    max_candles: int = 10
    cutoff_time: str = "15:15"
    brokerage_flat: float = 20.0
    slippage_pct: float = 0.05
    initial_balance: float = 100000.0
    
    strategy: str = "heikin_ashi_gar"
    five_ema_period: int = 5
    five_ema_rr: float = 3.0
    
    live_trading: bool = False
    engine_version: str = "v1"

@app.post('/start')
def start_engine(req_data: StartEngineModel):
    global SYSTEM_STATUS, TRADE_LOGS, EVENT_LOGS, EQUITY_CURVE, HEIKIN_ASHI_CANDLES, current_feed, current_strategy, active_thread, running_loop, CURRENT_SESSION_ID, current_v2_runner
    
    if getattr(req_data, "engine_version", "v1") == "v2":
        # ----------------------------------------------------------------
        # V2 ENGINE DISPATCH
        # ----------------------------------------------------------------
        # PAPER / LIVE mode → spin up V2 live paper engine attached to LiveFeed.
        # BACKTEST mode (or no mode) → delegate to run_backtest_v2 as before.
        # ----------------------------------------------------------------
        mode_v2 = getattr(req_data, "mode", "BACKTEST")
        try:
            import sys as _sys
            import os as _os
            _backend_dir = _os.path.dirname(_os.path.abspath(__file__))
            if _backend_dir not in _sys.path:
                _sys.path.insert(0, _backend_dir)

            index_name = req_data.index or req_data.index_name or "NIFTY"
            underlying_keys_map = {
                "NIFTY": "NSE_INDEX|Nifty 50",
                "BANKNIFTY": "NSE_INDEX|Nifty Bank",
                "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
                "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
                "SENSEX": "BSE_INDEX|SENSEX",
                "BANKEX": "BSE_INDEX|BANKEX"
            }
            underlying_key = underlying_keys_map.get(index_name.upper(), "NSE_INDEX|Nifty 50")
            
            tf_val = req_data.timeframe
            timeframe_mapped = "1m"
            if tf_val == "1minute":
                timeframe_mapped = "1m"
            elif tf_val == "5minute":
                timeframe_mapped = "5m"
            elif tf_val in ["10s", "30s", "1m", "3m", "5m", "15m", "30m"]:
                timeframe_mapped = tf_val

            opt_pref = "DYNAMIC"
            if req_data.option_type == "CE":
                opt_pref = "CE_ONLY"
            elif req_data.option_type == "PE":
                opt_pref = "PE_ONLY"

            strategy_name_v2 = req_data.strategy
            strategy_params_v2 = {}
            if strategy_name_v2 == "heikin_ashi_gar":
                strategy_params_v2 = {
                    "candle_limit": int(req_data.max_candles),
                    "cut_off_time": req_data.cutoff_time
                }
            elif strategy_name_v2 in ["five_ema_scalping", "five_ema"]:
                strategy_params_v2 = {
                    "ema_period": int(req_data.five_ema_period),
                    "rr_ratio": float(req_data.five_ema_rr),
                    "cut_off_time": req_data.cutoff_time
                }

            strike_m = req_data.strike
            if strike_m not in [
                "ATM", "ATM+1", "ATM+2", "ATM+3", "ATM-1", "ATM-2", "ATM-3",
                "OTM_1", "OTM_2", "OTM_3", "ITM_1", "ITM_2", "ITM_3"
            ]:
                strike_m = "ATM"

            expiry_mode_val = "CURRENT_WEEKLY"
            if req_data.expiry == "NEXT_WEEKLY":
                expiry_mode_val = "NEXT_WEEKLY"
            elif req_data.expiry == "CURRENT_MONTHLY":
                expiry_mode_val = "CURRENT_MONTHLY"

            v2_payload = {
                "underlying_instrument_key": index_name,  # Short name for resolver (NIFTY/BANKNIFTY/etc.)
                "timeframe": timeframe_mapped,
                "start_date": req_data.start_date or "2026-05-25",
                "end_date": req_data.end_date or "2026-05-29",
                "strategy_name": strategy_name_v2,
                "strategy_params": strategy_params_v2,
                "option_type_preference": opt_pref,
                "strike_selection": {
                    "mode": strike_m
                },
                "expiry_selection": {
                    "mode": expiry_mode_val,
                    "roll_threshold_hours": 2.0
                },
                "risk_management": {
                    "target_type": "percent" if strategy_name_v2 == "five_ema_scalping" else "none",
                    "target_value": req_data.five_ema_rr if strategy_name_v2 == "five_ema_scalping" else 0.0,
                    "stop_loss_type": "percent" if strategy_name_v2 == "five_ema_scalping" else "none",
                    "stop_loss_value": 1.0,
                    "trailing_sl_gap": 0.0,
                    "max_holding_candles": int(req_data.max_candles),
                    "cutoff_time": req_data.cutoff_time
                },
                "execution": {
                    "brokerage_flat": req_data.brokerage_flat,
                    "slippage_pct": req_data.slippage_pct,
                    "lot_size": req_data.lot_size,
                    "initial_balance": req_data.initial_balance
                }
            }

            # ----------------------------------------------------------
            # V2 LIVE PAPER EXECUTION PATH (mode=PAPER or LIVE)
            # ----------------------------------------------------------
            if mode_v2 in ["PAPER", "LIVE"]:
                if SYSTEM_STATUS["state"] in ["PROCESSING", "LIVE_MONITORING", "RUNNING_BACKTEST"]:
                    raise HTTPException(status_code=400, detail="Session already active. Stop it first.")

                # --- Reset global state ---
                TRADE_LOGS = []
                EVENT_LOGS = []
                EQUITY_CURVE = [{"timestamp": datetime.now().isoformat(), "equity": req_data.initial_balance}]
                HEIKIN_ASHI_CANDLES = []
                current_v2_runner = None

                SYSTEM_STATUS.update({
                    "state": "PROCESSING",
                    "mode": mode_v2,
                    "balance": req_data.initial_balance,
                    "initial_balance": req_data.initial_balance,
                    "position": None,
                    "instrument_key": underlying_key,
                    "index_name": index_name,
                    "engine": "v2"
                })

                # --- Instantiate V2 runtime components ---
                from v2.config import BacktestConfig
                from v2.position_ledger import PositionLedger
                from v2.position_manager import PositionManager
                from v2.realtime_signal_runner import RealtimeSignalRunner
                from v2.telemetry_logger import TelemetryLogger

                CURRENT_SESSION_ID = db.create_session(mode_v2, req_data.initial_balance, DB_PATH)
                SYSTEM_STATUS["session_id"] = CURRENT_SESSION_ID
                SYSTEM_STATUS["session_start_timestamp"] = datetime.now().isoformat()

                v2_config = BacktestConfig(**v2_payload)
                v2_ledger = PositionLedger()
                v2_position_manager = PositionManager(ledger=v2_ledger)
                
                TelemetryLogger.set_live_mode(True)
                TelemetryLogger.start_session()

                realtime_runner = RealtimeSignalRunner(
                    config=v2_config,
                    position_manager=v2_position_manager,
                    db_path=DB_PATH
                )
                current_v2_runner = realtime_runner

                log_event(f"V2 Engine runtime components initialized. Strategy: {strategy_name_v2} | Underlying: {underlying_key}", "V2")

                # --- Build a lightweight V1 stub feed (no V1 strategy execution) ---
                # We still need LiveFeed for WebSocket market data ingestion.
                # The strategy engine and account are stubs — V2 runner handles execution.
                current_strategy = STRATEGY_REGISTRY.get("heikin_ashi_gar", HeikinAshiGarStrategy)()
                engine_account = EngineAccount(
                    initial_balance=req_data.initial_balance,
                    is_real=False,
                    lot_size=req_data.lot_size,
                    lot_size_multiplier=75
                )

                # Instrument key for underlying index feed subscription
                current_feed = LiveFeed(underlying_key, current_strategy, engine_account)

                # --- Wire V2 runner to LiveFeed observer ---
                current_feed.register_candle_listener(realtime_runner.on_candle)
                log_event("RealtimeSignalRunner registered as LiveFeed candle listener.", "V2")

                def run_v2_websocket_loop():
                    global running_loop
                    running_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(running_loop)
                    try:
                        running_loop.run_until_complete(current_feed.connect())
                    except Exception as e:
                        log_event(f"V2 WebSocket session disconnected: {e}", "ERROR")
                    finally:
                        SYSTEM_STATUS["state"] = "DISCONNECTED"

                active_thread = threading.Thread(target=run_v2_websocket_loop, daemon=True)
                active_thread.start()

                SYSTEM_STATUS["state"] = "LIVE_MONITORING"
                log_event(f"V2 PAPER ENGINE LIVE. Strategy: {strategy_name_v2}. Listening for market candles...", "V2")

                return {
                    "message": f"V2 Paper Engine initialized in {mode_v2} mode.",
                    "engine": "v2",
                    "strategy": strategy_name_v2,
                    "underlying": underlying_key,
                    "status": SYSTEM_STATUS
                }

            # ----------------------------------------------------------
            # V2 BACKTEST PATH (default — delegates to run_backtest_v2)
            # ----------------------------------------------------------
            from v2.engine_v2 import run_backtest_v2
            result = run_backtest_v2(v2_payload)
            return {
                "status": "accepted",
                "engine": "v2",
                "configuration": result.get("configuration")
            }
        except HTTPException:
            raise
        except Exception as ex:
            raise HTTPException(status_code=400, detail=f"V2 Initialization failed: {str(ex)}")

    mode = req_data.mode
    lot_size = req_data.lot_size
    live_protection = req_data.live_protection
    expiry = req_data.expiry
    option_type = req_data.option_type
    strike = req_data.strike
    exchange = req_data.exchange
    index_name = req_data.index or req_data.index_name or "NIFTY"
    
    scalper_expiry = req_data.scalper_expiry
    scalper_option_type = req_data.scalper_option_type
    scalper_strike = req_data.scalper_strike
    
    start_date_str = req_data.start_date
    end_date_str = req_data.end_date
    timeframe = req_data.timeframe
    max_candles = req_data.max_candles
    cutoff_time = req_data.cutoff_time
    brokerage_flat = req_data.brokerage_flat
    slippage_pct = req_data.slippage_pct
    initial_balance = req_data.initial_balance
    
    strategy_name = req_data.strategy
    strategy_params = {}
    if strategy_name == "heikin_ashi_gar":
        strategy_params = {
            "candle_limit": int(max_candles),
            "cut_off_time": cutoff_time
        }
    elif strategy_name == "five_ema_scalping":
        strategy_params = {
            "ema_period": int(req_data.five_ema_period),
            "rr_ratio": float(req_data.five_ema_rr),
            "cut_off_time": cutoff_time
        }
        
    period_type = "custom"
    start_date, end_date = parse_predefined_period(period_type, start_date_str, end_date_str)
    
    if strike == "ATM":
        log_event(f"Strike configured as ATM for {index_name}. Fetching spot price...", "SYSTEM")
        underlying_keys_map = {
            "NIFTY": "NSE_INDEX|Nifty 50",
            "BANKNIFTY": "NSE_INDEX|Nifty Bank",
            "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
            "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
            "SENSEX": "BSE_INDEX|SENSEX",
            "BANKEX": "BSE_INDEX|BANKEX"
        }
        underlying_key = underlying_keys_map.get(index_name, "NSE_INDEX|Nifty 50")
        spot_price = get_index_spot_price(underlying_key)
        if spot_price == 0.0:
            strike_price = 22000.0
        else:
            step = 100
            if index_name in ["NIFTY", "MIDCPNIFTY"]:
                step = 50
            strike_price = round(spot_price / step) * step
    else:
        strike_price = float(strike)
        
    try:
        instrument_key, trading_symbol, lot_multiplier = get_instrument_details(index_name, strike_price, expiry, option_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Instrument lookup failed: {e}")
        
    if not scalper_expiry:
        scalper_expiry = expiry
        scalper_option_type = option_type
        scalper_strike = strike
        scalper_key = instrument_key
        scalper_symbol = trading_symbol
        scalper_multiplier = lot_multiplier
    else:
        if scalper_strike == "ATM":
            underlying_keys_map = {
                "NIFTY": "NSE_INDEX|Nifty 50",
                "BANKNIFTY": "NSE_INDEX|Nifty Bank",
                "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
                "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
                "SENSEX": "BSE_INDEX|SENSEX",
                "BANKEX": "BSE_INDEX|BANKEX"
            }
            underlying_key = underlying_keys_map.get(index_name, "NSE_INDEX|Nifty 50")
            spot_price = get_index_spot_price(underlying_key)
            if spot_price == 0.0:
                scalper_strike_price = 22000.0
            else:
                step = 100
                if index_name in ["NIFTY", "MIDCPNIFTY"]:
                    step = 50
                scalper_strike_price = round(spot_price / step) * step
        else:
            scalper_strike_price = float(scalper_strike)
            
        try:
            scalper_key, scalper_symbol, scalper_multiplier = get_instrument_details(index_name, scalper_strike_price, scalper_expiry, scalper_option_type)
        except Exception:
            scalper_key, scalper_symbol, scalper_multiplier = instrument_key, trading_symbol, lot_multiplier
 
    if SYSTEM_STATUS["state"] in ["PROCESSING", "LIVE_MONITORING", "RUNNING_BACKTEST"]:
        raise HTTPException(status_code=400, detail="Session is already active. Stop it first.")
 
    global GTT_ORDERS
    TRADE_LOGS = []
    EVENT_LOGS = []
    EQUITY_CURVE = [{"timestamp": datetime.now().isoformat(), "equity": initial_balance}]
    HEIKIN_ASHI_CANDLES = []
    GTT_ORDERS = []
    
    SYSTEM_STATUS.update({
        "state": "PROCESSING",
        "mode": mode,
        "balance": initial_balance,
        "initial_balance": initial_balance,
        "position": None,
        "instrument_key": instrument_key,
        "trading_symbol": trading_symbol,
        "strike": strike_price,
        "expiry": expiry,
        "option_type": option_type,
        "exchange": exchange,
        "index_name": index_name,
        
        "scalper_instrument_key": scalper_key,
        "scalper_trading_symbol": scalper_symbol,
        "scalper_lot_multiplier": scalper_multiplier,
        "scalper_option_type": scalper_option_type,
        "scalper_strike": scalper_strike,
        "scalper_spot_price": 0.0,
        
        "live_protection": live_protection,
        "is_real_execution": False,
        "lot_size": lot_size,
        "lot_size_multiplier": lot_multiplier,
        "total_pnl": 0.0,
        "return_percent": 0.0,
        "max_drawdown": 0.0,
        "profit_factor": 0.0,
        "total_trades": 0,
        "win_rate": 0.0,
        "sharpe_ratio": 0.0,
        "max_consec_wins": 0,
        "max_consec_losses": 0
    })
    
    if mode == "BACKTEST":
        def run_backtest_thread():
            global SYSTEM_STATUS
            SYSTEM_STATUS["state"] = "RUNNING_BACKTEST"
            try:
                run_historical_backtest(
                    instrument_key, 
                    lot_size, 
                    start_date, 
                    end_date, 
                    timeframe, 
                    max_candles, 
                    cutoff_time, 
                    brokerage_flat, 
                    slippage_pct,
                    initial_balance,
                    strategy_name=strategy_name,
                    strategy_params=strategy_params
                )
                SYSTEM_STATUS["state"] = "COMPLETED"
            except Exception as e:
                log_event(f"Backtest execution failed: {e}", "ERROR")
                SYSTEM_STATUS["state"] = "FAILED"
        active_thread = threading.Thread(target=run_backtest_thread, daemon=True)
        active_thread.start()
        return {"message": "Backtest session initialized.", "status": SYSTEM_STATUS}
        
    elif mode in ["PAPER", "LIVE", "MANUAL"]:
        CURRENT_SESSION_ID = db.create_session(mode, initial_balance, DB_PATH)
        SYSTEM_STATUS["session_id"] = CURRENT_SESSION_ID
        SYSTEM_STATUS["session_start_timestamp"] = datetime.now().isoformat()
        
        account_is_real = (mode == "LIVE" or (mode == "MANUAL" and req_data.live_trading)) and live_protection
        log_event(f"Starting {mode} session engine. Real Execution active: {account_is_real} | Session ID: {CURRENT_SESSION_ID}", "SYSTEM")
        SYSTEM_STATUS["is_real_execution"] = account_is_real
        
        strategy_class = STRATEGY_REGISTRY.get(strategy_name, HeikinAshiGarStrategy)
        current_strategy = strategy_class(**strategy_params)
        
        engine_account = EngineAccount(
            initial_balance=initial_balance, 
            is_real=account_is_real, 
            lot_size=lot_size, 
            lot_size_multiplier=lot_multiplier,
            brokerage_flat=brokerage_flat, 
            slippage_pct=slippage_pct
        )
        current_feed = LiveFeed(instrument_key, current_strategy, engine_account, scalper_key=scalper_key)
        
        def run_websocket_loop():
            global running_loop
            running_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(running_loop)
            try:
                running_loop.run_until_complete(current_feed.connect())
            except Exception as e:
                log_event(f"WebSocket session disconnected: {e}", "ERROR")
            finally:
                SYSTEM_STATUS["state"] = "DISCONNECTED"
                
        active_thread = threading.Thread(target=run_websocket_loop, daemon=True)
        active_thread.start()
        
        SYSTEM_STATUS["state"] = "LIVE_MONITORING"
        return {"message": f"{mode} session engine initialized.", "status": SYSTEM_STATUS}
        
    raise HTTPException(status_code=400, detail="Unsupported execution mode.")

@app.post('/stop')
def stop_engine():
    global current_feed, running_loop, active_thread, SYSTEM_STATUS, CURRENT_SESSION_ID, current_v2_runner
    log_event("Shutdown instruction received. Stopping session engine...", "SYSTEM")
    
    if current_feed:
        if current_v2_runner:
            try:
                current_feed.unregister_candle_listener(current_v2_runner.on_candle)
            except Exception:
                pass
        current_feed.stop()
        current_feed = None
        
    if running_loop:
        try:
            running_loop.call_soon_threadsafe(running_loop.stop)
        except Exception:
            pass
        running_loop = None
        
    if CURRENT_SESSION_ID:
        db.close_session(CURRENT_SESSION_ID, SYSTEM_STATUS["balance"], DB_PATH)
        CURRENT_SESSION_ID = None
        
    if current_v2_runner:
        from v2.telemetry_logger import TelemetryLogger
        TelemetryLogger.set_live_mode(False)
        current_v2_runner = None
        
    SYSTEM_STATUS["session_id"] = None
    SYSTEM_STATUS["session_start_timestamp"] = None
    SYSTEM_STATUS["state"] = "IDLE"
    return {"message": "Session engine successfully halted.", "status": SYSTEM_STATUS}

@app.post('/pause')
def pause_engine():
    global current_v2_runner, SYSTEM_STATUS
    if not current_v2_runner:
        raise HTTPException(status_code=400, detail="No active V2 session to pause.")
    current_v2_runner.is_paused = True
    SYSTEM_STATUS["state"] = "PAUSED"
    log_event("V2 engine session PAUSED by user request.", "SYSTEM")
    return {"message": "Session successfully paused.", "status": SYSTEM_STATUS}

@app.post('/resume')
def resume_engine_route():
    global current_v2_runner, SYSTEM_STATUS
    if not current_v2_runner:
        raise HTTPException(status_code=400, detail="No active V2 session to resume.")
    current_v2_runner.is_paused = False
    SYSTEM_STATUS["state"] = "LIVE_MONITORING"
    log_event("V2 engine session RESUMED by user request.", "SYSTEM")
    return {"message": "Session successfully resumed.", "status": SYSTEM_STATUS}

@app.get('/telemetry')
def get_telemetry():
    global LAST_NIFTY_SPOT_TIME, CACHED_NIFTY_SPOT, current_feed, active_thread, SESSION_START_TIME
    
    if SYSTEM_STATUS.get("state") in ["LIVE_MONITORING", "PROCESSING"]:
        elapsed_since_start = time.time() - SESSION_START_TIME
        if elapsed_since_start > 8.0:
            is_alive = False
            if current_feed and active_thread and active_thread.is_alive():
                if SYSTEM_STATUS.get("state") == "PROCESSING":
                    is_alive = True
                elif current_feed.ws and not getattr(current_feed.ws, 'closed', False):
                    is_alive = True
                    
            if not is_alive:
                log_event("Connection check: option stream feed is not active. Resetting state to IDLE.", "SYSTEM")
                if current_feed:
                    try:
                        current_feed.stop()
                    except Exception:
                        pass
                    current_feed = None
                SYSTEM_STATUS["state"] = "IDLE"
                SYSTEM_STATUS["position"] = None
            
    update_telemetry_metrics()
    now = time.time()
    active_index = SYSTEM_STATUS.get("index_name", "NIFTY")
    
    underlying_keys_map = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
        "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
        "SENSEX": "BSE_INDEX|SENSEX",
        "BANKEX": "BSE_INDEX|BANKEX"
    }
    
    if now - LAST_NIFTY_SPOT_TIME > 10.0:
        try:
            underlying_key = underlying_keys_map.get(active_index, "NSE_INDEX|Nifty 50")
            spot = get_index_spot_price(underlying_key)
            if spot > 0:
                CACHED_NIFTY_SPOT = spot
                LAST_NIFTY_SPOT_TIME = now
        except Exception:
            pass
    SYSTEM_STATUS["nifty_spot"] = CACHED_NIFTY_SPOT

    return {
        "status": SYSTEM_STATUS,
        "trades": TRADE_LOGS,
        "logs": EVENT_LOGS,
        "candles": HEIKIN_ASHI_CANDLES,
        "gtt_orders": GTT_ORDERS,
        "equity_curve": EQUITY_CURVE
    }

class BuyOrderModel(BaseModel):
    qty: int = 1
    target: float = 0.0
    target_type: str = "points"
    stop_loss: float = 0.0
    stop_loss_type: str = "points"
    trailing_gap: float = 0.0
    is_scalper: bool = False

@app.post('/manual/buy')
def manual_buy(req_data: BuyOrderModel):
    global SYSTEM_STATUS, current_feed, TRADE_LOGS
    if not current_feed or not current_feed.account:
        raise HTTPException(status_code=400, detail="Trading Desk stream is not connected. Connect first.")
        
    pos = SYSTEM_STATUS.get("position")
    qty = req_data.qty
    target = req_data.target
    target_type = req_data.target_type
    stop_loss = req_data.stop_loss
    stop_loss_type = req_data.stop_loss_type
    trailing_gap = req_data.trailing_gap
    is_scalper = req_data.is_scalper
    
    if is_scalper:
        instrument_key = SYSTEM_STATUS.get("scalper_instrument_key", SYSTEM_STATUS["instrument_key"])
        lot_mult = SYSTEM_STATUS.get("scalper_lot_multiplier", SYSTEM_STATUS["lot_size_multiplier"])
        price = SYSTEM_STATUS.get("scalper_spot_price", 0.0)
    else:
        instrument_key = SYSTEM_STATUS["instrument_key"]
        lot_mult = SYSTEM_STATUS["lot_size_multiplier"]
        price = SYSTEM_STATUS["spot_price"]

    if pos and pos.get("instrument_key") and pos["instrument_key"] != instrument_key:
        raise HTTPException(status_code=400, detail=f"Already in a position for {pos['instrument_key']}. Exit first before buying a different instrument.")
        
    if price <= 0.0:
        raise HTTPException(status_code=400, detail=f"LTP is not available yet for {instrument_key}. Wait for a tick.")
        
    current_feed.account.lot_size = qty
    current_feed.account.lot_size_multiplier = lot_mult
    current_feed.account.qty = qty * lot_mult
    SYSTEM_STATUS["lot_size"] = qty
    
    success = current_feed.account.buy(
        instrument_key=instrument_key,
        price=price,
        timestamp=datetime.now(),
        stop_loss=0.0,
        details="SCALPER_BUY" if is_scalper else "MANUAL_BUY"
    )
    if success:
        avg_entry = current_feed.account.entry_price
        target_price = 0.0
        stop_loss_price = 0.0
        
        if target > 0.0:
            if target_type == "points":
                target_price = avg_entry + target
            elif target_type == "percent":
                target_price = avg_entry * (1.0 + target / 100.0)
            elif target_type == "atr":
                target_price = avg_entry + target
                
        if stop_loss > 0.0:
            if stop_loss_type == "points":
                stop_loss_price = avg_entry - stop_loss
            elif stop_loss_type == "percent":
                stop_loss_price = avg_entry * (1.0 - stop_loss / 100.0)
            elif stop_loss_type == "atr":
                stop_loss_price = avg_entry - stop_loss
                
        if SYSTEM_STATUS["position"]:
            SYSTEM_STATUS["position"]["target_price"] = target_price
            SYSTEM_STATUS["position"]["stop_loss"] = stop_loss_price
            SYSTEM_STATUS["position"]["is_scalper"] = is_scalper
            SYSTEM_STATUS["position"]["trailing_gap"] = trailing_gap
            SYSTEM_STATUS["position"]["highest_price"] = price
            SYSTEM_STATUS["position"]["total_qty"] = current_feed.account.qty
            
        action = "scaled in" if pos else "opened"
        return {"message": f"BUY order executed ({action}). Avg: ₹{avg_entry:.2f} | Qty: {current_feed.account.qty}", "status": SYSTEM_STATUS}
    else:
        reason = getattr(current_feed.account, 'buy_reject_reason', '') or 'Unknown failure'
        log_event(f"Manual BUY rejected: {reason}", "ERROR")
        raise HTTPException(status_code=400, detail=f"BUY rejected: {reason}")

@app.post('/manual/sell')
def manual_sell():
    global SYSTEM_STATUS, current_feed, TRADE_LOGS
    if not current_feed or not current_feed.account or not current_feed.account.position:
        raise HTTPException(status_code=400, detail="No active position to exit.")
        
    pos = SYSTEM_STATUS["position"]
    instrument_key = pos["instrument_key"]
    is_scalper = pos.get("is_scalper", False)
    
    price = SYSTEM_STATUS["scalper_spot_price"] if is_scalper else SYSTEM_STATUS["spot_price"]
    if price <= 0.0:
        raise HTTPException(status_code=400, detail="Spot price is not available yet.")
        
    success = current_feed.account.sell(
        instrument_key=instrument_key,
        price=price,
        timestamp=datetime.now(),
        reason="MANUAL_EXIT",
        details="Manual exit from dashboard"
    )
    if success:
        return {"message": "Manual SELL/EXIT order executed.", "status": SYSTEM_STATUS}
    else:
        raise HTTPException(status_code=400, detail="Manual SELL/EXIT order failed.")

@app.post('/manual/panic_exit')
def manual_panic_exit():
    global SYSTEM_STATUS, current_feed, GTT_ORDERS
    
    cancelled_count = 0
    for order in GTT_ORDERS:
        if order.get("status") == "PENDING":
            order["status"] = "CANCELLED"
            cancelled_count += 1
            log_event(f"GTT Trigger Cancelled via Panic Exit: {order['id']}", "SYSTEM")
            
    squared_off = False
    if current_feed and current_feed.account and current_feed.account.position:
        pos = SYSTEM_STATUS["position"]
        if pos:
            instrument_key = pos["instrument_key"]
            is_scalper = pos.get("is_scalper", False)
            price = SYSTEM_STATUS["scalper_spot_price"] if is_scalper else SYSTEM_STATUS["spot_price"]
            if price > 0.0:
                success = current_feed.account.sell(
                    instrument_key=instrument_key,
                    price=price,
                    timestamp=datetime.now(),
                    reason="PANIC_EXIT",
                    details="Emergency Panic Square Off"
                )
                if success:
                    squared_off = True
            else:
                fallback_price = pos.get("average_price", 1.0)
                success = current_feed.account.sell(
                    instrument_key=instrument_key,
                    price=fallback_price,
                    timestamp=datetime.now(),
                    reason="PANIC_EXIT",
                    details="Emergency Panic Square Off (LTP Fallback)"
                )
                if success:
                    squared_off = True
                    
    msg = f"Panic Exit Executed: Cancelled {cancelled_count} GTT orders."
    if squared_off:
        msg += " Open position squared off."
    else:
        msg += " No active position to square off."
        
    log_event(msg, "SYSTEM")
    return {"message": msg, "status": SYSTEM_STATUS}

class GttOrderModel(BaseModel):
    trigger_price: float
    qty: int = 1
    side: str = "BUY"
    order_type: str = "MARKET"
    price: float = 0.0
    target: float = 0.0
    target_type: str = "points"
    stop_loss: float = 0.0
    stop_loss_type: str = "points"
    trailing_gap: float = 0.0
    direction: Optional[str] = None

@app.post('/manual/gtt/create')
def manual_gtt_create(req_data: GttOrderModel):
    global GTT_ORDERS, SYSTEM_STATUS
    if not current_feed:
        raise HTTPException(status_code=400, detail="Trading Desk stream is not connected.")
        
    try:
        trigger_price = req_data.trigger_price
        qty = req_data.qty
        side = req_data.side.upper()
        order_type = req_data.order_type.upper()
        price = req_data.price
        
        target = req_data.target
        target_type = req_data.target_type
        stop_loss = req_data.stop_loss
        stop_loss_type = req_data.stop_loss_type
        trailing_gap = req_data.trailing_gap
        
        if trigger_price <= 0.0:
            raise HTTPException(status_code=400, detail="Trigger price must be greater than 0.")
            
        direction = req_data.direction
        if not direction:
            current_price = SYSTEM_STATUS["spot_price"]
            if current_price <= 0.0:
                current_price = trigger_price
            direction = "ABOVE" if trigger_price >= current_price else "BELOW"
        direction = direction.upper()
        
        gtt_id = f"GTT_{int(time.time() * 1000)}"
        gtt_order = {
            "id": gtt_id,
            "trigger_price": trigger_price,
            "side": side,
            "qty": qty,
            "order_type": order_type,
            "price": price if order_type == "LIMIT" else trigger_price,
            "target": target,
            "target_type": target_type,
            "stop_loss": stop_loss,
            "stop_loss_type": stop_loss_type,
            "trailing_gap": trailing_gap,
            "direction": direction,
            "status": "PENDING",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        GTT_ORDERS.append(gtt_order)
        log_event(f"GTT Trigger Created: {side} {qty} Lots if LTP goes {direction} {trigger_price:.2f}", "SYSTEM")
        return {"message": "GTT order created successfully.", "gtt_order": gtt_order}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class CancelGttModel(BaseModel):
    id: str

@app.post('/manual/gtt/cancel')
def manual_gtt_cancel(req_data: CancelGttModel):
    global GTT_ORDERS
    gtt_id = req_data.id
    for order in GTT_ORDERS:
        if order["id"] == gtt_id and order["status"] == "PENDING":
            order["status"] = "CANCELLED"
            log_event(f"GTT Trigger Cancelled: {order['id']}", "SYSTEM")
            return {"message": "GTT order cancelled successfully."}
    raise HTTPException(status_code=404, detail="GTT order not found or already triggered/cancelled.")

# -------------------------------
# WebSocket Telemetry Server
# -------------------------------

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_connections.append(websocket)
    log_event("Telemetry WebSocket client connected.", "WS")
    try:
        while True:
            # Keep connection alive & receive client messages if any
            data = await websocket.receive_text()
            # Handle incoming ping / custom control frames from UI if needed
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        log_event("Telemetry WebSocket client disconnected.", "WS")
    except Exception as e:
        log_event(f"Telemetry WS handling error: {e}", "ERROR")
    finally:
        if websocket in ws_connections:
            ws_connections.remove(websocket)

# Periodically broadcast telemetry to all connected WS clients
async def start_periodic_broadcaster():
    while True:
        try:
            await broadcast_telemetry()
        except Exception:
            pass
        await asyncio.sleep(1.0)

def resume_active_session_if_any():
    global CURRENT_SESSION_ID, SYSTEM_STATUS
    active_session = db.get_active_session(DB_PATH)
    if active_session:
        session_id = active_session["id"]
        db.close_session(session_id, active_session["initial_balance"], DB_PATH)
        log_event(f"Halted previous active session {session_id} on startup.", "SYSTEM")
    SYSTEM_STATUS["state"] = "IDLE"

def start_docs_watcher():
    def watch_docs():
        files_state = {}
        for root, dirs, files in os.walk(os.path.join(ROOT_DIR, "backend")):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        files_state[path] = os.path.getmtime(path)
                    except Exception:
                        pass
        for f in os.listdir(ROOT_DIR):
            if f.endswith(".py") and f != "docs_generator.py":
                path = os.path.join(ROOT_DIR, f)
                try:
                    files_state[path] = os.path.getmtime(path)
                except Exception:
                    pass
        
        while True:
            time.sleep(5)
            changed = False
            for root, dirs, files in os.walk(os.path.join(ROOT_DIR, "backend")):
                for f in files:
                    if f.endswith(".py"):
                        path = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(path)
                            if path not in files_state or files_state[path] != mtime:
                                files_state[path] = mtime
                                changed = True
                        except Exception:
                            pass
            for f in os.listdir(ROOT_DIR):
                if f.endswith(".py") and f != "docs_generator.py":
                    path = os.path.join(ROOT_DIR, f)
                    try:
                        mtime = os.path.getmtime(path)
                        if path not in files_state or files_state[path] != mtime:
                            files_state[path] = mtime
                            changed = True
                    except Exception:
                        pass
                        
            if changed:
                log_event("Codebase change detected. Re-generating documentation...", "SYSTEM")
                import subprocess
                try:
                    subprocess.run([sys.executable, os.path.join(ROOT_DIR, "docs_generator.py")], cwd=ROOT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    log_event(f"Docs auto-generation failed: {e}", "WARNING")
                    
    t = threading.Thread(target=watch_docs, daemon=True)
    t.start()

# ----------------------------------------------------
# V2 Backend Engine REST Endpoints
# ----------------------------------------------------
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class V2BacktestRequest(BaseModel):
    underlying_instrument_key: str
    timeframe: str
    start_date: str
    end_date: str
    strategy_name: str
    strategy_params: Dict[str, Any]
    option_type_preference: str
    strike_mode: str
    expiry_mode: str
    initial_capital: float = 100000.0
    lot_multiplier: int = 1
    brokerage_flat: float = 20.0
    slippage_pct: float = 0.05

class V2ParameterRange(BaseModel):
    name: str
    type: str
    min_val: float
    max_val: float
    step: float
    options: Optional[List[str]] = None

class V2OptimizationRequest(BaseModel):
    base_config: V2BacktestRequest
    ranges: List[V2ParameterRange]
    max_workers: int = 1

LATEST_V2_BACKTEST_RESULT = None
LATEST_V2_OPTIMIZATION_REPORT = None
V2_BACKTEST_STATUS = {"state": "IDLE", "progress": 0, "error": None}

@app.post("/api/v2/backtest/run")
def run_v2_backtest(req: V2BacktestRequest):
    global LATEST_V2_BACKTEST_RESULT, V2_BACKTEST_STATUS
    V2_BACKTEST_STATUS = {"state": "RUNNING", "progress": 20, "error": None}
    try:
        from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig, RiskConfig, ExecutionConfig
        from v2.types import StrikeMode, ExpiryMode, Timeframe as V2Timeframe
        from v2.replay_engine import HistoricalReplayEngine
        from v2.pnl_engine import PnLEngine
        from v2.metrics_engine import MetricsEngine
        from v2.replay_engine import get_index_short_name

        try:
            strike_m = StrikeMode(req.strike_mode)
        except ValueError:
            val = req.strike_mode
            if val == "ATM+1": strike_m = StrikeMode.ATM_PLUS_1
            elif val == "ATM+2": strike_m = StrikeMode.ATM_PLUS_2
            elif val == "ATM+3": strike_m = StrikeMode.ATM_PLUS_3
            elif val == "ATM-1": strike_m = StrikeMode.ATM_MINUS_1
            elif val == "ATM-2": strike_m = StrikeMode.ATM_MINUS_2
            elif val == "ATM-3": strike_m = StrikeMode.ATM_MINUS_3
            else: strike_m = StrikeMode.ATM

        try:
            expiry_m = ExpiryMode(req.expiry_mode)
        except ValueError:
            expiry_m = ExpiryMode.CURRENT_WEEKLY

        try:
            tf = V2Timeframe(req.timeframe)
        except ValueError:
            tf = V2Timeframe.MIN_5

        strat_params = dict(req.strategy_params)
        if "fastEma" in strat_params:
            strat_params["fast_period"] = int(strat_params["fastEma"])
        if "slowEma" in strat_params:
            strat_params["slow_period"] = int(strat_params["slowEma"])

        config = BacktestConfig(
            underlying_instrument_key=req.underlying_instrument_key,
            timeframe=tf,
            start_date=req.start_date,
            end_date=req.end_date,
            strategy_name=req.strategy_name,
            strategy_params=strat_params,
            option_type_preference=req.option_type_preference,
            strike_selection=StrikeConfig(mode=strike_m),
            expiry_selection=ExpiryConfig(mode=expiry_m),
            risk_management=RiskConfig(
                target_type="percent" if req.strategy_name == "five_ema_scalping" else "none",
                target_value=strat_params.get("five_ema_rr", 3.0) if req.strategy_name == "five_ema_scalping" else 0.0,
                stop_loss_type="percent" if req.strategy_name == "five_ema_scalping" else "none",
                stop_loss_value=1.0,
                trailing_sl_gap=0.0,
                max_holding_candles=strat_params.get("max_candles", 10) if req.strategy_name != "five_ema_scalping" else 10,
                cutoff_time=strat_params.get("cut_off_time", "15:25")
            ),
            execution=ExecutionConfig(
                brokerage_flat=req.brokerage_flat,
                slippage_pct=req.slippage_pct,
                lot_size=req.lot_multiplier,
                initial_balance=req.initial_capital
            )
        )
        
        V2_BACKTEST_STATUS["progress"] = 50
        
        from v2.backtest_runner import BacktestRunner
        runner_result = BacktestRunner.run(config)
        
        V2_BACKTEST_STATUS["progress"] = 80
        
        report = runner_result.report
        trades = runner_result.trades
        positions = runner_result.positions
        
        underlying_name = get_index_short_name(config.underlying_instrument_key)
        chart_start = datetime.strptime(req.start_date, "%Y-%m-%d").replace(hour=9, minute=15)
        chart_end = datetime.strptime(req.end_date, "%Y-%m-%d").replace(hour=15, minute=30)
        
        from v2.data_loader import UnderlyingHistoricalLoader
        from v2.cache.manager import HistoricalDataCacheManager
        cache_mgr = HistoricalDataCacheManager()
        spot_loader = UnderlyingHistoricalLoader(cache_mgr)
        spot_candles = spot_loader.load_candles(underlying_name, "1m", chart_start, chart_end)
        
        formatted_candles = []
        for c in spot_candles:
            dt = datetime.fromisoformat(c["timestamp"].replace('Z', '+00:00')) if isinstance(c["timestamp"], str) else c["timestamp"]
            formatted_candles.append({
                "time": int(dt.timestamp()),
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"]
            })
            
        formatted_trades = []
        for t in trades:
            pos_dict = None
            for p in positions:
                if p.position_id == t.position_id:
                    pos_dict = p
                    break
            
            formatted_trades.append({
                "id": f"{t.position_id}_entry",
                "timestamp": t.entry_time.isoformat(),
                "type": "BUY",
                "price": t.entry_premium,
                "quantity": t.quantity,
                "pnl": 0.0,
                "reason": "Signal Entry",
                "strike": getattr(pos_dict, "strike", 0.0) if pos_dict else 0.0,
                "expiry": getattr(pos_dict, "expiry", "") if pos_dict else "",
                "option_type": getattr(pos_dict, "option_type", "") if pos_dict else ""
            })
            formatted_trades.append({
                "id": f"{t.position_id}_exit",
                "timestamp": t.exit_time.isoformat(),
                "type": "SELL",
                "price": t.exit_premium,
                "quantity": t.quantity,
                "pnl": t.net_pnl,
                "reason": "Signal Exit",
                "strike": getattr(pos_dict, "strike", 0.0) if pos_dict else 0.0,
                "expiry": getattr(pos_dict, "expiry", "") if pos_dict else "",
                "option_type": getattr(pos_dict, "option_type", "") if pos_dict else ""
            })

        LATEST_V2_BACKTEST_RESULT = {
            "report": report.model_dump(),
            "trades": [t.model_dump() for t in trades],
            "candles": formatted_candles,
            "chart_trades": formatted_trades,
            "runtime_logs": [log.model_dump() for log in runner_result.runtime_logs]
        }
        
        V2_BACKTEST_STATUS = {"state": "COMPLETED", "progress": 100, "error": None}
        return LATEST_V2_BACKTEST_RESULT
    except Exception as e:
        import traceback
        err_msg = f"Backtest run failed: {str(e)}\n{traceback.format_exc()}"
        print(err_msg)
        V2_BACKTEST_STATUS = {"state": "FAILED", "progress": 0, "error": str(e)}
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v2/optimization/run")
def run_v2_optimization(req: V2OptimizationRequest):
    global LATEST_V2_OPTIMIZATION_REPORT
    try:
        from v2.config import BacktestConfig, StrikeConfig, ExpiryConfig, RiskConfig, ExecutionConfig
        from v2.types import StrikeMode, ExpiryMode, Timeframe as V2Timeframe
        from v2.optimization_models import ParameterRange
        from v2.optimization_engine import OptimizationEngine

        try:
            strike_m = StrikeMode(req.base_config.strike_mode)
        except ValueError:
            strike_m = StrikeMode.ATM

        try:
            expiry_m = ExpiryMode(req.base_config.expiry_mode)
        except ValueError:
            expiry_m = ExpiryMode.CURRENT_WEEKLY

        try:
            tf = V2Timeframe(req.base_config.timeframe)
        except ValueError:
            tf = V2Timeframe.MIN_5

        strat_params = dict(req.base_config.strategy_params)
        if "fastEma" in strat_params:
            strat_params["fast_period"] = int(strat_params["fastEma"])
        if "slowEma" in strat_params:
            strat_params["slow_period"] = int(strat_params["slowEma"])

        base_config = BacktestConfig(
            underlying_instrument_key=req.base_config.underlying_instrument_key,
            timeframe=tf,
            start_date=req.base_config.start_date,
            end_date=req.base_config.end_date,
            strategy_name=req.base_config.strategy_name,
            strategy_params=strat_params,
            option_type_preference=req.base_config.option_type_preference,
            strike_selection=StrikeConfig(mode=strike_m),
            expiry_selection=ExpiryConfig(mode=expiry_m),
            risk_management=RiskConfig(
                target_type="percent" if req.base_config.strategy_name == "five_ema_scalping" else "none",
                target_value=strat_params.get("five_ema_rr", 3.0) if req.base_config.strategy_name == "five_ema_scalping" else 0.0,
                stop_loss_type="percent" if req.base_config.strategy_name == "five_ema_scalping" else "none",
                stop_loss_value=1.0,
                trailing_sl_gap=0.0,
                max_holding_candles=strat_params.get("max_candles", 10) if req.base_config.strategy_name != "five_ema_scalping" else 10,
                cutoff_time=strat_params.get("cut_off_time", "15:25")
            ),
            execution=ExecutionConfig(
                brokerage_flat=req.base_config.brokerage_flat,
                slippage_pct=req.base_config.slippage_pct,
                lot_size=req.base_config.lot_multiplier,
                initial_balance=req.base_config.initial_capital
            )
        )

        engine = OptimizationEngine(initial_capital=req.base_config.initial_capital)
        
        if req.base_config.strategy_name in ["EMA", "str_ema"]:
            engine.register_constraint(
                "fast_less_than_slow",
                lambda p: (p.get("fast_period", p.get("fastEma", 0)) < p.get("slow_period", p.get("slowEma", 0)), "fast_period must be less than slow_period")
            )

        ranges = []
        for r in req.ranges:
            ranges.append(ParameterRange(
                name=r.name,
                type=r.type,
                min_val=r.min_val,
                max_val=r.max_val,
                step=r.step,
                options=r.options
            ))

        report = engine.run_optimization(base_config, ranges, max_workers=req.max_workers)
        LATEST_V2_OPTIMIZATION_REPORT = report.model_dump()
        return LATEST_V2_OPTIMIZATION_REPORT
    except Exception as e:
        import traceback
        print(f"Optimization run failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v2/backtest/status")
def get_v2_backtest_status():
    return V2_BACKTEST_STATUS

@app.get("/api/v2/backtest/results")
def get_v2_backtest_results():
    if not LATEST_V2_BACKTEST_RESULT:
        raise HTTPException(status_code=404, detail="No backtest results available.")
    return LATEST_V2_BACKTEST_RESULT

@app.get("/api/v2/backtest/trades")
def get_v2_backtest_trades():
    if not LATEST_V2_BACKTEST_RESULT:
        raise HTTPException(status_code=404, detail="No backtest trades available.")
    return LATEST_V2_BACKTEST_RESULT["trades"]

@app.get("/api/v2/backtest/equity")
def get_v2_backtest_equity():
    if not LATEST_V2_BACKTEST_RESULT:
        raise HTTPException(status_code=404, detail="No backtest results available.")
    return LATEST_V2_BACKTEST_RESULT["report"]["equity_curve"]

@app.get("/api/v2/backtest/drawdown")
def get_v2_backtest_drawdown():
    if not LATEST_V2_BACKTEST_RESULT:
        raise HTTPException(status_code=404, detail="No backtest results available.")
    return LATEST_V2_BACKTEST_RESULT["report"]["drawdown_curve"]

@app.get("/api/v2/strategies")
def get_v2_strategies():
    from v2.strategy_registry import get_all_strategy_metadata
    return get_all_strategy_metadata()

@app.get("/api/v2/strategies/{strategy_id}")
def get_v2_strategy_by_id(strategy_id: str):
    from v2.strategy_registry import get_strategy_metadata
    meta = get_strategy_metadata(strategy_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found.")
    return meta

from v2.preset_manager import PresetManager, StrategyPreset

preset_manager = PresetManager()

@app.get("/api/v2/presets")
def get_v2_presets():
    return preset_manager.get_all_presets()

@app.get("/api/v2/presets/{preset_id}")
def get_v2_preset(preset_id: str):
    preset = preset_manager.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")
    return preset

@app.post("/api/v2/presets")
def create_v2_preset(preset: StrategyPreset):
    if not preset.id or preset.id.strip() == "":
        import uuid
        preset.id = "preset_" + str(uuid.uuid4())[:8]
    return preset_manager.create_preset(preset)

class UpdatePresetRequest(BaseModel):
    name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    risk_management: Optional[Dict[str, Any]] = None
    strike_selection: Optional[Dict[str, Any]] = None
    expiry_selection: Optional[Dict[str, Any]] = None
    timeframe: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None

@app.put("/api/v2/presets/{preset_id}")
def update_v2_preset(preset_id: str, req_data: UpdatePresetRequest):
    update_dict = {k: v for k, v in req_data.model_dump().items() if v is not None}
    updated = preset_manager.update_preset(preset_id, update_dict)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")
    return updated

@app.delete("/api/v2/presets/{preset_id}")
def delete_v2_preset(preset_id: str):
    success = preset_manager.delete_preset(preset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")
    return {"status": "success", "message": f"Preset '{preset_id}' deleted."}

class DuplicatePresetRequest(BaseModel):
    new_name: str

@app.post("/api/v2/presets/{preset_id}/duplicate")
def duplicate_v2_preset(preset_id: str, req_data: DuplicatePresetRequest):
    duplicated = preset_manager.duplicate_preset(preset_id, req_data.new_name)
    if not duplicated:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")
    return duplicated

async def start_hedge_monitor():
    """
    Async hedge monitor — runs every 1 s and exits positions when SL or Target is breached.
    Uses httpx.AsyncClient (non-blocking) to avoid stalling the FastAPI event loop.
    Handles both NSE_FO|57022 (pipe) and NSE_FO:57022 (colon) key formats returned by Upstox.
    """
    async with httpx.AsyncClient(timeout=8.0) as client:
        while True:
            try:
                if ACTIVE_HEDGES:
                    token = load_upstox_token()
                    if token:
                        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
                        for inst_key, hedge in list(ACTIVE_HEDGES.items()):
                            # URL-encode the key for the query parameter
                            encoded_key = urllib.parse.quote(inst_key, safe="")
                            url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={encoded_key}"
                            resp = await client.get(url, headers=headers)
                            if resp.status_code == 200:
                                data = resp.json().get("data", {})
                                # Upstox may return the key in colon format even if we sent pipe format
                                colon_key = inst_key.replace("|", ":")
                                pipe_key = inst_key.replace(":", "|")
                                q_data = data.get(inst_key) or data.get(colon_key) or data.get(pipe_key) or {}
                                ltp = float(q_data.get("last_price", 0.0))

                                if ltp > 0:
                                    side = hedge["side"]
                                    sl = hedge["stop_loss"]
                                    tp = hedge["target"]
                                    trigger_exit = False
                                    trigger_reason = ""

                                    if side == "BUY":
                                        if sl > 0 and ltp <= sl:
                                            trigger_exit = True
                                            trigger_reason = f"Stop Loss breached (LTP ₹{ltp:.2f} <= SL ₹{sl:.2f})"
                                        elif tp > 0 and ltp >= tp:
                                            trigger_exit = True
                                            trigger_reason = f"Target hit (LTP ₹{ltp:.2f} >= Target ₹{tp:.2f})"
                                    elif side == "SELL":
                                        if sl > 0 and ltp >= sl:
                                            trigger_exit = True
                                            trigger_reason = f"Stop Loss breached (LTP ₹{ltp:.2f} >= SL ₹{sl:.2f})"
                                        elif tp > 0 and ltp <= tp:
                                            trigger_exit = True
                                            trigger_reason = f"Target hit (LTP ₹{ltp:.2f} <= Target ₹{tp:.2f})"

                                    if trigger_exit:
                                        exit_side = "SELL" if side == "BUY" else "BUY"
                                        prod_map = {"MIS": "I", "NRML": "D", "CNC": "D"}
                                        upstox_product = prod_map.get(hedge["product"], hedge["product"])
                                        exit_payload = {
                                            "instrument_token": inst_key,
                                            "quantity": hedge["qty"],
                                            "transaction_type": exit_side,
                                            "order_type": "MARKET",
                                            "product": upstox_product,
                                            "price": 0.0,
                                            "trigger_price": 0.0,
                                            "validity": "DAY",
                                            "tag": "valkyrie_hedge_exit",
                                            "is_amo": False,
                                            "slice": False
                                        }
                                        exit_headers = {**headers, "Content-Type": "application/json"}
                                        exit_resp = await client.post(
                                            "https://api.upstox.com/v2/order/place",
                                            json=exit_payload,
                                            headers=exit_headers
                                        )
                                        if exit_resp.status_code == 200:
                                            log_event(f"🚨 [Hedge Exit] {trigger_reason} for {inst_key}. Market exit submitted!", "WARNING")
                                            ACTIVE_HEDGES.pop(inst_key, None)
                                        else:
                                            log_event(f"❌ [Hedge Failure] Exit order failed for {inst_key}: {exit_resp.text}", "ERROR")
                                else:
                                    log_event(f"[Hedge Monitor] LTP=0 for {inst_key} — market may be closed or key invalid.", "WARNING")
            except Exception as e:
                log_event(f"[Hedge Monitor] Unhandled error: {e}", "WARNING")
            await asyncio.sleep(1.0)

@app.on_event("startup")
async def startup_event():
    sync_nifty_options_csv()
    resume_active_session_if_any()
    # Trigger initial docs generation at startup
    import subprocess
    try:
        subprocess.Popen([sys.executable, os.path.join(ROOT_DIR, "docs_generator.py")], cwd=ROOT_DIR)
    except Exception:
        pass
    # Start file changes docs watcher
    start_docs_watcher()
    # Start periodic broadcaster in background of main event loop
    asyncio.create_task(start_periodic_broadcaster())
    asyncio.create_task(start_hedge_monitor())

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8081)
