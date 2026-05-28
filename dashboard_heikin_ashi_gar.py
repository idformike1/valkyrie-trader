import os
import json
import threading
import time
import asyncio
from datetime import datetime, timedelta
import requests
import socket
import urllib3.util.connection as urllib3_connection

# Force requests library to use IPv4 exclusively (resolves static IP mismatch on IPv6 networks)
def allowed_gai_family():
    return socket.AF_INET

urllib3_connection.allowed_gai_family = allowed_gai_family

# Proxy configuration for Upstox order API (replace placeholders with your credentials)
PROXIES = {
    "http": "http://USER:PASS@STATIC_PROXY_IP:PORT",
    "https": "http://USER:PASS@STATIC_PROXY_IP:PORT",
}

import pandas as pd
import numpy as np
import websockets
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import MarketDataFeed_pb2 as pb
from strategy_heikin_ashi_gar import HeikinAshiGarStrategy, FiveEmaScalpingStrategy, calculate_heikin_ashi
import database as db

STRATEGY_REGISTRY = {
    "heikin_ashi_gar": HeikinAshiGarStrategy,
    "five_ema_scalping": FiveEmaScalpingStrategy
}

CURRENT_SESSION_ID = None

# -------------------------------
# Initialize Flask App
# -------------------------------
app = Flask(__name__)
CORS(app)

TOKEN_FILE = "token.txt"
CSV_PATH = "nifty_options.csv"

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
    "chart_type": "heikin_ashi"
}

TRADE_LOGS = []
EVENT_LOGS = []
EQUITY_CURVE = []
HEIKIN_ASHI_CANDLES = []
GTT_ORDERS = []

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

current_feed = None
current_strategy = None
active_thread = None
running_loop = None

def log_event(msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    EVENT_LOGS.append(f"[{timestamp}] [{level}] {msg}")
    print(f"[{timestamp}] [{level}] {msg}")

# -------------------------------
# Upstox Auth Token Loader
# -------------------------------
def load_upstox_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return os.getenv("UPSTOX_ACCESS_TOKEN", "")

# -------------------------------
# CSV Sync and Fallback Logic
# -------------------------------
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
            options_df.to_csv(CSV_PATH, index=False)
            log_event(f"Successfully saved {len(options_df)} active options to nifty_options.csv", "SYSTEM")
        except Exception as e:
            log_event(f"Failed to synchronize instruments: {e}", "ERROR")

# -------------------------------
# Upstox API Quotes Helper
# -------------------------------
def get_index_spot_price(underlying_key):
    token = load_upstox_token()
    if not token or not underlying_key:
        return 0.0
    import urllib.parse
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

def get_nifty_spot_price():
    return get_index_spot_price("NSE_INDEX|Nifty 50")

def get_instrument_details(index_name, strike, expiry_str, option_type):
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

# -------------------------------
# Order Execution Router
# -------------------------------
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

# -------------------------------
# Telemetry Calculations
# -------------------------------
def update_telemetry_metrics():
    global SYSTEM_STATUS, TRADE_LOGS, EQUITY_CURVE
    if CURRENT_SESSION_ID:
        TRADE_LOGS = db.get_session_trades(CURRENT_SESSION_ID)
        EQUITY_CURVE = db.get_session_equity_curve(CURRENT_SESSION_ID, SYSTEM_STATUS["initial_balance"])
        
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
    
    # Win rate & Profit factor & Sharpe Ratio
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

# -------------------------------
# Simulated/Real Paper Account
# -------------------------------
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
        
    def buy(self, instrument_key, price, timestamp, stop_loss=0.0, details=""):
        if self.position and self.position != instrument_key:
            log_event(f"REJECTED: Already have an open position in {self.position}. Close it first.", "WARNING")
            return False
            
        new_qty = self.qty
        buy_cost = self.brokerage_flat + (price * (self.slippage_pct / 100.0) * new_qty)
        required_capital = (price * new_qty) + buy_cost
        
        if SYSTEM_STATUS["balance"] < required_capital:
            log_event(f"REJECTED: Insufficient funds. Required: ₹{required_capital:.2f}, Available: ₹{SYSTEM_STATUS['balance']:.2f}", "WARNING")
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
                timestamp=timestamp
            )
            global TRADE_LOGS
            TRADE_LOGS = db.get_session_trades(CURRENT_SESSION_ID)
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
        
        # Real Execution Call
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
                timestamp=timestamp
            )
            global TRADE_LOGS, EQUITY_CURVE
            TRADE_LOGS = db.get_session_trades(CURRENT_SESSION_ID)
            EQUITY_CURVE = db.get_session_equity_curve(CURRENT_SESSION_ID, SYSTEM_STATUS["initial_balance"])
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
        
        # Real Execution Call
        if self.is_real:
            execute_order(instrument_key, self.qty, "SELL")
            
        self.position = None
        self.entry_price = 0.0
        SYSTEM_STATUS["position"] = None
        
        update_telemetry_metrics()
        return True

# -------------------------------
# WebSocket Market Data Client
# -------------------------------
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
            
        log_event(f"Connecting to Upstox Market Stream...", "WS")
        async with websockets.connect(uri, max_size=2**25) as ws:
            self.ws = ws
            
            # Pre-populate historical candles to show the option chart immediately
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

    async def process_message(self, raw_message):
        try:
            feed = pb.FeedResponse()
            feed.ParseFromString(raw_message)
            for key, feed_data in feed.feeds.items():
                price = None
                if feed_data.HasField("fullFeed"):
                    full_feed = feed_data.fullFeed
                    if full_feed.HasField("marketFF"):
                        price = full_feed.marketFF.ltpc.ltp
                    elif full_feed.HasField("indexFF"):
                        price = full_feed.indexFF.ltpc.ltp
                    
                if price:
                    if key == self.instrument_key:
                        SYSTEM_STATUS["spot_price"] = price
                        self.on_tick(price, datetime.now())
                    if key == self.scalper_key:
                        SYSTEM_STATUS["scalper_spot_price"] = price
                        self.on_scalper_tick(price, datetime.now())
        except Exception as e:
            log_event(f"Protobuf processing error: {e}", "ERROR")

    def on_scalper_tick(self, price, timestamp):
        # Check manual bracket targets/stop-loss exit checks for active scalper position
        if self.account.position and SYSTEM_STATUS.get("position"):
            pos = SYSTEM_STATUS["position"]
            if pos.get("is_scalper") and pos["instrument_key"] == self.scalper_key:
                target_price = pos.get("target_price", 0.0)
                stop_loss_price = pos.get("stop_loss", 0.0)
                
                # Check Stop Loss
                if stop_loss_price > 0.0 and price <= stop_loss_price:
                    details = f"Stop Loss triggered. LTP ₹{price:.2f} touched or breached SL level of ₹{stop_loss_price:.2f}."
                    self.account.sell(self.scalper_key, price, timestamp, "STOP_LOSS", details=details)
                    self.strategy.reset_state()
                # Check Target / Take Profit
                elif target_price > 0.0 and price >= target_price:
                    details = f"Target Limit triggered. LTP ₹{price:.2f} touched or breached Target level of ₹{target_price:.2f}."
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
        
        # Check manual bracket targets/stop-loss exit checks for active positions
        if self.account.position and SYSTEM_STATUS.get("position"):
            pos = SYSTEM_STATUS["position"]
            if not pos.get("is_scalper") and pos["instrument_key"] == self.instrument_key:
                # Update Trailing Stop Loss if configured
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
                            log_event(f"Trailing SL adjusted upward to ₹{pos['stop_loss']:.2f} (LTP: ₹{price:.2f}, Highest: ₹{pos['highest_price']:.2f})", "SYSTEM")

                target_price = pos.get("target_price", 0.0)
                stop_loss_price = pos.get("stop_loss", 0.0)
                
                # Check Stop Loss
                if stop_loss_price > 0.0 and price <= stop_loss_price:
                    details = f"Stop Loss triggered. LTP ₹{price:.2f} touched or breached SL level of ₹{stop_loss_price:.2f}."
                    self.account.sell(self.instrument_key, price, timestamp, "STOP_LOSS", details=details)
                    self.strategy.reset_state()
                # Check Target / Take Profit
                elif target_price > 0.0 and price >= target_price:
                    details = f"Target Limit triggered. LTP ₹{price:.2f} touched or breached Target level of ₹{target_price:.2f}."
                    self.account.sell(self.instrument_key, price, timestamp, "TARGET_LIMIT", details=details)
                    self.strategy.reset_state()
        elif self.account.position and not SYSTEM_STATUS.get("position", {}).get("is_scalper"):
            # Fallback to strategy default trailing SL
            if price <= self.strategy.stop_loss_level:
                entry_sl = self.strategy.stop_loss_level
                details = f"Stop Loss triggered. Live trailing price ₹{price:.2f} touched or breached the SL level of ₹{entry_sl:.2f}."
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
                        # Execute Buy Order
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
                            # Apply brackets
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
                        # Execute Sell Order
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
        
        if len(self.candles_history) < 3:
            return
            
        df = pd.DataFrame(self.candles_history)
        
        if SYSTEM_STATUS["mode"] == "MANUAL":
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

# -------------------------------
# Historical backtest fetcher & runner
# -------------------------------
def fetch_historical_candles(instrument_key, interval, from_date, to_date):
    if not instrument_key:
        return []
    token = load_upstox_token()
    if not token:
        raise Exception("Access token missing in token.txt")
    import urllib.parse
    encoded_key = urllib.parse.quote(instrument_key)
    url = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/{interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        if "Invalid Instrument key" in resp.text or "UDAPI100011" in resp.text:
            raise Exception("Option contract is expired or invalid. Upstox standard API does not support historical candles for expired contracts.")
        raise Exception(f"API error {resp.status_code}: {resp.text}")
    data = resp.json()
    candles_data = data.get('data', {}).get('candles', [])
    candles = []
    for c in candles_data:
        ts = datetime.fromisoformat(c[0].replace('Z', '+00:00'))
        candles.append({
            'timestamp': ts,
            'open': float(c[1]),
            'high': float(c[2]),
            'low': float(c[3]),
            'close': float(c[4])
        })
    return candles[::-1]

def resample_candles(candles, target_interval):
    if target_interval not in ['5minute', '15minute']:
        return candles
    rule_map = {'5minute': '5min', '15minute': '15min'}
    rule = rule_map[target_interval]
    df = pd.DataFrame(candles)
    df.set_index('timestamp', inplace=True)
    ohlc = df.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
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
    
    # Create DB Session for Backtest
    CURRENT_SESSION_ID = db.create_session("BACKTEST", initial_balance)
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
    
    # Resolve dynamic lot size multiplier for backtest
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
                    f"with low deviation of {abs(candle_completed['open'] - candle_completed['low']):.3f} (strong green support). "
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
        
    db.close_session(CURRENT_SESSION_ID, SYSTEM_STATUS["balance"])
    log_event("Historical backtest sequence execution complete.", "BACKTEST")

# -------------------------------
HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Valkyrie HEIKIN-ASHI GAR Command Room</title>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-deep: #080b11;
            --bg-card: rgba(22, 28, 45, 0.7);
            --border-glow: rgba(102, 252, 241, 0.2);
            --cyan-neon: #66fcf1;
            --teal-neon: #45a29e;
            --gold-accent: #c5a880;
            --green-glow: #2ec4b6;
            --red-glow: #ff4d4d;
            --text-main: #e2e8f0;
            --text-mute: #94a3b8;
        }
        * { box-sizing: border-box; }
        body { 
            font-family: 'Plus Jakarta Sans', sans-serif; 
            background: var(--bg-deep); 
            color: var(--text-main); 
            margin: 0; 
            padding: 24px;
            background-image: radial-gradient(circle at 10% 20%, rgba(102, 252, 241, 0.05) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(197, 168, 128, 0.05) 0%, transparent 40%);
        }
        .container { max-width: 1500px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }
        header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 20px; 
            background: var(--bg-card); 
            border: 1px solid var(--border-glow); 
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }
        header h1 { margin: 0; font-size: 24px; font-weight: 700; color: var(--cyan-neon); letter-spacing: 0.5px; }
        .pulsing-indicator { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; }
        .pulse-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--green-glow); box-shadow: 0 0 10px var(--green-glow); animation: pulse 2s infinite; }
        @keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 196, 182, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(46, 196, 182, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 196, 182, 0); } }
        
        /* Metrics Grid */
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; }
        .metric-card { 
            background: var(--bg-card); 
            border: 1px solid rgba(255,255,255,0.05); 
            border-radius: 12px; 
            padding: 16px; 
            text-align: center;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }
        .metric-card:hover { border-color: var(--teal-neon); transform: translateY(-2px); box-shadow: 0 4px 15px rgba(102, 252, 241, 0.1); }
        .metric-card label { font-size: 10px; text-transform: uppercase; color: var(--text-mute); letter-spacing: 1px; }
        .metric-card .val { font-size: 18px; font-weight: 700; margin-top: 8px; color: #fff; }
        .metric-card.positive .val { color: var(--green-glow); }
        .metric-card.negative .val { color: var(--red-glow); }
        
        .main-layout { display: grid; grid-template-columns: 1fr 380px; gap: 24px; }
        .card { 
            background: var(--bg-card); 
            border: 1px solid rgba(255,255,255,0.05); 
            border-radius: 16px; 
            padding: 24px;
            backdrop-filter: blur(10px);
        }
        .card h2 { margin-top: 0; color: var(--cyan-neon); font-size: 18px; font-weight: 600; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 12px; margin-bottom: 16px; }
        
        /* Control Groups */
        .control-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
        .control-item { display: flex; flex-direction: column; gap: 8px; }
        .control-item label { font-size: 11px; text-transform: uppercase; color: var(--text-mute); letter-spacing: 0.5px; }
        input, select { 
            background: rgba(11, 16, 26, 0.8); 
            border: 1px solid rgba(255,255,255,0.1); 
            color: #fff; 
            padding: 10px 12px; 
            border-radius: 8px; 
            outline: none;
            transition: all 0.3s;
            font-size: 13px;
        }
        input:focus, select:focus { border-color: var(--cyan-neon); box-shadow: 0 0 8px rgba(102, 252, 241, 0.3); }
        
        /* Toggle Switch */
        .toggle-container { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 16px; }
        .toggle-label { font-size: 13px; font-weight: 600; color: var(--text-main); }
        .switch { position: relative; display: inline-block; width: 48px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #334155; transition: .4s; border-radius: 24px; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: var(--green-glow); }
        input:checked + .slider:before { transform: translateX(24px); }
        
        .btn { background: linear-gradient(135deg, var(--teal-neon), var(--cyan-neon)); color: var(--bg-deep); border: none; padding: 14px; border-radius: 8px; font-weight: 700; cursor: pointer; text-transform: uppercase; width: 100%; transition: all 0.3s ease; letter-spacing: 0.5px; }
        .btn:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(102, 252, 241, 0.4); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn.stop { background: linear-gradient(135deg, #ef4444, #f87171); color: #fff; }
        .btn.stop:hover { box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4); }
        
        /* Table Styles */
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { text-align: left; padding: 14px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; }
        th { color: var(--text-mute); font-weight: 500; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
        td { color: #fff; }
        
        /* Log panel */
        .log-panel { 
            background: rgba(11, 16, 26, 0.9); 
            border-radius: 12px; 
            height: 250px; 
            overflow-y: auto; 
            padding: 16px; 
            font-family: 'JetBrains Mono', monospace; 
            font-size: 12px; 
            color: #fff; 
            border: 1px solid rgba(255,255,255,0.05); 
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .log-panel::-webkit-scrollbar { width: 6px; }
        .log-panel::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
        .log-entry.error { color: var(--red-glow); }
        .log-entry.trade { color: var(--green-glow); }
        .log-entry.system { color: var(--gold-accent); }
        
        /* Accordion Details Styles */
        .btn-toggle-details {
            background: transparent;
            border: 1px solid var(--border-glow);
            color: var(--cyan-neon);
            padding: 4px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        .btn-toggle-details:hover {
            background: rgba(102, 252, 241, 0.1);
            border-color: var(--cyan-neon);
        }
        .details-row td {
            padding: 0 !important;
            border-bottom: 1px solid var(--border-glow) !important;
        }
        
        /* Chart Tab Styles */
        .chart-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 8px;
        }
        .tab-btn {
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-mute);
            padding: 8px 16px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            border-radius: 4px;
            transition: all 0.2s ease;
        }
        .tab-btn:hover {
            color: #fff;
            background: rgba(255, 255, 255, 0.02);
        }
        .tab-btn.active {
            color: var(--cyan-neon);
            border-color: var(--border-glow);
            background: rgba(102, 252, 241, 0.05);
            box-shadow: 0 0 10px rgba(102, 252, 241, 0.1);
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div style="display: flex; align-items: center; gap: 24px;">
                <h1>Valkyrie HEIKIN-ASHI GAR Command Room</h1>
                <div style="display: flex; gap: 8px; background: rgba(255,255,255,0.02); padding: 4px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                    <a href="/" style="text-decoration: none; padding: 6px 12px; font-size: 12px; font-weight: 600; color: var(--cyan-neon); background: rgba(102, 252, 241, 0.05); border-radius: 6px; border: 1px solid rgba(102,252,241,0.2);">Backtest & Tuner</a>
                    <a href="/paper" style="text-decoration: none; padding: 6px 12px; font-size: 12px; font-weight: 600; color: var(--text-mute); border-radius: 6px; border: 1px solid transparent; transition: all 0.2s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-mute)'">Live Paper Trading</a>
                    <a href="/manual" style="text-decoration: none; padding: 6px 12px; font-size: 12px; font-weight: 600; color: var(--text-mute); border-radius: 6px; border: 1px solid transparent; transition: all 0.2s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-mute)'">Manual Order Desk</a>
                </div>
            </div>
            <div class="pulsing-indicator">
                <span class="pulse-dot"></span>
                <span id="header-state-txt">SYSTEM READY</span>
            </div>
        </header>
        
        <div class="metrics-grid">
            <div class="metric-card" id="card-pnl">
                <label>Total P&amp;L</label>
                <div class="val">₹0.00</div>
            </div>
            <div class="metric-card" id="card-return">
                <label>Return %</label>
                <div class="val">0.00%</div>
            </div>
            <div class="metric-card">
                <label>Max Drawdown</label>
                <div class="val" id="val-dd">₹0.00</div>
            </div>
            <div class="metric-card">
                <label>Profit Factor</label>
                <div class="val" id="val-pf">0.00</div>
            </div>
            <div class="metric-card">
                <label>Total Trades</label>
                <div class="val" id="val-trades">0</div>
            </div>
            <div class="metric-card">
                <label>Win Rate %</label>
                <div class="val" id="val-winrate">0.00%</div>
            </div>
            <div class="metric-card">
                <label>Sharpe Ratio</label>
                <div class="val" id="val-sharpe">0.00</div>
            </div>
            <div class="metric-card">
                <label>Max Consec Wins</label>
                <div class="val" id="val-consec-wins">0</div>
            </div>
            <div class="metric-card">
                <label>Max Consec Losses</label>
                <div class="val" id="val-consec-losses">0</div>
            </div>
        </div>
        
        <div class="main-layout">
            <div style="display: flex; flex-direction: column; gap: 24px;">
                <div class="card" style="position: relative;">
                    <div class="chart-tabs">
                        <button id="tab-btn-equity" class="tab-btn active" onclick="switchTab('equity')">Performance Equity Curve</button>
                        <button id="tab-btn-candles" class="tab-btn" onclick="switchTab('candles')">Heikin Ashi Option Candles</button>
                    </div>
                    <div id="tab-content-equity" class="tab-content active">
                        <div id="chart"></div>
                    </div>
                    <div id="tab-content-candles" class="tab-content">
                        <div id="candle-chart" style="width: 100%; height: 380px; overflow: hidden;"></div>
                    </div>
                </div>
                <div class="card">
                    <h2>Live Trade Registry</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Entry Time</th>
                                <th>Exit Time</th>
                                <th>Entry Price</th>
                                <th>Exit Price</th>
                                <th>Exit Reason</th>
                                <th>Net P&amp;L</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody id="trade-rows">
                            <tr><td colspan="7" style="text-align:center; color: var(--text-mute);">No trades executed in this active engine instance.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div style="display: flex; flex-direction: column; gap: 24px;">
                <div class="card">
                    <h2>Deployment Control</h2>
                    
                    <div class="control-row">
                        <div class="control-item">
                            <label>Execution Mode</label>
                            <select id="exec-mode">
                                <option value="BACKTEST">Historical Backtest</option>
                                <option value="PAPER">Simulated Paper</option>
                                <option value="LIVE">Live Production</option>
                            </select>
                        </div>
                        <div class="control-item">
                            <label>Lot Size</label>
                            <input type="number" id="lot-size" value="1" min="1">
                        </div>
                    </div>
                    
                    <div class="control-item" style="margin-bottom: 16px;">
                        <label>Capital Deployed (₹)</label>
                        <input type="number" id="capital-input" value="100000" min="1000">
                    </div>
                    
                    <div class="toggle-container">
                        <span class="toggle-label">Real Upstox Execution</span>
                        <label class="switch">
                            <input type="checkbox" id="live-protection">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="control-row">
                        <div class="control-item">
                            <label>Expiry Date</label>
                            <select id="expiry-select"></select>
                        </div>
                        <div class="control-item">
                            <label>Option Type</label>
                            <select id="option-type">
                                <option value="CE">Call (CE)</option>
                                <option value="PE">Put (PE)</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="control-item" style="margin-bottom: 20px;">
                        <label>Strike Price</label>
                        <select id="strike-select"></select>
                    </div>

                    <!-- Backtesting Parameters -->
                    <div id="backtest-controls" style="border-top: 1px dashed rgba(255,255,255,0.05); padding-top: 16px; margin-top: 16px;">
                        <h3 style="font-size: 13px; text-transform: uppercase; color: var(--gold-accent); margin-bottom: 12px; letter-spacing: 0.5px;">Strategy &amp; Backtest Config</h3>
                        
                        <div class="control-row">
                            <div class="control-item">
                                <label>Strategy</label>
                                <select id="strategy-select" onchange="toggleStrategyParams()">
                                    <option value="heikin_ashi_gar">Heikin Ashi GAR</option>
                                    <option value="five_ema_scalping">5 EMA Scalping</option>
                                </select>
                            </div>
                            <div class="control-item">
                                <label>Period</label>
                                <select id="period-select" onchange="togglePeriodInputs()">
                                    <option value="custom">Custom Range</option>
                                    <option value="last_week">Last Week</option>
                                    <option value="last_month">Last Month</option>
                                    <option value="last_3_months">Last 3 Months</option>
                                    <option value="last_6_months">Last 6 Months</option>
                                    <option value="ytd">Year to Date (YTD)</option>
                                </select>
                            </div>
                        </div>

                        <div class="control-row" id="date-range-row">
                            <div class="control-item">
                                <label>Start Date</label>
                                <input type="date" id="start-date">
                            </div>
                            <div class="control-item">
                                <label>End Date</label>
                                <input type="date" id="end-date">
                            </div>
                        </div>

                        <div class="control-row" id="ha-params-row">
                            <div class="control-item">
                                <label>Max Hold (Candles)</label>
                                <input type="number" id="max-candles" value="10" min="1">
                            </div>
                            <div class="control-item">
                                <label>Cutoff Time</label>
                                <input type="text" id="cutoff-time" value="15:15" placeholder="HH:MM">
                            </div>
                        </div>

                        <div class="control-row" id="five-ema-params-row" style="display: none;">
                            <div class="control-item">
                                <label>EMA Period</label>
                                <input type="number" id="five-ema-period" value="5" min="1">
                            </div>
                            <div class="control-item">
                                <label>Risk-Reward Ratio</label>
                                <input type="number" id="five-ema-rr" value="3.0" step="0.1" min="0.1">
                            </div>
                        </div>
                        
                        <div class="control-row">
                            <div class="control-item">
                                <label>Timeframe</label>
                                <select id="timeframe-select">
                                    <option value="1minute">1 Minute</option>
                                    <option value="5minute">5 Minute</option>
                                    <option value="15minute">15 Minute</option>
                                </select>
                            </div>
                            <div class="control-item">
                                <label>Flat Brokerage (₹)</label>
                                <input type="number" id="brokerage-flat" value="20" min="0">
                            </div>
                        </div>

                        <div class="control-item" style="margin-bottom: 16px;">
                            <label>Slippage Percentage (%)</label>
                            <input type="number" id="slippage-pct" value="0.05" step="0.01" min="0">
                        </div>
                    </div>
                    
                    <button class="btn" id="start-btn" onclick="toggleEngine()">Initialize Engine Session</button>
                </div>
                
                <div class="card">
                    <h2>System Event Log</h2>
                    <div id="log-panel" class="log-panel">
                        <div class="log-entry system">Valkyrie control room ready. Initializing parameters...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let chartOptions = {
            series: [{ name: 'Account Balance', data: [100000] }],
            chart: { 
                type: 'area', 
                height: 260, 
                background: 'transparent',
                toolbar: { show: false } 
            },
            colors: ['#66fcf1'],
            dataLabels: { enabled: false },
            stroke: { curve: 'smooth', width: 2 },
            grid: { 
                borderColor: 'rgba(255,255,255,0.05)',
                padding: {
                    bottom: 0,
                    top: 0
                }
            },
            theme: { mode: 'dark' },
            xaxis: { 
                labels: { 
                    hideOverlappingLabels: true,
                    style: { colors: '#94a3b8' } 
                } 
            },
            yaxis: { 
                labels: { 
                    formatter: function(val) {
                        if (val === undefined || val === null || isNaN(val)) {
                            return '₹0.00';
                        }
                        return '₹' + parseFloat(val).toFixed(2);
                    },
                    style: { colors: '#94a3b8' } 
                } 
            }
        };
        let chart = new ApexCharts(document.querySelector("#chart"), chartOptions);
        chart.render();

        // Initialize TradingView Lightweight Chart
        let tvChart = null;
        let candleSeries = null;
        let cachedCandles = [];
        let cachedTrades = [];
        
        function initCandleChart() {
            if (typeof LightweightCharts === 'undefined') {
                console.warn("TradingView Lightweight Charts library is not loaded. Candlestick visualization will be disabled.");
                return;
            }
            try {
                const container = document.getElementById('candle-chart');
                if (!container) return;
                container.innerHTML = '';
                
                let width = container.clientWidth;
                if (!width || width === 0) {
                    const parentCard = container.closest('.card');
                    if (parentCard) {
                        width = parentCard.clientWidth - 48; // subtract padding
                    }
                }
                if (!width || width <= 0) width = 600; // fallback
                
                tvChart = LightweightCharts.createChart(container, {
                    width: width,
                    height: 380,
                    layout: {
                        background: { type: 'solid', color: 'transparent' },
                        textColor: '#94a3b8',
                        fontSize: 11,
                        fontFamily: "'Plus Jakarta Sans', sans-serif"
                    },
                    grid: {
                        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
                    },
                    crosshair: {
                        mode: LightweightCharts.CrosshairMode.Normal,
                    },
                    rightPriceScale: {
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                    },
                    timeScale: {
                        minimumHeight: 50,
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        timeVisible: true,
                        secondsVisible: false,
                        tickMarkFormatter: (time, tickMarkType, locale) => {
                            const date = new Date(time * 1000);
                            const options = { timeZone: 'Asia/Kolkata' };
                            if (tickMarkType === 0) {
                                options.year = 'numeric';
                            } else if (tickMarkType === 1) {
                                options.month = 'short';
                            } else if (tickMarkType === 2) {
                                options.day = 'numeric';
                            } else {
                                options.hour = '2-digit';
                                options.minute = '2-digit';
                                options.hour12 = false;
                            }
                            return date.toLocaleString('en-US', options);
                        }
                    },
                    localization: {
                        locale: 'en-IN',
                        timeFormatter: (time) => {
                            const date = new Date(time * 1000);
                            return date.toLocaleString('en-IN', {
                                timeZone: 'Asia/Kolkata',
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                hour12: false
                            });
                        }
                    }
                });
                
                candleSeries = tvChart.addCandlestickSeries({
                    upColor: '#2ec4b6',
                    downColor: '#ff4d4d',
                    borderVisible: false,
                    wickUpColor: '#2ec4b6',
                    wickDownColor: '#ff4d4d',
                });
                
                if (cachedCandles && cachedCandles.length > 0) {
                    renderCandlesAndMarkers(cachedCandles, cachedTrades);
                }
            } catch (e) {
                console.error("Failed to initialize TradingView chart:", e);
            }
        }
        
        function renderCandlesAndMarkers(candles, trades) {
            if (!candleSeries) return;
            try {
                candleSeries.setData(candles);
                
                let markers = [];
                let candleTimes = candles.map(c => c.time);
                
                trades.forEach(t => {
                    let ts = Math.floor(new Date(t.timestamp).getTime() / 1000);
                    
                    let closestTime = candleTimes.reduce((prev, curr) => {
                        return Math.abs(curr - ts) < Math.abs(prev - ts) ? curr : prev;
                    }, candleTimes[0]);
                    
                    if (closestTime && Math.abs(closestTime - ts) <= 300) {
                        ts = closestTime;
                    }
                    
                    if (t.type === 'BUY') {
                        markers.push({
                            time: ts,
                            position: 'belowBar',
                            color: '#2ec4b6',
                            shape: 'arrowUp',
                            text: 'BUY'
                        });
                    } else if (t.type === 'EXIT') {
                        markers.push({
                            time: ts,
                            position: 'aboveBar',
                            color: '#ff4d4d',
                            shape: 'arrowDown',
                            text: t.reason
                        });
                    }
                });
                
                markers.sort((a, b) => a.time - b.time);
                candleSeries.setMarkers(markers);
                
                // Auto-fit content to center and size candles beautifully
                if (tvChart) {
                    tvChart.timeScale().fitContent();
                }
            } catch (e) {
                console.error("Error rendering candles and markers:", e);
            }
        }
        
        initCandleChart();
        
        // Handle Tab Switching
        let currentTab = 'equity';
        function switchTab(tabName) {
            currentTab = tabName;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            if (tabName === 'equity') {
                document.getElementById('tab-btn-equity').classList.add('active');
                document.getElementById('tab-content-equity').classList.add('active');
            } else if (tabName === 'candles') {
                document.getElementById('tab-btn-candles').classList.add('active');
                document.getElementById('tab-content-candles').classList.add('active');
                
                if (!tvChart) {
                    initCandleChart();
                } else {
                    const container = document.getElementById('candle-chart');
                    let width = container.clientWidth;
                    if (!width || width === 0) {
                        const parentCard = container.closest('.card');
                        if (parentCard) {
                            width = parentCard.clientWidth - 48;
                        }
                    }
                    if (width && width > 0) {
                        tvChart.resize(width, 380);
                    }
                    tvChart.timeScale().fitContent();
                }
            }
        }
        
        window.addEventListener('resize', () => {
            if (tvChart) {
                const container = document.getElementById('candle-chart');
                let width = container.clientWidth;
                if (!width || width === 0) {
                    const parentCard = container.closest('.card');
                    if (parentCard) {
                        width = parentCard.clientWidth - 48;
                    }
                }
                if (width && width > 0) {
                    tvChart.resize(width, 380);
                }
            }
        });

        let isRunning = false;

        // Set default dates
        const today = new Date();
        const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        document.getElementById("start-date").value = lastWeek.toISOString().split('T')[0];
        document.getElementById("end-date").value = today.toISOString().split('T')[0];

        function toggleStrategyParams() {
            const strategy = document.getElementById("strategy-select").value;
            const haRow = document.getElementById("ha-params-row");
            const fiveEmaRow = document.getElementById("five-ema-params-row");
            
            if (strategy === "heikin_ashi_gar") {
                haRow.style.display = "flex";
                fiveEmaRow.style.display = "none";
            } else {
                haRow.style.display = "none";
                fiveEmaRow.style.display = "flex";
            }
        }

        function togglePeriodInputs() {
            const period = document.getElementById("period-select").value;
            const dateRow = document.getElementById("date-range-row");
            if (period === "custom") {
                dateRow.style.display = "flex";
            } else {
                dateRow.style.display = "none";
            }
        }

        toggleStrategyParams();
        togglePeriodInputs();
        updateTelemetry();

        // Fetch instrument metadata
        fetch('/api/instruments')
        .then(res => res.json())
        .then(expiries => {
            const expSelect = document.getElementById("expiry-select");
            expiries.forEach(exp => {
                let opt = document.createElement("option");
                opt.value = exp;
                opt.innerText = exp;
                expSelect.appendChild(opt);
            });
            updateStrikes();
        });

        document.getElementById("expiry-select").addEventListener("change", updateStrikes);
        document.getElementById("option-type").addEventListener("change", updateStrikes);

        function toggleDetails(rowId) {
            const el = document.getElementById(rowId);
            if (el.style.display === 'none') {
                el.style.display = 'table-row';
            } else {
                el.style.display = 'none';
            }
        }

        function updateStrikes() {
            const expiry = document.getElementById("expiry-select").value;
            const type = document.getElementById("option-type").value;
            if(!expiry || !type) return;

            fetch(`/api/strikes?expiry=${expiry}&type=${type}`)
            .then(res => res.json())
            .then(strikes => {
                const strikeSelect = document.getElementById("strike-select");
                strikeSelect.innerHTML = '';
                
                // Add Dynamic ATM option first
                let atmOpt = document.createElement("option");
                atmOpt.value = "ATM";
                atmOpt.innerText = "Dynamic At-The-Money (ATM)";
                strikeSelect.appendChild(atmOpt);

                strikes.forEach(s => {
                    let opt = document.createElement("option");
                    opt.value = s;
                    opt.innerText = s;
                    strikeSelect.appendChild(opt);
                });
            });
        }

        function toggleEngine() {
            const btn = document.getElementById("start-btn");
            btn.disabled = true;
            if(!isRunning) {
                const mode = document.getElementById("exec-mode").value;
                const lotSize = document.getElementById("lot-size").value;
                const liveProtection = document.getElementById("live-protection").checked;
                const expiry = document.getElementById("expiry-select").value;
                const type = document.getElementById("option-type").value;
                const strike = document.getElementById("strike-select").value;
                
                const start_date = document.getElementById("start-date").value;
                const end_date = document.getElementById("end-date").value;
                const timeframe = document.getElementById("timeframe-select").value;
                const max_candles = document.getElementById("max-candles").value;
                const cutoff_time = document.getElementById("cutoff-time").value;
                const brokerage_flat = document.getElementById("brokerage-flat").value;
                const slippage_pct = document.getElementById("slippage-pct").value;
                const initial_balance = document.getElementById("capital-input").value;
                
                const strategy = document.getElementById("strategy-select").value;
                const period_type = document.getElementById("period-select").value;
                const five_ema_period = document.getElementById("five-ema-period").value;
                const five_ema_rr = document.getElementById("five-ema-rr").value;

                fetch('/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        mode: mode,
                        lot_size: lotSize,
                        live_protection: liveProtection,
                        expiry: expiry,
                        option_type: type,
                        strike: strike,
                        start_date: start_date,
                        end_date: end_date,
                        timeframe: timeframe,
                        max_candles: max_candles,
                        cutoff_time: cutoff_time,
                        brokerage_flat: brokerage_flat,
                        slippage_pct: slippage_pct,
                        initial_balance: initial_balance,
                        strategy: strategy,
                        period_type: period_type,
                        five_ema_period: five_ema_period,
                        five_ema_rr: five_ema_rr
                    })
                })
                .then(res => res.json())
                .then(data => {
                    btn.disabled = false;
                    if(data.error) {
                        alert(data.error);
                        return;
                    }
                    isRunning = true;
                    btn.innerText = "Shutdown Engine Routine";
                    btn.className = "btn stop";
                    
                    // Reset UI metrics and charts immediately for the new session
                    document.getElementById("card-pnl").querySelector(".val").innerText = "₹0.00";
                    document.getElementById("card-pnl").className = "metric-card";
                    document.getElementById("card-return").querySelector(".val").innerText = "0.00%";
                    document.getElementById("card-return").className = "metric-card";
                    document.getElementById("val-dd").innerText = "₹0.00";
                    document.getElementById("val-pf").innerText = "0.00";
                    document.getElementById("val-trades").innerText = "0";
                    document.getElementById("val-winrate").innerText = "0.00%";
                    document.getElementById("val-sharpe").innerText = "0.00";
                    document.getElementById("val-consec-wins").innerText = "0";
                    document.getElementById("val-consec-losses").innerText = "0";
                    document.getElementById("trade-rows").innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-mute);">No trades executed in this active engine instance.</td></tr>';
                    
                    cachedCandles = [];
                    cachedTrades = [];
                    if (candleSeries) {
                        candleSeries.setData([]);
                    }
                    
                    const startCapital = parseFloat(initial_balance) || 100000;
                    chart.updateSeries([{ name: 'Account Balance', data: [startCapital] }]);
                    
                    updateTelemetry();
                })
                .catch(err => {
                    btn.disabled = false;
                });
            } else {
                fetch('/stop', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    btn.disabled = false;
                    isRunning = false;
                    btn.innerText = "Initialize Engine Session";
                    btn.className = "btn";
                })
                .catch(err => {
                    btn.disabled = false;
                });
            }
        }

        function updateTelemetry() {
            fetch('/telemetry')
            .then(res => res.json())
            .then(data => {
                // Update system indicator state
                document.getElementById("header-state-txt").innerText = data.status.state + " - " + data.status.mode;
                
                // Update metrics cards
                const pnlCard = document.getElementById("card-pnl");
                pnlCard.querySelector(".val").innerText = "₹" + data.status.total_pnl.toFixed(2);
                pnlCard.className = "metric-card " + (data.status.total_pnl >= 0 ? "positive" : "negative");

                const retCard = document.getElementById("card-return");
                retCard.querySelector(".val").innerText = data.status.return_percent.toFixed(2) + "%";
                retCard.className = "metric-card " + (data.status.return_percent >= 0 ? "positive" : "negative");

                document.getElementById("val-dd").innerText = "₹" + data.status.max_drawdown.toFixed(2);
                document.getElementById("val-pf").innerText = data.status.profit_factor.toFixed(2);
                document.getElementById("val-trades").innerText = data.status.total_trades;
                document.getElementById("val-winrate").innerText = data.status.win_rate.toFixed(2) + "%";
                
                document.getElementById("val-sharpe").innerText = data.status.sharpe_ratio.toFixed(2);
                document.getElementById("val-consec-wins").innerText = data.status.max_consec_wins;
                document.getElementById("val-consec-losses").innerText = data.status.max_consec_losses;

                   if(data.trades.length > 0) {
                    let roundTrips = [];
                    let activeBuy = null;
                    
                    data.trades.forEach(t => {
                        if (t.type === 'BUY') {
                            activeBuy = t;
                        } else if (t.type === 'EXIT' && activeBuy) {
                            roundTrips.push({
                                entryTime: activeBuy.timestamp,
                                exitTime: t.timestamp,
                                entryPrice: activeBuy.price,
                                exitPrice: t.price,
                                reason: t.reason,
                                pnl: t.pnl,
                                entryDetails: activeBuy.details || '—',
                                exitDetails: t.details || '—',
                                entrySL: activeBuy.sl || 0
                            });
                            activeBuy = null;
                        }
                    });
                    
                    if (activeBuy) {
                        roundTrips.push({
                            entryTime: activeBuy.timestamp,
                            exitTime: 'ACTIVE',
                            entryPrice: activeBuy.price,
                            exitPrice: null,
                            reason: 'OPEN POSITION',
                            pnl: null,
                            entryDetails: activeBuy.details || '—',
                            exitDetails: 'Position is currently open and monitoring market data.',
                            entrySL: activeBuy.sl || 0
                        });
                    }
                    
                    if (roundTrips.length > 0) {
                        let html = '';
                        roundTrips.reverse().forEach((rt, index) => {
                            let pnlStr = rt.pnl !== null ? `₹${rt.pnl.toFixed(2)}` : '—';
                            let pnlColor = rt.pnl !== null ? (rt.pnl >= 0 ? 'var(--green-glow)' : 'var(--red-glow)') : '#fff';
                            let exitPriceStr = rt.exitPrice !== null ? `₹${rt.exitPrice.toFixed(2)}` : '—';
                            let detailsId = `details-${index}`;
                            
                            html += `<tr style="cursor: pointer;" onclick="toggleDetails('${detailsId}')">
                                <td>${rt.entryTime}</td>
                                <td>${rt.exitTime}</td>
                                <td>₹${rt.entryPrice.toFixed(2)}</td>
                                <td>${exitPriceStr}</td>
                                <td><span style="color:${rt.reason=='STOP_LOSS'?'#ff4d4d':'#fff'}; font-weight: 500;">${rt.reason}</span></td>
                                <td><span style="color:${pnlColor}; font-weight: 700;">${pnlStr}</span></td>
                                <td style="text-align: center;"><button class="btn-toggle-details">ℹ️ Info</button></td>
                            </tr>
                            <tr id="${detailsId}" class="details-row" style="display: none; background: rgba(14, 20, 36, 0.95); border-left: 3px solid var(--cyan-neon);">
                                <td colspan="7">
                                    <div class="details-container" style="padding: 16px; font-family: 'Plus Jakarta Sans', sans-serif; text-align: left; font-size: 0.9rem;">
                                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                                            <div style="border-right: 1px solid rgba(255, 255, 255, 0.1); padding-right: 16px;">
                                                <h4 style="color: var(--cyan-neon); margin-bottom: 8px; font-size: 0.95rem; letter-spacing: 0.5px;">🟢 ENTRY SEQUENCE DETAILS</h4>
                                                <p style="margin: 4px 0;"><strong>Time:</strong> ${rt.entryTime}</p>
                                                <p style="margin: 4px 0;"><strong>Execution Price:</strong> ₹${rt.entryPrice.toFixed(2)}</p>
                                                <p style="margin: 4px 0;"><strong>Initial Stop Loss:</strong> ₹${rt.entrySL.toFixed(2)} (Anchored at raw open of prior red candle)</p>
                                                <p style="color: rgba(255,255,255,0.7); margin-top: 8px; line-height: 1.4; font-style: italic;">"${rt.entryDetails}"</p>
                                            </div>
                                            <div>
                                                <h4 style="color: ${rt.reason == 'STOP_LOSS' ? '#ff4d4d' : 'var(--teal-neon)'}; margin-bottom: 8px; font-size: 0.95rem; letter-spacing: 0.5px;">🔴 EXIT SEQUENCE DETAILS</h4>
                                                <p style="margin: 4px 0;"><strong>Time:</strong> ${rt.exitTime}</p>
                                                <p style="margin: 4px 0;"><strong>Execution Price:</strong> ${exitPriceStr}</p>
                                                <p style="margin: 4px 0;"><strong>Exit Condition:</strong> <span style="text-transform: uppercase; font-weight: 600;">${rt.reason}</span></p>
                                                <p style="color: rgba(255,255,255,0.7); margin-top: 8px; line-height: 1.4; font-style: italic;">"${rt.exitDetails}"</p>
                                            </div>
                                        </div>
                                    </div>
                                </td>
                            </tr>`;
                        });
                        document.getElementById("trade-rows").innerHTML = html;
                    }
                }

                // Update event log
                const logPanel = document.getElementById("log-panel");
                logPanel.innerHTML = '';
                data.logs.forEach(l => {
                    let className = 'log-entry';
                    if (l.includes('[TRADE]')) className += ' trade';
                    else if (l.includes('[ERROR]') || l.includes('[ORDER]')) className += ' error';
                    else if (l.includes('[SYSTEM]') || l.includes('[BACKTEST]')) className += ' system';
                    
                    let div = document.createElement("div");
                    div.className = className;
                    div.innerText = l;
                    logPanel.appendChild(div);
                });
                logPanel.scrollTop = logPanel.scrollHeight;

                // Update chart
                let initialCapital = data.status.initial_balance || 100000;
                let balancePoints = [initialCapital];
                let currentVal = initialCapital;
                data.trades.forEach(t => {
                    if (t.type === 'EXIT') {
                        currentVal += (t.pnl || 0);
                        balancePoints.push(currentVal);
                    }
                });
                chart.updateSeries([{ name: 'Account Balance', data: balancePoints }]);

                // Update Heikin Ashi Candlestick Chart
                if (data.candles && data.candles.length > 0) {
                    cachedCandles = data.candles;
                    cachedTrades = data.trades;
                    
                    if (candleSeries) {
                        renderCandlesAndMarkers(cachedCandles, cachedTrades);
                    }
                }

                if (["PROCESSING", "LIVE_MONITORING", "RUNNING_BACKTEST"].includes(data.status.state)) {
                    isRunning = true;
                    const btn = document.getElementById("start-btn");
                    btn.innerText = "Shutdown Engine Routine";
                    btn.className = "btn stop";
                } else {
                    isRunning = false;
                    const btn = document.getElementById("start-btn");
                    btn.innerText = "Initialize Engine Session";
                    btn.className = "btn";
                }

                if (isRunning) {
                    setTimeout(updateTelemetry, 2000);
                }
            });
        }

    </script>
</body>
</html>
"""

HTML_PAPER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Valkyrie - Paper Trading Desk</title>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-deep: #080b11;
            --bg-card: rgba(22, 28, 45, 0.7);
            --border-glow: rgba(102, 252, 241, 0.2);
            --cyan-neon: #66fcf1;
            --teal-neon: #45a29e;
            --green-glow: #2ec4b6;
            --red-glow: #ff4d4d;
            --text-main: #e2e8f0;
            --text-mute: #94a3b8;
        }
        * { box-sizing: border-box; }
        body { 
            font-family: 'Plus Jakarta Sans', sans-serif; 
            background: var(--bg-deep); 
            color: var(--text-main); 
            margin: 0; 
            padding: 24px;
            background-image: radial-gradient(circle at 10% 20%, rgba(102, 252, 241, 0.05) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(197, 168, 128, 0.05) 0%, transparent 40%);
        }
        .container { max-width: 1500px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
        header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 16px 20px; 
            background: var(--bg-card); 
            border: 1px solid var(--border-glow); 
            border-radius: 12px;
            backdrop-filter: blur(10px);
        }
        header h1 { margin: 0; font-size: 20px; font-weight: 700; color: var(--cyan-neon); letter-spacing: 0.5px; }
        .pulsing-indicator { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; }
        .pulse-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--green-glow); box-shadow: 0 0 10px var(--green-glow); }
        .pulse-dot.idle { background: var(--text-mute); box-shadow: none; }
        
        /* Metrics Grid */
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }
        .metric-card { 
            background: var(--bg-card); 
            border: 1px solid rgba(255,255,255,0.05); 
            border-radius: 10px; 
            padding: 14px; 
            text-align: center;
            backdrop-filter: blur(10px);
            transition: border-color 0.3s;
        }
        .metric-card label { font-size: 10px; text-transform: uppercase; color: var(--text-mute); letter-spacing: 1px; }
        .metric-card .val { font-size: 18px; font-weight: 700; margin-top: 6px; color: #fff; font-family: 'JetBrains Mono', monospace; }
        .metric-card.positive .val { color: var(--green-glow); }
        .metric-card.negative .val { color: var(--red-glow); }
        
        .main-layout { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
        
        .card { 
            background: var(--bg-card); 
            border: 1px solid rgba(255,255,255,0.05); 
            border-radius: 12px; 
            padding: 20px;
            backdrop-filter: blur(10px);
            margin-bottom: 20px;
        }
        .card h2 { margin-top: 0; color: var(--cyan-neon); font-size: 15px; font-weight: 600; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 8px; margin-bottom: 14px; }
        
        /* Form Controls */
        .control-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
        .control-item { display: flex; flex-direction: column; gap: 6px; }
        .control-item label { font-size: 10px; text-transform: uppercase; color: var(--text-mute); }
        input, select { 
            background: rgba(11, 16, 26, 0.8); 
            border: 1px solid rgba(255,255,255,0.1); 
            color: #fff; 
            padding: 8px 12px; 
            border-radius: 6px; 
            font-size: 13px;
            outline: none;
            transition: all 0.3s;
        }
        input:focus, select:focus { border-color: var(--cyan-neon); }
        
        .btn { 
            background: linear-gradient(135deg, #1f4068, #162447); 
            border: 1px solid var(--border-glow); 
            color: #fff; 
            padding: 10px 20px; 
            border-radius: 6px; 
            font-size: 13px; 
            font-weight: 600; 
            cursor: pointer; 
            transition: all 0.3s;
            width: 100%;
        }
        .btn:hover { background: linear-gradient(135deg, #162447, #1f4068); border-color: var(--cyan-neon); box-shadow: 0 0 10px rgba(102, 252, 241, 0.2); }
        .btn-stop { background: linear-gradient(135deg, #721c24, #a71d2a) !important; border-color: rgba(255, 77, 77, 0.3) !important; }
        .btn-stop:hover { box-shadow: 0 0 10px rgba(255, 77, 77, 0.3) !important; }
        
        /* Active Position Widget */
        .pos-banner {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            border-radius: 8px;
            background: rgba(255,255,255,0.02);
            border: 1px dashed rgba(255,255,255,0.1);
        }
        .pos-banner.long {
            background: rgba(46, 196, 182, 0.05);
            border-color: rgba(46, 196, 182, 0.2);
            border-style: solid;
        }
        
        /* Terminal Log */
        .terminal { 
            background: rgba(5, 8, 15, 0.9); 
            border: 1px solid rgba(255,255,255,0.05); 
            border-radius: 8px; 
            height: 250px; 
            overflow-y: auto; 
            padding: 12px; 
            font-family: 'JetBrains Mono', monospace; 
            font-size: 11px; 
            line-height: 1.5; 
            color: var(--text-main);
        }
        
        /* Table Styles */
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { font-size: 10px; text-transform: uppercase; color: var(--text-mute); padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        td { padding: 10px 12px; font-size: 12px; border-bottom: 1px solid rgba(255,255,255,0.03); }
        tr:hover td { background: rgba(255,255,255,0.01); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div style="display: flex; align-items: center; gap: 24px;">
                <h1>Valkyrie Paper Trading Desk</h1>
                <div style="display: flex; gap: 8px; background: rgba(255,255,255,0.02); padding: 4px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                    <a href="/" style="text-decoration: none; padding: 6px 12px; font-size: 12px; font-weight: 600; color: var(--text-mute); border-radius: 6px; border: 1px solid transparent; transition: all 0.2s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-mute)'">Backtest & Tuner</a>
                    <a href="/paper" style="text-decoration: none; padding: 6px 12px; font-size: 12px; font-weight: 600; color: var(--cyan-neon); background: rgba(102, 252, 241, 0.05); border-radius: 6px; border: 1px solid rgba(102,252,241,0.2);">Live Paper Trading</a>
                    <a href="/manual" style="text-decoration: none; padding: 6px 12px; font-size: 12px; font-weight: 600; color: var(--text-mute); border-radius: 6px; border: 1px solid transparent; transition: all 0.2s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-mute)'">Manual Order Desk</a>
                </div>
            </div>
            <div class="pulsing-indicator">
                <span class="pulse-dot idle" id="pulse-indicator"></span>
                <span id="header-state-txt">READY</span>
            </div>
        </header>
        
        <div class="metrics-grid">
            <div class="metric-card" id="card-pnl">
                <label>Total P&amp;L</label>
                <div class="val" id="val-pnl">₹0.00</div>
            </div>
            <div class="metric-card" id="card-return">
                <label>Return %</label>
                <div class="val" id="val-return">0.00%</div>
            </div>
            <div class="metric-card">
                <label>Option Premium LTP</label>
                <div class="val" id="val-spot">₹0.00</div>
            </div>
            <div class="metric-card">
                <label>Balance</label>
                <div class="val" id="val-balance">₹100,000.00</div>
            </div>
            <div class="metric-card">
                <label>Win Rate</label>
                <div class="val" id="val-winrate">0.00%</div>
            </div>
            <div class="metric-card">
                <label>Total Trades</label>
                <div class="val" id="val-trades">0</div>
            </div>
        </div>
        
        <div class="main-layout">
            <div>
                <!-- Active Position Details -->
                <div class="card" style="padding-bottom: 16px;">
                    <h2>Active Position State</h2>
                    <div id="pos-container" class="pos-banner">
                        <div style="font-size: 13px; font-weight: 600; color: var(--text-mute);" id="pos-status-text">FLAT / NO ACTIVE POSITION</div>
                        <div id="pos-details" style="display: none; align-items: center; gap: 20px;">
                            <div style="font-size: 12px;"><span style="color: var(--text-mute)">Entry:</span> <strong style="font-family: 'JetBrains Mono', monospace;" id="pos-entry-val">₹0.00</strong></div>
                            <div style="font-size: 12px;"><span style="color: var(--text-mute)">SL:</span> <strong style="font-family: 'JetBrains Mono', monospace; color: var(--red-glow);" id="pos-sl-val">₹0.00</strong></div>
                            <div style="font-size: 13px; font-weight: 700;" id="pos-pnl-val">₹0.00</div>
                        </div>
                    </div>
                </div>
                
                <!-- Candlestick Chart -->
                <div class="card">
                    <h2>Live Option Candles</h2>
                    <div id="chart-ha" style="min-height: 260px;"></div>
                </div>
                
                <!-- Trade Log Registry -->
                <div class="card">
                    <h2>Trade Log Registry</h2>
                    <div style="max-height: 220px; overflow-y: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Type</th>
                                    <th>Price</th>
                                    <th>Net P&amp;L</th>
                                    <th>Reason / Details</th>
                                </tr>
                            </thead>
                            <tbody id="trade-tbody">
                                <tr>
                                    <td colspan="5" style="text-align: center; color: var(--text-mute);">No trades executed in this paper session.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div>
                <!-- Deployment Control Card -->
                <div class="card">
                    <h2>Desk Controls</h2>
                    
                    <div class="control-row">
                        <div class="control-item">
                            <label>Expiry Date</label>
                            <select id="ctrl-expiry" onchange="loadStrikes()"></select>
                        </div>
                        <div class="control-item">
                            <label>Option Type</label>
                            <select id="ctrl-type" onchange="loadStrikes()">
                                <option value="CE">Call (CE)</option>
                                <option value="PE">Put (PE)</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="control-row">
                        <div class="control-item">
                            <label>Strike Price</label>
                            <select id="ctrl-strike"></select>
                        </div>
                        <div class="control-item">
                            <label>Lot Size</label>
                            <input type="number" id="ctrl-lots" value="1" min="1">
                        </div>
                    </div>
                    
                    <div class="control-row">
                        <div class="control-item">
                            <label>Max Hold (Candles)</label>
                            <input type="number" id="ctrl-max-hold" value="10" min="1">
                        </div>
                        <div class="control-item">
                            <label>Session Cutoff</label>
                            <input type="text" id="ctrl-cutoff" value="15:15">
                        </div>
                    </div>
                    
                    <div class="control-item" style="margin-bottom: 16px;">
                        <label>Paper Balance (₹)</label>
                        <input type="number" id="ctrl-balance" value="100000" step="10000">
                    </div>
                    
                    <button class="btn" id="start-btn" onclick="toggleEngine()">Start Trading Desk</button>
                </div>
                
                <!-- System Events Log -->
                <div class="card">
                    <h2>Desk Console Logs</h2>
                    <div class="terminal" id="log-terminal">
                        [DESK] Ready to initialize paper stream...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let isRunning = false;
        let chart = null;

        // Initialize empty chart
        const chartOptions = {
            series: [{ data: [] }],
            chart: {
                type: 'candlestick',
                height: 260,
                background: 'transparent',
                toolbar: { show: false }
            },
            theme: { mode: 'dark' },
            grid: {
                borderColor: 'rgba(255,255,255,0.05)',
                padding: { top: 0, bottom: 0, left: 10, right: 10 }
            },
            xaxis: {
                type: 'datetime',
                labels: {
                    style: { colors: '#94a3b8', fontSize: '10px' },
                    datetimeUTC: false
                }
            },
            yaxis: {
                labels: {
                    style: { colors: '#94a3b8', fontSize: '10px' },
                    formatter: function(val) { return val ? '₹' + parseFloat(val).toFixed(2) : ''; }
                }
            },
            plotOptions: {
                candlestick: {
                    colors: {
                        upward: '#2ec4b6',
                        downward: '#ff4d4d'
                    }
                }
            }
        };

        chart = new ApexCharts(document.querySelector("#chart-ha"), chartOptions);
        chart.render();
        updateTelemetry();

        // Load instrument expiries on startup
        fetch('/api/instruments')
            .then(r => r.json())
            .then(data => {
                const select = document.getElementById("ctrl-expiry");
                select.innerHTML = "";
                data.forEach(d => {
                    const opt = document.createElement("option");
                    opt.value = d;
                    opt.innerText = d;
                    select.appendChild(opt);
                });
                loadStrikes();
            });

        function loadStrikes() {
            const expiry = document.getElementById("ctrl-expiry").value;
            const type = document.getElementById("ctrl-type").value;
            if (!expiry) return;
            fetch(`/api/strikes?expiry=${expiry}&type=${type}`)
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById("ctrl-strike");
                    select.innerHTML = '<option value="ATM">Dynamic ATM Strike</option>';
                    data.forEach(d => {
                        const opt = document.createElement("option");
                        opt.value = d;
                        opt.innerText = d;
                        select.appendChild(opt);
                    });
                });
        }

        function toggleEngine() {
            const btn = document.getElementById("start-btn");
            if (!isRunning) {
                // Prepare Payload
                const payload = {
                    mode: "PAPER",
                    expiry: document.getElementById("ctrl-expiry").value,
                    option_type: document.getElementById("ctrl-type").value,
                    strike: document.getElementById("ctrl-strike").value,
                    lot_size: parseInt(document.getElementById("ctrl-lots").value),
                    max_candles: parseInt(document.getElementById("ctrl-max-hold").value),
                    cutoff_time: document.getElementById("ctrl-cutoff").value,
                    initial_balance: parseFloat(document.getElementById("ctrl-balance").value)
                };

                btn.innerText = "Connecting Feed...";
                btn.disabled = true;

                fetch('/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        btn.innerText = "Start Trading Desk";
                        btn.disabled = false;
                    } else {
                        isRunning = true;
                        btn.disabled = false;
                        btn.innerText = "Stop Trading Desk";
                        btn.className = "btn btn-stop";
                        
                        document.getElementById("pulse-indicator").className = "pulse-dot";
                        document.getElementById("header-state-txt").innerText = "LIVE MONITORING";
                        
                        updateTelemetry();
                    }
                });
            } else {
                btn.innerText = "Stopping Feed...";
                btn.disabled = true;
                fetch('/stop', { method: 'POST' })
                    .then(r => r.json())
                    .then(() => {
                        isRunning = false;
                        btn.disabled = false;
                        btn.innerText = "Start Trading Desk";
                        btn.className = "btn";
                        
                        document.getElementById("pulse-indicator").className = "pulse-dot idle";
                        document.getElementById("header-state-txt").innerText = "DISCONNECTED";
                    });
            }
        }

        function updateTelemetry() {
            fetch('/telemetry')
            .then(r => r.json())
            .then(data => {
                // Update basic stats
                document.getElementById("val-pnl").innerText = "₹" + data.status.total_pnl.toFixed(2);
                document.getElementById("val-return").innerText = data.status.return_percent.toFixed(2) + "%";
                document.getElementById("val-spot").innerText = "₹" + data.status.spot_price.toFixed(2);
                document.getElementById("val-balance").innerText = "₹" + data.status.balance.toLocaleString('en-IN', {minimumFractionDigits: 2});
                document.getElementById("val-winrate").innerText = data.status.win_rate.toFixed(2) + "%";
                document.getElementById("val-trades").innerText = data.status.total_trades;

                // Update positive/negative classes
                const pnlCard = document.getElementById("card-pnl");
                const returnCard = document.getElementById("card-return");
                if (data.status.total_pnl > 0) {
                    pnlCard.className = "metric-card positive";
                    returnCard.className = "metric-card positive";
                } else if (data.status.total_pnl < 0) {
                    pnlCard.className = "metric-card negative";
                    returnCard.className = "metric-card negative";
                } else {
                    pnlCard.className = "metric-card";
                    returnCard.className = "metric-card";
                }

                // Update Active Position Widget
                const posContainer = document.getElementById("pos-container");
                const posStatusText = document.getElementById("pos-status-text");
                const posDetails = document.getElementById("pos-details");
                if (data.status.position) {
                    posContainer.className = "pos-banner long";
                    posStatusText.innerText = "LONG | " + data.status.trading_symbol;
                    posDetails.style.display = "flex";
                    
                    document.getElementById("pos-entry-val").innerText = "₹" + data.status.position.entry_price.toFixed(2);
                    document.getElementById("pos-sl-val").innerText = "₹" + data.status.position.stop_loss.toFixed(2);
                    
                    const openPnl = (data.status.spot_price - data.status.position.entry_price) * (data.status.lot_size * (data.status.lot_size_multiplier || 75));
                    const pnlValEl = document.getElementById("pos-pnl-val");
                    pnlValEl.innerText = (openPnl >= 0 ? "+" : "") + "₹" + openPnl.toFixed(2);
                    pnlValEl.style.color = openPnl >= 0 ? "var(--green-glow)" : "var(--red-glow)";
                } else {
                    posContainer.className = "pos-banner";
                    posStatusText.innerText = "FLAT / NO ACTIVE POSITION";
                    posDetails.style.display = "none";
                }

                // Update Trade Registry table
                const tbody = document.getElementById("trade-tbody");
                if (data.trades.length > 0) {
                    tbody.innerHTML = "";
                    data.trades.forEach(t => {
                        const tr = document.createElement("tr");
                        const pnlVal = t.pnl !== undefined ? t.pnl : 0;
                        const pnlText = t.type === "EXIT" ? (pnlVal >= 0 ? "+" : "") + "₹" + pnlVal.toFixed(2) : "-";
                        const pnlStyle = t.type === "EXIT" ? (pnlVal >= 0 ? "color: var(--green-glow); font-weight:600;" : "color: var(--red-glow); font-weight:600;") : "";
                        
                        tr.innerHTML = `
                            <td style="font-family: 'JetBrains Mono', monospace;">${t.timestamp}</td>
                            <td><span style="padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; background: ${t.type === 'BUY' ? 'rgba(46,196,182,0.1)' : 'rgba(255,77,77,0.1)'}; color: ${t.type === 'BUY' ? 'var(--green-glow)' : 'var(--red-glow)'};">${t.type}</span></td>
                            <td style="font-family: 'JetBrains Mono', monospace;">₹${t.price.toFixed(2)}</td>
                            <td style="${pnlStyle}">${pnlText}</td>
                            <td>${t.reason} ${t.details ? '(' + t.details + ')' : ''}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-mute);">No trades executed in this paper session.</td></tr>';
                }

                // Update console log
                const logTerm = document.getElementById("log-terminal");
                logTerm.innerHTML = data.logs.join("<br>");
                logTerm.scrollTop = logTerm.scrollHeight;

                // Update series of Candlestick Chart
                if (data.candles.length > 0) {
                    const formattedCandles = data.candles.map(c => ({
                        x: new Date(c.time * 1000),
                        y: [c.open, c.high, c.low, c.close]
                    }));
                    chart.updateSeries([{ data: formattedCandles }]);
                }

                if (["PROCESSING", "LIVE_MONITORING", "RUNNING_BACKTEST"].includes(data.status.state)) {
                    isRunning = true;
                    const startBtn = document.getElementById("start-btn");
                    startBtn.innerText = "Stop Trading Desk";
                    startBtn.className = "btn stop";
                    document.getElementById("pulse-indicator").className = "pulse-dot active";
                    document.getElementById("header-state-txt").innerText = "LIVE MONITORING";
                } else {
                    isRunning = false;
                    const startBtn = document.getElementById("start-btn");
                    startBtn.innerText = "Start Trading Desk";
                    startBtn.className = "btn";
                    document.getElementById("pulse-indicator").className = "pulse-dot idle";
                    document.getElementById("header-state-txt").innerText = "READY";
                }

                if (isRunning) {
                    setTimeout(updateTelemetry, 2000);
                }
            });
        }
    </script>
</body>
</html>
"""


HTML_MANUAL_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>VALKYRIE // TACTICAL TRADING WORKSTATION</title>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            /* Rosé Pine Palette - Dark (Default) */
            --bg-deep: #16141f;
            --bg-card: #232136;
            --border-glow: #393552;
            --text-main: #e0def4;
            --text-mute: #908caa;
            --green-glow: #3fd18a;
            --red-glow: #eb6f92;
            --accent: #3fd18a;
            --accent-red: #eb6f92;
            --header-bg: #1f1d2e;
            --btn-hover: #2a283e;
            --accent-blue: #7aa2f7;
            --accent-amber: #f6c177;
            --atm-glow: rgba(246, 193, 119, 0.12);
            --font-family-sans: 'Inter', sans-serif;
            --font-family-header: 'IBM Plex Sans', sans-serif;
            --font-family-mono: 'JetBrains Mono', monospace;
        }

        body.light-theme {
            /* Muted Japanese Minimalism / Sepia Paper */
            --bg-deep: #faf4ed;
            --bg-card: #fffaf3;
            --border-glow: #ddd6cf;
            --text-main: #575279;
            --text-mute: #797593;
            --green-glow: #2e8b57;
            --red-glow: #c94f6d;
            --accent: #2e8b57;
            --accent-red: #c94f6d;
            --header-bg: #f2e9e1;
            --btn-hover: #ddd6cf;
            --accent-blue: #4c6fff;
            --accent-amber: #d98e04;
            --atm-glow: rgba(217, 142, 4, 0.1);
        }

        * { box-sizing: border-box; }
        body { 
            font-family: var(--font-family-sans); 
            font-size: 13.5px;
            background: var(--bg-deep); 
            color: var(--text-main); 
            margin: 0; 
            padding: 0;
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
            transition: background 0.4s, color 0.4s;
        }

        /* Layout Grid */
        .terminal-container {
            display: flex;
            width: 100vw;
            height: calc(100vh - 48px);
            overflow: hidden;
        }

        /* Cockpit Header */
        .hud-header {
            height: 48px;
            background: var(--header-bg);
            border-bottom: 1px solid var(--border-glow);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            font-family: var(--font-family-header);
        }
        
        .header-title {
            font-weight: 700;
            font-size: 14.5px;
            letter-spacing: 1px;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .header-title span.brand {
            color: var(--accent-blue);
            border-right: 1px solid var(--border-glow);
            padding-right: 12px;
        }

        .hud-info-grid {
            display: flex;
            align-items: center;
            gap: 24px;
            font-family: var(--font-family-mono);
            font-size: 11.5px;
        }

        .hud-info-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .hud-info-label {
            color: var(--text-mute);
        }

        .hud-info-val {
            font-weight: 700;
            color: var(--text-main);
        }

        .hud-info-val.pulse {
            animation: text-pulse 2s infinite;
        }

        @keyframes text-pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; color: var(--accent-amber); }
            100% { opacity: 0.8; }
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Left and Right Panes */
        .left-pane {
            width: 76%;
            height: 100%;
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--border-glow);
            padding: 12px;
            gap: 12px;
        }

        .right-pane {
            width: 24%;
            height: 100%;
            background: var(--bg-deep);
            display: flex;
            flex-direction: column;
            padding: 12px;
            gap: 12px;
            overflow-y: auto;
        }

        /* Cards & Tabs */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-glow);
            border-radius: 6px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            position: relative;
        }

        .workspace-area {
            display: flex;
            gap: 12px;
            flex: 1;
            min-height: 0;
        }

        .dom-card {
            width: 25%;
            min-width: 240px;
            max-width: 320px;
            height: 100%;
        }

        .chart-card {
            flex: 1;
            height: 100%;
            overflow: visible;
            min-height: 0;
        }

        .lower-tabs-card {
            height: 250px;
            min-height: 48px;
            transition: height 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .lower-tabs-card.minimized {
            height: 48px !important;
        }

        .lower-tabs-card.maximized {
            height: 50vh !important;
        }

        .lower-tabs-card.minimized .panel-content-area {
            display: none !important;
        }

        .panel-content-area {
            flex: 1;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            margin-top: 10px;
        }

        .tabs-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-glow);
            padding-bottom: 8px;
        }

        .tabs-list {
            display: flex;
            gap: 6px;
        }

        .tab-btn {
            background: none;
            border: none;
            color: var(--text-mute);
            font-family: var(--font-family-sans);
            font-weight: 600;
            font-size: 11.5px;
            padding: 6px 10px;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s ease;
            text-transform: uppercase;
        }

        .tab-btn:hover {
            color: var(--text-main);
            background: var(--btn-hover);
        }

        .tab-btn.active {
            color: var(--text-main);
            background: var(--btn-hover);
            border: 1px solid var(--border-glow);
        }

        .tab-content {
            flex: 1;
            display: none;
            overflow-y: auto;
            position: relative;
        }

        .tab-content.active {
            display: flex;
            flex-direction: column;
        }

        /* Dynamic CE/PE segment selector */
        .toggle-group {
            display: flex;
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            border-radius: 6px;
            padding: 2px;
            gap: 2px;
            width: 100%;
        }
        .toggle-group .toggle-btn {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-mute);
            padding: 8px;
            font-size: 11.5px;
            font-weight: 700;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s ease;
            text-transform: uppercase;
        }
        .toggle-group .toggle-btn.active {
            background: var(--btn-hover);
            color: var(--text-main);
            border: 1px solid var(--border-glow);
        }
        
        .toggle-group .toggle-btn[data-val="CE"].active {
            background: rgba(63, 209, 138, 0.15) !important;
            color: var(--green-glow) !important;
            border: 1px solid var(--green-glow) !important;
        }
        
        .toggle-group .toggle-btn[data-val="PE"].active {
            background: rgba(235, 111, 146, 0.15) !important;
            color: var(--red-glow) !important;
            border: 1px solid var(--red-glow) !important;
        }

        /* Chart Control Toolbar Styling */
        .chart-control-group {
            display: flex;
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            padding: 2px;
            gap: 2px;
            align-items: center;
        }
        .chart-control-btn {
            background: transparent;
            border: none;
            color: var(--text-mute);
            padding: 3px 6px;
            font-size: 10.5px;
            font-weight: 700;
            cursor: pointer;
            border-radius: 3px;
            transition: all 0.15s ease;
            text-transform: uppercase;
        }
        .chart-control-btn:hover {
            color: var(--text-main);
        }
        .chart-control-btn.active {
            background: var(--btn-hover);
            color: var(--text-main);
            border: 1px solid var(--border-glow);
        }

        /* Custom ATM-Centered Scrollable Dropdown Selector */
        .custom-dropdown {
            position: relative;
            width: 100%;
        }
        .dropdown-trigger {
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            color: var(--text-main);
            border-radius: 4px;
            padding: 8px 12px;
            font-family: var(--font-family-mono);
            font-size: 13px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            min-height: 36px;
        }
        .dropdown-trigger::after {
            content: '▼';
            font-size: 10px;
            color: var(--text-mute);
        }
        .dropdown-menu {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--bg-card);
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            margin-top: 4px;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            max-height: 250px;
            flex-direction: column;
        }
        .dropdown-menu.show {
            display: flex;
        }
        .dropdown-search {
            padding: 6px;
            border-bottom: 1px solid var(--border-glow);
        }
        .dropdown-search input {
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            color: var(--text-main);
            border-radius: 3px;
            padding: 6px;
            font-size: 12px;
            width: 100%;
            outline: none;
        }
        .dropdown-options-list {
            overflow-y: auto;
            flex: 1;
            max-height: 200px;
        }
        .dropdown-option {
            padding: 8px 12px;
            cursor: pointer;
            font-family: var(--font-family-mono);
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.15s;
        }
        .dropdown-option:hover {
            background: var(--btn-hover);
        }
        .dropdown-option.selected {
            background: var(--btn-hover);
            font-weight: 700;
        }
        .dropdown-option.atm-strike {
            background: var(--atm-glow);
            color: var(--accent-amber);
            border-left: 3px solid var(--accent-amber);
        }
        .dropdown-option.atm-strike::after {
            content: 'ATM';
            font-size: 10px;
            background: rgba(246, 193, 119, 0.2);
            color: var(--accent-amber);
            padding: 1px 4px;
            border-radius: 3px;
            font-weight: 700;
        }

        /* Order Book DOM Styles */
        .dom-table {
            width: 100%;
            border-collapse: collapse;
            font-family: var(--font-family-mono);
            font-size: 11.5px;
        }
        .dom-table th {
            text-align: right;
            padding: 8px 10px;
            color: var(--text-mute);
            font-weight: 600;
            border-bottom: 1px solid var(--border-glow);
            text-transform: uppercase;
            font-size: 10.5px;
        }
        .dom-table td {
            padding: 5px 10px;
            text-align: right;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.02);
            color: var(--text-main);
        }
        .dom-table tr.dom-ltp-row td {
            border-top: 1px solid var(--border-glow);
            border-bottom: 1px solid var(--border-glow);
            font-weight: 700;
            font-size: 12.5px;
            padding: 8px 10px;
        }

        /* TradingView Toolbar */
        .tv-toolbar {
            display: flex;
            align-items: center;
            gap: 12px;
            font-family: var(--font-family-mono);
            font-size: 11.5px;
        }

        .tv-metric {
            display: flex;
            gap: 4px;
        }

        .tv-label {
            color: var(--text-mute);
        }

        .tv-value {
            font-weight: 600;
        }

        /* Scalper Panel Styles */
        .scalper-summary {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 6px;
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            padding: 8px;
            text-align: center;
            font-size: 11.5px;
        }

        .scalper-metric {
            display: flex;
            flex-direction: column;
        }

        .scalper-label {
            color: var(--text-mute);
            margin-bottom: 2px;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.5px;
        }

        .scalper-value {
            font-family: var(--font-family-mono);
            font-weight: 700;
            font-size: 14px;
        }

        .scalper-bid-ask {
            display: flex;
            justify-content: space-between;
            font-family: var(--font-family-mono);
            font-size: 11.5px;
            padding: 6px 8px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 4px;
            margin-top: 2px;
        }

        .scalper-bid {
            color: var(--accent-red);
            font-weight: 700;
        }

        .scalper-ask {
            color: var(--accent);
            font-weight: 700;
        }

        .scalper-qty-selector {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            background: var(--bg-deep);
            padding: 6px;
            margin-top: 4px;
        }

        .scalper-qty-btn {
            background: var(--btn-hover);
            border: none;
            color: var(--text-main);
            width: 28px;
            height: 28px;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .scalper-qty-display {
            font-family: var(--font-family-mono);
            font-weight: 700;
            font-size: 13.5px;
        }

        .scalper-qty-subtext {
            display: block;
            font-size: 10px;
            color: var(--text-mute);
            text-align: center;
        }

        .scalper-execution-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 8px;
        }

        .scalper-exec-btn {
            border: none;
            border-radius: 6px;
            padding: 12px;
            color: #16141f;
            font-family: var(--font-family-sans);
            font-weight: 700;
            font-size: 13.5px;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: opacity 0.2s;
        }

        .scalper-exec-btn:hover {
            opacity: 0.9;
        }

        .scalper-exec-btn.sell {
            background: var(--accent-red);
        }

        .scalper-exec-btn.buy {
            background: var(--accent);
        }

        .scalper-exec-btn .btn-sublabel {
            font-size: 10.5px;
            opacity: 0.8;
            margin-top: 2px;
            font-family: var(--font-family-mono);
        }

        .bracket-section {
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            background: var(--bg-deep);
            padding: 8px;
            margin-top: 8px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .bracket-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .bracket-input-group {
            display: flex;
            align-items: center;
            border: 1px solid var(--border-glow);
            background: var(--bg-card);
            border-radius: 4px;
            padding: 2px 6px;
            width: 130px;
        }

        .bracket-input-group input {
            background: transparent;
            border: none;
            color: var(--text-main);
            width: 100%;
            font-family: var(--font-family-mono);
            font-size: 12px;
            text-align: right;
            outline: none;
            padding: 4px 0;
        }

        .bracket-input-group select {
            background: transparent;
            border: none;
            color: var(--text-mute);
            font-size: 11px;
            outline: none;
            cursor: pointer;
            margin-left: 6px;
            padding: 0;
        }

        /* Form Controls */
        .form-row {
            display: flex;
            flex-direction: column;
            gap: 4px;
            margin-bottom: 8px;
        }

        .form-row label {
            font-size: 11px;
            color: var(--text-mute);
            font-weight: 600;
            text-transform: uppercase;
        }

        select, input {
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            color: var(--text-main);
            border-radius: 4px;
            padding: 8px;
            font-family: var(--font-family-sans);
            font-size: 12.5px;
            outline: none;
            width: 100%;
        }

        input[type="number"] {
            font-family: var(--font-family-mono);
        }

        input[type="checkbox"] {
            width: 14px !important;
            height: 14px !important;
            min-width: 14px;
            cursor: pointer;
            margin: 0;
            padding: 0;
            background: transparent;
            border: none;
        }

        .action-btn {
            background: var(--accent);
            border: none;
            color: #16141f;
            font-weight: 700;
            padding: 10px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }

        .action-btn:hover {
            opacity: 0.9;
        }

        /* HUD top connection control */
        .hud-mode-selector {
            display: flex;
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            border-radius: 6px;
            padding: 2px;
            gap: 2px;
            width: 100%;
        }

        .hud-mode-selector .mode-btn {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-mute);
            padding: 8px;
            font-size: 11.5px;
            font-weight: 700;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s ease;
        }

        .hud-mode-selector .mode-btn.active {
            background: var(--btn-hover);
            color: var(--text-main);
            border: 1px solid var(--border-glow);
        }

        .ctrl-btn {
            background: var(--btn-hover);
            border: 1px solid var(--border-glow);
            color: var(--text-main);
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
        }

        .ctrl-btn.icon-btn {
            border-radius: 50%;
            padding: 0;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
        }

        .ctrl-btn.active-hotkey {
            border-color: var(--accent);
            box-shadow: 0 0 6px var(--accent);
        }

        /* Tables & Lists */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12.5px;
            text-align: left;
        }

        th {
            color: var(--text-mute);
            font-weight: 600;
            padding: 8px 6px;
            border-bottom: 1px solid var(--border-glow);
            text-transform: uppercase;
            font-size: 10px;
        }

        td {
            padding: 8px 6px;
            border-bottom: 1px solid var(--border-glow);
        }

        /* Status Colors */
        .text-green { color: var(--green-glow) !important; }
        .text-red { color: var(--red-glow) !important; }

        .console-log {
            font-family: var(--font-family-mono);
            font-size: 11px;
            padding: 3px 6px;
            margin: 0;
            border-bottom: 1px solid rgba(255,255,255,0.01);
        }
        
        .picker-tabs {
            display: flex;
            gap: 4px;
            border-bottom: 1px solid var(--border-glow);
            padding-bottom: 4px;
            margin-bottom: 8px;
        }
        
        .picker-tab-btn {
            background: none;
            border: none;
            color: var(--text-mute);
            font-size: 11.5px;
            font-weight: 700;
            cursor: pointer;
            padding: 4px 6px;
            border-radius: 3px;
        }
        
        .picker-tab-btn.active {
            background: var(--btn-hover);
            color: var(--text-main);
        }
        
        .picker-content {
            display: none;
            flex-direction: column;
            gap: 4px;
        }
        
        .picker-content.active {
            display: flex;
        }

        /* Minimal Stepper Widget */
        .stepper-container {
            display: flex;
            align-items: center;
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.02);
            padding: 4px;
            justify-content: space-between;
            height: 32px;
        }
        .stepper-btn {
            background: transparent;
            border: none;
            color: var(--text-mute);
            cursor: pointer;
            font-size: 14px;
            padding: 0 8px;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .stepper-btn:hover {
            color: var(--text-main);
        }
        .stepper-value-group {
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
        }



        /* Linked Pair Input Layout */
        .linked-pair-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 4px;
        }
        .linked-pair-input {
            flex: 1;
            background: var(--bg-deep);
            border: 1px solid var(--border-glow);
            border-radius: 4px;
            color: var(--text-main);
            padding: 6px;
            font-family: var(--font-family-mono);
            font-size: 12px;
            text-align: right;
        }
        .linked-indicator {
            color: var(--text-mute);
            font-size: 12px;
        }

        /* Product Toggle & Transaction Action */
        .product-toggle-btn {
            flex: 1;
            padding: 6px;
            font-size: 11px;
            background: transparent;
            border: none;
            color: var(--text-mute);
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        .product-toggle-btn.active {
            background: rgba(109, 93, 252, 0.15);
            border: 1px solid rgba(109, 93, 252, 0.5);
            color: #fff;
        }
        .side-toggle-btn {
            flex: 1;
            border: none;
            border-radius: 3px;
            font-size: 11px;
            background: transparent;
            color: var(--text-mute);
            cursor: pointer;
            font-weight: 700;
            transition: all 0.2s ease;
        }
        .side-toggle-btn.active-buy {
            background: var(--green-glow) !important;
            color: #16141f !important;
        }
        .side-toggle-btn.active-sell {
            border: 1px solid var(--border-glow);
            color: var(--text-main) !important;
        }
    </style>
</head>
<body class="dark-theme">

    <!-- Cockpit HUD Header -->
    <header class="hud-header">
        <div class="header-title">
            <span class="brand">VALKYRIE</span>
            <span>TACTICAL OPTIONS TERMINAL</span>
        </div>
        
        <div class="hud-info-grid">
            <div class="hud-info-item">
                <span class="hud-info-label" id="hud-spot-label">NIFTY SPOT:</span>
                <span class="hud-info-val" id="hud-spot-price">--</span>
            </div>
            <div class="hud-info-item">
                <span class="hud-info-label">CONTRACT:</span>
                <span class="hud-info-val text-green" id="hud-active-contract">--</span>
            </div>
            <div class="hud-info-item">
                <span class="hud-info-label">STATUS:</span>
                <span class="hud-info-val pulse" id="hud-stream-state">OFFLINE</span>
            </div>
        </div>

        <div class="header-actions">
            <button class="ctrl-btn icon-btn" id="theme-toggle-btn" onclick="toggleTheme()" title="Toggle Theme">🌙</button>
        </div>
    </header>

    <div class="terminal-container">
        
        <!-- Left Pane (76%) -->
        <div class="left-pane">
            
            <!-- DOM + Chart workspace -->
            <div class="workspace-area">
                
                <!-- DOM (Depth of Market) Card (25%) -->
                <div class="card dom-card">
                    <div class="tabs-header">
                        <span style="font-weight:700; font-size:11px; text-transform:uppercase;">Depth of Market</span>
                        <span id="dom-spread" style="font-family:var(--font-family-mono); font-size:10px; color:var(--text-mute);">Spread: --</span>
                    </div>
                    <div style="flex:1; overflow-y:auto; margin-top:8px;">
                        <table class="dom-table">
                            <thead>
                                <tr>
                                    <th>Size</th>
                                    <th>Side</th>
                                    <th>Price</th>
                                </tr>
                            </thead>
                            <tbody id="dom-ladder-body">
                                <tr>
                                    <td colspan="3" style="text-align:center; color: var(--text-mute); padding: 24px;">No streaming data available. Connect stream.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Candlestick Chart Card (75%) -->
                <div class="card chart-card">
                    <div class="tabs-header" style="justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                            <span style="font-weight:700; font-size:11px; text-transform:uppercase; color: var(--text-main);">Option Candles</span>
                            <!-- Timeframe Selectors -->
                            <div class="chart-control-group">
                                <button class="chart-control-btn timeframe-btn" onclick="changeChartInterval('10s')">10s</button>
                                <button class="chart-control-btn timeframe-btn" onclick="changeChartInterval('30s')">30s</button>
                                <button class="chart-control-btn timeframe-btn active" onclick="changeChartInterval('1m')">1m</button>
                                <button class="chart-control-btn timeframe-btn" onclick="changeChartInterval('5m')">5m</button>
                                <button class="chart-control-btn timeframe-btn" onclick="changeChartInterval('15m')">15m</button>
                            </div>
                            <!-- Candle Type Selectors -->
                            <div class="chart-control-group">
                                <button class="chart-control-btn chart-type-btn active" onclick="changeChartType('ha')">HA</button>
                                <button class="chart-control-btn chart-type-btn" onclick="changeChartType('normal')">Normal</button>
                            </div>

                            <!-- Indicators Selector -->
                            <div class="chart-control-group" id="indicators-menu-container" style="position: relative;">
                                <button class="chart-control-btn" id="indicators-menu-btn" onclick="toggleIndicatorsMenu()" style="display: flex; align-items: center; gap: 4px;">
                                    Indicators <span style="font-size: 8px;">▼</span>
                                </button>
                                <div class="dropdown-menu" id="indicators-dropdown" style="display: none; position: absolute; top: 100%; right: 0; min-width: 160px; padding: 10px; z-index: 1100; background: var(--bg-card); border: 1px solid var(--border-glow); border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); flex-direction: column; gap: 8px; margin-top: 4px; text-align: left;">
                                    <span style="font-size: 10px; font-weight: 700; color: var(--text-mute); text-transform: uppercase; margin-bottom: 2px;">Overlays</span>
                                    <label style="display: flex; align-items: center; gap: 8px; margin: 0; cursor: pointer; color: var(--text-main); font-size: 11.5px; font-weight: 600;">
                                        <input type="checkbox" id="ind-ema5" onchange="onIndicatorToggle('ema5')" style="width: 14px; height: 14px; cursor: pointer; margin: 0;"> EMA 5
                                    </label>
                                    <label style="display: flex; align-items: center; gap: 8px; margin: 0; cursor: pointer; color: var(--text-main); font-size: 11.5px; font-weight: 600;">
                                        <input type="checkbox" id="ind-ema20" onchange="onIndicatorToggle('ema20')" style="width: 14px; height: 14px; cursor: pointer; margin: 0;"> EMA 20
                                    </label>
                                    <label style="display: flex; align-items: center; gap: 8px; margin: 0; cursor: pointer; color: var(--text-main); font-size: 11.5px; font-weight: 600;">
                                        <input type="checkbox" id="ind-sma10" onchange="onIndicatorToggle('sma10')" style="width: 14px; height: 14px; cursor: pointer; margin: 0;"> SMA 10
                                    </label>
                                    <label style="display: flex; align-items: center; gap: 8px; margin: 0; cursor: pointer; color: var(--text-main); font-size: 11.5px; font-weight: 600;">
                                        <input type="checkbox" id="ind-bb" onchange="onIndicatorToggle('bb')" style="width: 14px; height: 14px; cursor: pointer; margin: 0;"> Bollinger Bands
                                    </label>
                                </div>
                            </div>
                        </div>
                        <div class="tv-toolbar">
                            <div class="tv-metric"><span class="tv-label">O</span><span id="tv-open" class="tv-value">--</span></div>
                            <div class="tv-metric"><span class="tv-label">H</span><span id="tv-high" class="tv-value">--</span></div>
                            <div class="tv-metric"><span class="tv-label">L</span><span id="tv-low" class="tv-value">--</span></div>
                            <div class="tv-metric"><span class="tv-label">C</span><span id="tv-close" class="tv-value">--</span></div>
                            <div class="tv-metric" style="margin-left:8px;"><span class="tv-label">T</span><span id="tv-time" class="tv-value">--</span></div>
                        </div>
                    </div>
                    <div id="chart-ha" style="flex:1; width:100%; margin-top:8px; min-height:0;"></div>
                </div>

            </div>

            <!-- Lower Tab Card (Positions + History + Console) - Resizable -->
            <div class="card lower-tabs-card" id="bottom-panel">
                <div class="tabs-header">
                    <div class="tabs-list">
                        <button class="tab-btn active" onclick="switchLowerTab('positions')">Active Positions</button>
                        <button class="tab-btn" onclick="switchLowerTab('gtt-registry')">GTT Registries</button>
                        <button class="tab-btn" onclick="switchLowerTab('history')">Trade Fills</button>
                        <button class="tab-btn" onclick="switchLowerTab('console')">System Events</button>
                    </div>
                    <div class="panel-actions">
                        <button class="ctrl-btn" id="btn-resize-panel" onclick="togglePanelHeight()">↕ Size</button>
                    </div>
                </div>

                <div class="panel-content-area">
                    <!-- Position Tab -->
                    <div id="tab-positions" class="tab-content active">
                        <table>
                            <thead>
                                <tr>
                                    <th>Trading Symbol</th>
                                    <th>Entry Price</th>
                                    <th>Quantity (Lots)</th>
                                    <th>Target Price</th>
                                    <th>Stop Loss</th>
                                    <th>Net P&L</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="positions-table-body">
                                <tr>
                                    <td colspan="7" style="text-align:center; color:var(--text-mute);">No active position.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- GTT Registry Tab -->
                    <div id="tab-gtt-registry" class="tab-content">
                        <table>
                            <thead>
                                <tr>
                                    <th>Trigger ID</th>
                                    <th>Side</th>
                                    <th>Trigger Price</th>
                                    <th>Lots</th>
                                    <th>Target / SL</th>
                                    <th>Status</th>
                                    <th>Timestamp</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="gtt-table-body">
                                <tr>
                                    <td colspan="8" style="text-align:center; color:var(--text-mute);">No active GTT triggers.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- Trade History -->
                    <div id="tab-history" class="tab-content">
                        <table>
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Type</th>
                                    <th>Fill Price</th>
                                    <th>Stop Loss Price</th>
                                    <th>Net Realized PnL</th>
                                    <th>Trigger Source</th>
                                </tr>
                            </thead>
                            <tbody id="history-table-body">
                                <tr>
                                    <td colspan="6" style="text-align:center; color:var(--text-mute);">No fills recorded.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- System Console Logs -->
                    <div id="tab-console" class="tab-content">
                        <div id="console-logs-div" style="flex:1; overflow-y:auto; display:flex; flex-direction:column-reverse;"></div>
                    </div>
                </div>
            </div>

        </div>

        <!-- Right Pane (24%) -->
        <div class="right-pane">
            
            <!-- Connection Panel HUD (Top) -->
            <div class="card connection-hud" style="gap:6px;">
                <div class="hud-mode-selector">
                    <button class="mode-btn active" id="mode-paper-btn" onclick="setDeskMode('PAPER')">Simulation (Paper)</button>
                    <button class="mode-btn" id="mode-live-btn" onclick="setDeskMode('MANUAL')">Production (Live)</button>
                </div>
                
                <div class="form-row" id="live-trading-toggle-row" style="display:none; flex-direction:row; justify-content:space-between; align-items:center; margin: 4px 0;">
                    <label style="font-size: 10.5px;">Enable Real Money API Execution</label>
                    <input type="checkbox" id="ctrl-real-exec" style="width:14px; height:14px; cursor:pointer;">
                </div>
                
                <button class="action-btn" id="execute-btn" onclick="toggleExecutionSession()" style="margin-top:2px; font-size:11px;">Connect Option Stream</button>
                <button class="action-btn" id="panic-btn" onclick="executePanicExit()" style="margin-top:4px; font-size:11px; background:var(--accent-red); color:#16141f; font-weight:700;">PANIC EXIT (Shift+Esc)</button>
            </div>

            <!-- Target Instrument Picker (Middle) -->
            <div class="card instrument-picker-card">
                <div class="tabs-header" style="margin-bottom: 8px; border-bottom: none; padding-bottom: 0;">
                    <span style="font-weight:700; font-size:12px; text-transform:uppercase; color: var(--accent-blue);">Target Settings</span>
                </div>
                
                <!-- Exchange selector -->
                <div class="form-row">
                    <label>Exchange</label>
                    <div class="toggle-group" id="exchange-toggle">
                        <button class="toggle-btn active" data-val="NSE" onclick="setExchange('NSE')">NSE</button>
                        <button class="toggle-btn" data-val="BSE" onclick="setExchange('BSE')">BSE</button>
                    </div>
                </div>

                <!-- Index selector -->
                <div class="form-row">
                    <label>Index</label>
                    <div class="toggle-group" id="index-toggle">
                        <!-- Populated dynamically via setExchange -->
                    </div>
                </div>

                <!-- Expiry Date selector -->
                <div class="form-row">
                    <label>Expiry Date</label>
                    <select id="ctrl-expiry" onchange="onExpiryChange()"></select>
                </div>

                <!-- Strike Selector -->
                <div class="form-row">
                    <label>Strike Price</label>
                    <div class="custom-dropdown" id="strike-dropdown-container">
                        <div class="dropdown-trigger" id="strike-trigger" onclick="toggleStrikeDropdown()">Select Strike (ATM: --)</div>
                        <div class="dropdown-menu" id="strike-menu">
                            <div class="dropdown-search">
                                <input type="text" id="strike-search-input" placeholder="Search strike..." onkeyup="filterStrikes()">
                            </div>
                            <div class="dropdown-options-list" id="strike-options-list">
                                <!-- Populated dynamically -->
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Option Type -->
                <div class="form-row">
                    <label>Option Type</label>
                    <div class="toggle-group" id="opt-type-toggle">
                        <button class="toggle-btn active" data-val="CE" onclick="setOptionType('CE')">CALL (CE)</button>
                        <button class="toggle-btn" data-val="PE" onclick="setOptionType('PE')">PUT (PE)</button>
                    </div>
                </div>
            </div>

            <!-- Execution Panel Workspace (Bottom) -->
            <div class="card" style="flex:1; gap:6px;">
                <div class="tabs-list" style="border-bottom:1px solid var(--border-glow); padding-bottom:4px; margin-bottom:4px;">
                    <button class="tab-btn" id="pad-std-btn" onclick="switchOrderPad('standard')">Standard &amp; GTT Pad</button>
                    <button class="tab-btn active" id="pad-scalper-btn" onclick="switchOrderPad('scalper')">Scalper Mode</button>
                </div>

                <!-- Pad 1: Scalper Mode -->
                <div id="pad-scalper" style="display:flex; flex-direction:column; gap:6px;">
                    <div class="scalper-summary">
                        <div class="scalper-metric">
                            <span class="scalper-label">Lots</span>
                            <span id="sc-lots" class="scalper-value">0</span>
                        </div>
                        <div class="scalper-metric">
                            <span class="scalper-label">LTP</span>
                            <span id="sc-ltp" class="scalper-value">0.00</span>
                        </div>
                        <div class="scalper-metric">
                            <span class="scalper-label">Avg. Price</span>
                            <span id="sc-avg" class="scalper-value">0.00</span>
                        </div>
                        <div class="scalper-metric">
                            <span class="scalper-label">P&amp;L</span>
                            <span id="sc-pnl" class="scalper-value">0.00</span>
                        </div>
                    </div>

                    <div class="scalper-bid-ask">
                        <div>Bid: <span id="sc-bid" class="scalper-bid">0.00</span></div>
                        <div><span id="sc-ask" class="scalper-ask">0.00</span> :Ask</div>
                    </div>

                    <div class="scalper-qty-selector">
                        <button class="scalper-qty-btn" onclick="adjustScalperLots(-1)">−</button>
                        <div style="flex:1; text-align:center;">
                            <span id="sc-selected-lots" class="scalper-qty-display">1 lots</span>
                            <span id="sc-selected-qty" class="scalper-qty-subtext">(65 qty.)</span>
                        </div>
                        <button class="scalper-qty-btn" onclick="adjustScalperLots(1)">+</button>
                    </div>

                    <div class="scalper-execution-buttons">
                        <button class="scalper-exec-btn sell" id="scalp-sell-btn" onclick="placeOrder('SELL', true)">
                            <span>Sell Call</span>
                            <span class="btn-sublabel">shift ↓</span>
                        </button>
                        <button class="scalper-exec-btn buy" id="scalp-buy-btn" onclick="placeOrder('BUY', true)">
                            <span>Buy Call</span>
                            <span class="btn-sublabel">shift ↑</span>
                        </button>
                    </div>

                    <!-- Brackets -->
                    <div class="bracket-section">
                        <div style="font-weight:700; font-size:10px; color:var(--text-mute); text-transform:uppercase;">Bracket Protection</div>
                        <div class="bracket-row">
                            <label style="font-size:10px;">Stop Loss</label>
                            <div style="display:flex; flex-direction:column; gap:4px; width:100%;">
                                <div class="bracket-input-group">
                                    <input type="number" id="sc-bracket-sl" value="0.0" step="0.5">
                                    <select id="sc-bracket-sl-type" onchange="handleAtrChange('sc-bracket-sl')">
                                        <option value="points">pts</option>
                                        <option value="percent">%</option>
                                        <option value="atr">auto (atr)</option>
                                    </select>
                                </div>
                                <div class="preset-buttons" style="display:flex; gap:3px; flex-wrap:wrap;">
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-sl', 2, 'points')" style="padding:2px 6px; font-size:8.5px; background:#3a1e1e; border:1px solid #6e2d2d; border-radius:3px; color:#f87171; cursor:pointer; font-weight:600;">2</button>
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-sl', 3, 'points')" style="padding:2px 6px; font-size:8.5px; background:#3a1e1e; border:1px solid #6e2d2d; border-radius:3px; color:#f87171; cursor:pointer; font-weight:600;">3</button>
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-sl', 5, 'points')" style="padding:2px 6px; font-size:8.5px; background:#3a1e1e; border:1px solid #6e2d2d; border-radius:3px; color:#f87171; cursor:pointer; font-weight:600;">5</button>
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-sl', 8, 'points')" style="padding:2px 6px; font-size:8.5px; background:#3a1e1e; border:1px solid #6e2d2d; border-radius:3px; color:#f87171; cursor:pointer; font-weight:600;">8</button>
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-sl', 10, 'points')" style="padding:2px 6px; font-size:8.5px; background:#3a1e1e; border:1px solid #6e2d2d; border-radius:3px; color:#f87171; cursor:pointer; font-weight:600;">10</button>
                                </div>
                            </div>
                        </div>
                        <div class="bracket-row">
                            <label style="font-size:10px;">Take Profit</label>
                            <div style="display:flex; flex-direction:column; gap:4px; width:100%;">
                                <div class="bracket-input-group">
                                    <input type="number" id="sc-bracket-target" value="0.0" step="0.5">
                                    <select id="sc-bracket-target-type" onchange="handleAtrChange('sc-bracket-target')">
                                        <option value="points">pts</option>
                                        <option value="percent">%</option>
                                        <option value="atr">auto (atr)</option>
                                    </select>
                                </div>
                                <div class="preset-buttons" style="display:flex; gap:3px; flex-wrap:wrap;">
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-target', 2, 'points')" style="padding:2px 6px; font-size:8.5px; background:#1e3a28; border:1px solid #2d6e4e; border-radius:3px; color:#4ade80; cursor:pointer; font-weight:600;">+2</button>
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-target', 5, 'points')" style="padding:2px 6px; font-size:8.5px; background:#1e3a28; border:1px solid #2d6e4e; border-radius:3px; color:#4ade80; cursor:pointer; font-weight:600;">+5</button>
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-target', 10, 'points')" style="padding:2px 6px; font-size:8.5px; background:#1e3a28; border:1px solid #2d6e4e; border-radius:3px; color:#4ade80; cursor:pointer; font-weight:600;">+10</button>
                                    <button class="preset-btn" onclick="setPreset('sc-bracket-target', 20, 'points')" style="padding:2px 6px; font-size:8.5px; background:#1e3a28; border:1px solid #2d6e4e; border-radius:3px; color:#4ade80; cursor:pointer; font-weight:600;">+20</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Pad 2: Standard & GTT Pad -->
                <div id="pad-standard" style="display:none; flex-direction:column; gap:12px; overflow-y:auto; max-height:480px; padding-right:2px;">
                    <!-- Order Mode Toggle (Standard vs GTT) -->
                    <div style="display:flex; border: 1px solid var(--border-glow); border-radius: 6px; padding: 2px;">
                        <button id="mode-std" class="product-toggle-btn active" onclick="setOrderMode('STANDARD')">Standard Mode</button>
                        <button id="mode-gtt" class="product-toggle-btn" onclick="setOrderMode('GTT')">GTT Trigger Mode</button>
                    </div>



                    <!-- 3. Split Row: Quantity & Transaction Side -->
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; align-items: end;">
                        <!-- Left: Quantity Stepper -->
                        <div>
                            <label style="font-size:10px; color:var(--text-mute); display:block; margin-bottom:4px; text-transform:uppercase; font-weight:600;">Quantity</label>
                            <div class="stepper-container">
                                <button class="stepper-btn" onclick="adjustQty(-1)">-</button>
                                <div class="stepper-value-group">
                                    <span id="gtt-display-qty" style="font-family:var(--font-family-mono); font-size:13px; color:#fff; font-weight:700;">65</span>
                                    <span style="font-size:7px; color:var(--text-mute);">▼</span>
                                </div>
                                <button class="stepper-btn" onclick="adjustQty(1)">+</button>
                            </div>
                        </div>

                        <!-- Right: Transaction Side Toggle -->
                        <div>
                            <label style="font-size:10px; color:var(--text-mute); display:block; margin-bottom:4px; text-transform:uppercase; font-weight:600;">Action</label>
                            <div style="display:flex; border: 1px solid var(--border-glow); border-radius:6px; padding:2px; height: 32px; box-sizing: border-box;">
                                <button id="side-buy-btn" class="side-toggle-btn active-buy" onclick="setTransactionSide('BUY')">Buy</button>
                                <button id="side-sell-btn" class="side-toggle-btn" onclick="setTransactionSide('SELL')">Sell</button>
                            </div>
                        </div>
                    </div>

                    <!-- 4. Condition & Trigger Stacked Body -->
                    <div style="display:flex; flex-direction:column; gap:12px; border-top:1px solid var(--border-glow); padding-top:12px;">
                        
                        <!-- Entry Trigger Row -->
                        <div id="gtt-entry-row" style="display:none;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <select id="gtt-trigger-dir" onchange="syncLinkedPair('entry', 'pct')" style="background:transparent; border:none; color:var(--text-mute); font-size:11px; padding:0; cursor:pointer; width:auto; font-weight:600; text-transform:uppercase; outline:none;">
                                    <option value="below">Place order If price is below</option>
                                    <option value="above">Place order If price is above</option>
                                </select>
                            </div>
                            <div class="linked-pair-row">
                                <input type="number" id="gtt-trigger-price" class="linked-pair-input" value="186.85" step="0.05" oninput="syncLinkedPair('entry', 'abs')">
                                <span class="linked-indicator">↔</span>
                                <input type="number" id="gtt-trigger-pct" class="linked-pair-input" value="0.25" step="0.01" placeholder="%" oninput="syncLinkedPair('entry', 'pct')">
                            </div>
                        </div>

                        <!-- Stop-Loss Leg -->
                        <div>
                            <label style="display:flex; align-items:center; gap:6px; font-size:11px; color:#fff; cursor:pointer; font-weight:600; text-transform:uppercase;">
                                <input type="checkbox" id="chk-add-sl" checked onchange="toggleLeg('sl')">
                                <span>Add stop loss</span>
                            </label>
                            <div id="sl-leg-inputs" class="linked-pair-row" style="display:flex;">
                                <input type="number" id="gtt-sl" class="linked-pair-input" value="176.50" step="0.05" oninput="syncLinkedPair('sl', 'abs')">
                                <span class="linked-indicator">↔</span>
                                <input type="number" id="gtt-sl-pct" class="linked-pair-input" value="5.55" step="0.01" placeholder="%" oninput="syncLinkedPair('sl', 'pct')">
                            </div>

                        </div>

                        <!-- Target Leg -->
                        <div>
                            <label style="display:flex; align-items:center; gap:6px; font-size:11px; color:#fff; cursor:pointer; font-weight:600; text-transform:uppercase;">
                                <input type="checkbox" id="chk-add-target" checked onchange="toggleLeg('target')">
                                <span>Add target</span>
                            </label>
                            <div id="target-leg-inputs" class="linked-pair-row" style="display:flex;">
                                <input type="number" id="gtt-target" class="linked-pair-input" value="211.55" step="0.05" oninput="syncLinkedPair('target', 'abs')">
                                <span class="linked-indicator">↔</span>
                                <input type="number" id="gtt-target-pct" class="linked-pair-input" value="13.21" step="0.01" placeholder="%" oninput="syncLinkedPair('target', 'pct')">
                            </div>
                        </div>
                    </div>

                    <!-- 5. Submit Action Button -->
                    <button id="main-exec-btn" class="action-btn" onclick="submitMainOrder()" style="width:100%; margin-top:8px; padding:10px; font-size:12px; background:var(--accent-purple); color:#fff; border-radius:6px; font-weight:700; cursor:pointer;">Execute Standard Order</button>
                </div>

            </div>
        </div>

    </div>

    <script>
        let isRunning = false;
        let deskMode = 'PAPER'; 
        let hotkeysActive = false;
        let chart = null;
        let scalperLots = 1;
        let lotMultiplier = 65; 
        let spotPrice = 0.0; 

        // State variables for unified instrument selection
        let currentExchange = 'NSE';
        let currentIndex = 'NIFTY';
        let currentExpiry = '';
        let currentStrike = 'ATM';
        let currentOptionType = 'CE';
        let atmStrike = null;
        let strikesList = [];
        let isMetadataLoading = false;

        const indicesByExchange = {
            "NSE": [
                { name: "NIFTY 50", val: "NIFTY" },
                { name: "NIFTY BANK", val: "BANKNIFTY" },
                { name: "FINNIFTY", val: "FINNIFTY" },
                { name: "MIDCP", val: "MIDCPNIFTY" }
            ],
            "BSE": [
                { name: "SENSEX", val: "SENSEX" },
                { name: "BANKEX", val: "BANKEX" }
            ]
        };

        // Tab Switching
        function switchLowerTab(tabId) {
            document.querySelectorAll('.lower-tabs-card .tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.lower-tabs-card .tab-content').forEach(content => content.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');
        }

        function switchPickerTarget(tgt) {
            document.getElementById('tab-tgt-std').classList.remove('active');
            document.getElementById('tab-tgt-sc').classList.remove('active');
            document.getElementById('picker-std-content').classList.remove('active');
            document.getElementById('picker-sc-content').classList.remove('active');
            
            if (tgt === 'std') {
                document.getElementById('tab-tgt-std').classList.add('active');
                document.getElementById('picker-std-content').classList.add('active');
            } else {
                document.getElementById('tab-tgt-sc').classList.add('active');
                document.getElementById('picker-sc-content').classList.add('active');
            }
        }

        function switchOrderPad(pad) {
            document.getElementById('pad-std-btn').classList.remove('active');
            document.getElementById('pad-scalper-btn').classList.remove('active');
            
            document.getElementById('pad-standard').style.display = 'none';
            document.getElementById('pad-scalper').style.display = 'none';

            if (pad === 'scalper') {
                document.getElementById('pad-scalper-btn').classList.add('active');
                document.getElementById('pad-scalper').style.display = 'flex';
            } else {
                document.getElementById('pad-std-btn').classList.add('active');
                document.getElementById('pad-standard').style.display = 'flex';
            }
            activePad = pad;
            if (typeof saveLocalSettings === 'function') saveLocalSettings();
        }

        let selectedQty = 65;
        let selectedSide = 'BUY';
        let selectedOrderMode = 'STANDARD';
        let hasInitializedDefaults = false;

        function setOrderMode(mode) {
            selectedOrderMode = mode;
            document.getElementById("mode-std").classList.toggle("active", mode === 'STANDARD');
            document.getElementById("mode-gtt").classList.toggle("active", mode === 'GTT');
            
            document.getElementById("gtt-entry-row").style.display = (mode === 'GTT') ? 'block' : 'none';
            
            const submitBtn = document.getElementById("main-exec-btn");
            if (mode === 'GTT') {
                submitBtn.innerText = "Deploy GTT Trigger";
                submitBtn.style.background = "var(--accent-amber)";
                submitBtn.style.color = "#16141f";
            } else {
                submitBtn.innerText = "Execute Standard Order";
                submitBtn.style.background = "var(--accent-purple)";
                submitBtn.style.color = "#fff";
            }
            
            // Recalculate SL/Target relative to the mode's correct ref price
            recalcBracketValues();
            if (typeof saveLocalSettings === 'function') saveLocalSettings();
        }

        function adjustQty(val) {
            selectedQty = Math.max(1, selectedQty + val);
            document.getElementById("gtt-display-qty").innerText = selectedQty;
        }

        function setTransactionSide(side) {
            selectedSide = side;
            const buyBtn = document.getElementById("side-buy-btn");
            const sellBtn = document.getElementById("side-sell-btn");
            
            if (side === 'BUY') {
                buyBtn.classList.add("active-buy");
                sellBtn.classList.remove("active-sell");
            } else {
                buyBtn.classList.remove("active-buy");
                sellBtn.classList.add("active-sell");
            }
            
            recalcBracketValues();
        }

        function toggleLeg(leg) {
            const isChecked = document.getElementById(`chk-add-${leg}`).checked;
            const inputsRow = document.getElementById(`${leg}-leg-inputs`);
            if (inputsRow) {
                inputsRow.style.display = isChecked ? 'flex' : 'none';
            }
        }

        function getEntryRefPrice() {
            if (selectedOrderMode === 'GTT') {
                return parseFloat(document.getElementById("gtt-trigger-price").value) || spotPrice;
            } else {
                return spotPrice;
            }
        }

        function syncLinkedPair(field, source) {
            const ref = getEntryRefPrice();
            if (field === 'entry') {
                if (source === 'abs') {
                    const val = parseFloat(document.getElementById("gtt-trigger-price").value) || 0;
                    let pct = 0;
                    if (spotPrice > 0) {
                        pct = Math.abs(val - spotPrice) / spotPrice * 100;
                    }
                    document.getElementById("gtt-trigger-pct").value = pct.toFixed(2);
                } else {
                    const pctVal = parseFloat(document.getElementById("gtt-trigger-pct").value) || 0;
                    const dir = document.getElementById("gtt-trigger-dir").value;
                    let val = spotPrice;
                    if (dir === 'below') {
                        val = spotPrice * (1.0 - pctVal / 100.0);
                    } else {
                        val = spotPrice * (1.0 + pctVal / 100.0);
                    }
                    document.getElementById("gtt-trigger-price").value = val.toFixed(2);
                }
                // When trigger price changes, SL/Target reference point changes
                recalcBracketValues();
            } else if (field === 'sl') {
                if (source === 'abs') {
                    const val = parseFloat(document.getElementById("gtt-sl").value) || 0;
                    let pct = 0;
                    if (ref > 0) {
                        pct = Math.abs(val - ref) / ref * 100;
                    }
                    document.getElementById("gtt-sl-pct").value = pct.toFixed(2);
                } else {
                    const pctVal = parseFloat(document.getElementById("gtt-sl-pct").value) || 0;
                    let val = ref;
                    if (selectedSide === 'BUY') {
                        val = ref * (1.0 - pctVal / 100.0);
                    } else {
                        val = ref * (1.0 + pctVal / 100.0);
                    }
                    document.getElementById("gtt-sl").value = val.toFixed(2);
                }
            } else if (field === 'target') {
                if (source === 'abs') {
                    const val = parseFloat(document.getElementById("gtt-target").value) || 0;
                    let pct = 0;
                    if (ref > 0) {
                        pct = Math.abs(val - ref) / ref * 100;
                    }
                    document.getElementById("gtt-target-pct").value = pct.toFixed(2);
                } else {
                    const pctVal = parseFloat(document.getElementById("gtt-target-pct").value) || 0;
                    let val = ref;
                    if (selectedSide === 'BUY') {
                        val = ref * (1.0 + pctVal / 100.0);
                    } else {
                        val = ref * (1.0 - pctVal / 100.0);
                    }
                    document.getElementById("gtt-target").value = val.toFixed(2);
                }
            }
        }

        function recalcBracketValues() {
            syncLinkedPair('sl', 'pct');
            syncLinkedPair('target', 'pct');
        }

        function initDefaultOrderPadValues() {
            if (spotPrice <= 0) return;
            
            document.getElementById("gtt-trigger-price").value = spotPrice.toFixed(2);
            document.getElementById("gtt-trigger-pct").value = "0.00";
            
            // Stop loss
            document.getElementById("gtt-sl-pct").value = "5.55";
            let slVal = spotPrice * (1.0 - 0.0555);
            document.getElementById("gtt-sl").value = slVal.toFixed(2);
            
            // Target
            document.getElementById("gtt-target-pct").value = "13.21";
            let tgtVal = spotPrice * (1.0 + 0.1321);
            document.getElementById("gtt-target").value = tgtVal.toFixed(2);
            
            hasInitializedDefaults = true;
        }

        function submitMainOrder() {
            if (!isRunning) {
                alert("Option stream is not connected.");
                return;
            }

            if (selectedOrderMode === 'GTT') {
                const triggerPrice = parseFloat(document.getElementById("gtt-trigger-price").value) || 0;
                if (triggerPrice <= 0) {
                    alert("Please provide a valid trigger price.");
                    return;
                }
                const side = selectedSide;
                const qty = selectedQty;
                const dir = document.getElementById("gtt-trigger-dir").value;
                
                const addTarget = document.getElementById("chk-add-target").checked;
                const target = addTarget ? parseFloat(document.getElementById("gtt-target-pct").value) || 0.0 : 0.0;
                
                const addSl = document.getElementById("chk-add-sl").checked;
                const stopLoss = addSl ? parseFloat(document.getElementById("gtt-sl-pct").value) || 0.0 : 0.0;
                
                const payload = {
                    trigger_price: triggerPrice,
                    direction: dir,
                    side: side,
                    qty: qty,
                    order_type: 'MARKET',
                    target: target,
                    target_type: 'percent',
                    stop_loss: stopLoss,
                    stop_loss_type: 'percent',
                    trailing_gap: 0.0
                };

                fetch('/manual/gtt/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        logConsole(`[GTT] Registered trigger for ${side} at ₹${triggerPrice.toFixed(2)}`);
                        switchLowerTab('gtt-registry');
                    }
                });
            } else {
                const side = selectedSide;
                const qty = selectedQty;
                
                const addTarget = document.getElementById("chk-add-target").checked;
                const target = addTarget ? parseFloat(document.getElementById("gtt-target-pct").value) || 0.0 : 0.0;
                
                const addSl = document.getElementById("chk-add-sl").checked;
                const stopLoss = addSl ? parseFloat(document.getElementById("gtt-sl-pct").value) || 0.0 : 0.0;
                
                const endpoint = (side === 'BUY') ? '/manual/buy' : '/manual/sell';
                const payload = {
                    qty: qty,
                    target: target,
                    target_type: 'percent',
                    stop_loss: stopLoss,
                    stop_loss_type: 'percent',
                    trailing_gap: 0.0,
                    is_scalper: false
                };

                fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        logConsole("[ERROR] " + data.error);
                    } else {
                        logConsole(`[TRADE] Filled ${side} ${qty} Lots of ${data.status.trading_symbol} at Market.`);
                    }
                });
            }
        }

        function togglePanelHeight() {
            const panel = document.getElementById('bottom-panel');
            if (panel.classList.contains('minimized')) {
                panel.classList.remove('minimized');
                panel.classList.add('maximized');
            } else if (panel.classList.contains('maximized')) {
                panel.classList.remove('maximized');
            } else {
                panel.classList.add('minimized');
            }
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 310);
        }

        // Theme Toggle
        function toggleTheme() {
            const body = document.body;
            const btn = document.getElementById("theme-toggle-btn");
            if (body.classList.contains('dark-theme')) {
                body.classList.remove('dark-theme');
                body.classList.add('light-theme');
                if (btn) btn.innerText = "☀️";
            } else {
                body.classList.remove('light-theme');
                body.classList.add('dark-theme');
                if (btn) btn.innerText = "🌙";
            }
            if (chart) {
                const themeDark = body.classList.contains('dark-theme');
                chart.updateOptions({
                    theme: { mode: themeDark ? 'dark' : 'light' }
                });
            }
        }

        // Hotkeys Toggle
        function toggleHotkeys() {
            hotkeysActive = !hotkeysActive;
            const btn = document.getElementById("hotkeys-toggle-btn");
            if (hotkeysActive) {
                btn.classList.add("active-hotkey");
                btn.innerText = "⌨️ Hotkeys (On)";
                logConsole("[SYSTEM] Scalping Hotkeys Active: Shift+Up = BUY, Shift+Down = SELL.");
            } else {
                btn.classList.remove("active-hotkey");
                btn.innerText = "⌨️ Hotkeys";
                logConsole("[SYSTEM] Keyboard hotkeys deactivated.");
            }
        }

        window.addEventListener('keydown', function(e) {
            if (!isRunning) return;
            if (e.shiftKey && e.key === 'Escape') {
                e.preventDefault();
                executePanicExit();
                return;
            }
            if (!hotkeysActive) return;
            if (e.shiftKey && e.key === 'ArrowUp') {
                e.preventDefault();
                placeOrder('BUY', true);
            } else if (e.shiftKey && e.key === 'ArrowDown') {
                e.preventDefault();
                placeOrder('SELL', true);
            }
        });

        // Lot Adjustments
        function adjustScalperLots(delta) {
            scalperLots += delta;
            if (scalperLots < 1) scalperLots = 1;
            document.getElementById("sc-selected-lots").innerText = scalperLots + " lots";
            document.getElementById("sc-selected-qty").innerText = "(" + (scalperLots * lotMultiplier) + " qty.)";
            if (typeof saveLocalSettings === 'function') saveLocalSettings();
        }

        // Dropdown actions and handlers
        function setExchange(exchange) {
            currentExchange = exchange;
            document.querySelectorAll('#exchange-toggle .toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-val') === exchange);
            });
            
            // Re-populate Index toggle
            const indexToggle = document.getElementById("index-toggle");
            indexToggle.innerHTML = "";
            const list = indicesByExchange[exchange] || [];
            list.forEach((idx, i) => {
                const btn = document.createElement("button");
                btn.className = "toggle-btn" + (i === 0 ? " active" : "");
                btn.setAttribute("data-val", idx.val);
                btn.innerText = idx.name;
                btn.onclick = () => setIndex(idx.val);
                indexToggle.appendChild(btn);
            });
            
            if (list.length > 0) {
                setIndex(list[0].val);
            }
        }

        function setIndex(index) {
            currentIndex = index;
            document.querySelectorAll('#index-toggle .toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-val') === index);
            });
            loadExpiries();
        }

        function onExpiryChange() {
            currentExpiry = document.getElementById("ctrl-expiry").value;
            loadStrikes();
        }

        function setOptionType(val) {
            currentOptionType = val;
            document.querySelectorAll('#opt-type-toggle .toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-val') === val);
            });
            loadStrikes();
        }

        function loadExpiries() {
            isMetadataLoading = true;
            const startBtn = document.getElementById("execute-btn");
            if (startBtn && !isRunning) {
                startBtn.disabled = true;
                startBtn.innerText = "Loading Contracts...";
            }
            
            const expSelect = document.getElementById("ctrl-expiry");
            expSelect.innerHTML = "<option>Loading Expiries...</option>";
            
            return fetch(`/api/options/metadata?exchange=${currentExchange}&index=${currentIndex}`)
            .then(r => {
                if (!r.ok) {
                    throw new Error("HTTP error " + r.status);
                }
                return r.json();
            })
            .then(data => {
                isMetadataLoading = false;
                if (startBtn && !isRunning) {
                    startBtn.disabled = false;
                    startBtn.innerText = "Connect Option Stream";
                }
                
                expSelect.innerHTML = "";
                
                if (data.error) {
                    alert("Upstox API Error: " + data.error);
                    const opt = document.createElement("option");
                    opt.value = "";
                    opt.innerText = "Error Loading Expiries";
                    expSelect.appendChild(opt);
                    currentExpiry = "";
                    atmStrike = null;
                    strikesList = [];
                    currentStrike = "ATM";
                    updateStrikeDropdown([]);
                    return;
                }
                
                if (!data.expiries || data.expiries.length === 0) {
                    const opt = document.createElement("option");
                    opt.value = "";
                    opt.innerText = "No Expiries Found";
                    expSelect.appendChild(opt);
                    currentExpiry = "";
                    atmStrike = null;
                    strikesList = [];
                    currentStrike = "ATM";
                    updateStrikeDropdown([]);
                    return;
                }
                
                data.expiries.forEach(exp => {
                    const opt = document.createElement("option");
                    opt.value = exp;
                    opt.innerText = exp;
                    expSelect.appendChild(opt);
                });
                
                // Update HUD spot price and label immediately
                const spotLabelEl = document.getElementById("hud-spot-label");
                if (spotLabelEl) {
                    spotLabelEl.innerText = currentIndex + " SPOT:";
                }
                const spotPriceEl = document.getElementById("hud-spot-price");
                if (spotPriceEl) {
                    if (data.spot_price && data.spot_price > 0) {
                        spotPriceEl.innerText = "₹" + parseFloat(data.spot_price).toFixed(2);
                    } else {
                        spotPriceEl.innerText = "--";
                    }
                }
                
                currentExpiry = data.expiries[0];
                expSelect.value = currentExpiry;
                atmStrike = data.atm_strike;
                currentStrike = "ATM";
                
                return loadStrikes();
            })
            .catch(err => {
                isMetadataLoading = false;
                console.error(err);
                if (startBtn && !isRunning) {
                    startBtn.disabled = false;
                    startBtn.innerText = "Connect Option Stream";
                }
                alert("Upstox Connection Failed: Ensure Upstox Token is valid in token.txt");
                expSelect.innerHTML = "<option value=''>Error Connecting</option>";
                currentExpiry = "";
                atmStrike = null;
                strikesList = [];
                updateStrikeDropdown([]);
            });
        }

        function loadStrikes() {
            if (!currentExpiry) {
                isMetadataLoading = false;
                return Promise.resolve();
            }
            
            isMetadataLoading = true;
            const listEl = document.getElementById("strike-options-list");
            listEl.innerHTML = "<div style='padding:12px; text-align:center; color:var(--text-mute);'>Loading Strikes...</div>";
            
            return fetch(`/api/strikes?expiry=${currentExpiry}&type=${currentOptionType}&exchange=${currentExchange}&index=${currentIndex}`)
            .then(r => {
                if (!r.ok) {
                    throw new Error("HTTP error " + r.status);
                }
                return r.json();
            })
            .then(strikes => {
                isMetadataLoading = false;
                strikesList = strikes;
                updateStrikeDropdown(strikes);
                if (isRunning) {
                    triggerTargetUpdate();
                }
            })
            .catch(err => {
                isMetadataLoading = false;
                console.error(err);
                listEl.innerHTML = "<div style='padding:12px; text-align:center; color:var(--accent-red);'>Error Loading Strikes</div>";
            });
        }

        function updateStrikeDropdown(strikes) {
            const listEl = document.getElementById("strike-options-list");
            listEl.innerHTML = "";
            
            // ATM Option
            const atmLabel = atmStrike ? `Dynamic ATM (₹${atmStrike})` : "Dynamic ATM Strike";
            const atmOpt = document.createElement("div");
            atmOpt.className = "dropdown-option atm-strike" + (currentStrike === "ATM" ? " selected" : "");
            atmOpt.innerText = atmLabel;
            atmOpt.onclick = () => selectStrike("ATM");
            listEl.appendChild(atmOpt);
            
            // Rest of strikes
            strikes.forEach(stk => {
                const isSelected = (currentStrike !== "ATM" && parseFloat(currentStrike) === parseFloat(stk));
                const isAtm = (atmStrike && parseFloat(stk) === parseFloat(atmStrike));
                
                const opt = document.createElement("div");
                opt.className = "dropdown-option" + (isSelected ? " selected" : "") + (isAtm ? " atm-strike" : "");
                opt.innerText = parseFloat(stk).toFixed(0);
                opt.onclick = () => selectStrike(stk);
                listEl.appendChild(opt);
            });
            
            // Update trigger label
            const triggerEl = document.getElementById("strike-trigger");
            if (currentStrike === "ATM") {
                triggerEl.innerText = atmStrike ? `Dynamic ATM Strike (${atmStrike})` : "Dynamic ATM Strike";
            } else if (currentStrike) {
                const parsed = parseFloat(currentStrike);
                triggerEl.innerText = isNaN(parsed) ? currentStrike : parsed.toFixed(0);
            } else {
                triggerEl.innerText = "Select Strike";
            }
        }

        function selectStrike(stk) {
            currentStrike = stk;
            document.getElementById("strike-menu").classList.remove("show");
            updateStrikeDropdown(strikesList);
            if (isRunning) {
                triggerTargetUpdate();
            }
        }

        function toggleStrikeDropdown() {
            const menu = document.getElementById("strike-menu");
            const isShown = menu.classList.contains("show");
            
            // Close all dropdowns first
            document.querySelectorAll(".dropdown-menu").forEach(m => m.classList.remove("show"));
            
            if (!isShown) {
                menu.classList.add("show");
                // Clear search input
                const searchInput = document.getElementById("strike-search-input");
                searchInput.value = "";
                filterStrikes();
                
                // Scroll ATM option into view center
                setTimeout(() => {
                    const listContainer = document.getElementById("strike-options-list");
                    const selectedEl = listContainer.querySelector(".dropdown-option.selected") || listContainer.querySelector(".dropdown-option.atm-strike");
                    if (selectedEl) {
                        const containerHeight = listContainer.clientHeight;
                        const elemTop = selectedEl.offsetTop;
                        const elemHeight = selectedEl.clientHeight;
                        listContainer.scrollTop = elemTop - (containerHeight / 2) + (elemHeight / 2);
                    }
                }, 50);
            }
        }

        function filterStrikes() {
            const query = document.getElementById("strike-search-input").value.trim().toLowerCase();
            const options = document.querySelectorAll("#strike-options-list .dropdown-option");
            options.forEach(opt => {
                if (opt.classList.contains("atm-strike") && opt.innerText.includes("Dynamic")) {
                    opt.style.display = "flex";
                    return;
                }
                const txt = opt.innerText.toLowerCase();
                if (txt.includes(query)) {
                    opt.style.display = "flex";
                } else {
                    opt.style.display = "none";
                }
            });
        }

        window.addEventListener("click", function(e) {
            if (!e.target.closest("#strike-dropdown-container")) {
                document.getElementById("strike-menu").classList.remove("show");
            }
            if (!e.target.closest("#indicators-menu-container")) {
                const indicatorsDropdown = document.getElementById("indicators-dropdown");
                if (indicatorsDropdown) {
                    indicatorsDropdown.style.display = "none";
                }
            }
        });

        function triggerTargetUpdate() {
            if (!isRunning) return;
            const payload = {
                exchange: currentExchange,
                index_name: currentIndex,
                expiry: currentExpiry,
                option_type: currentOptionType,
                strike: currentStrike
            };
            fetch('/api/standard/update_target', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    logConsole("[ERROR] Target update failed: " + data.error);
                } else {
                    logConsole("[SYSTEM] Target updated to " + data.status.trading_symbol);
                }
            });
        }

        function setDeskMode(mode) {
            deskMode = mode;
            document.getElementById("mode-paper-btn").classList.remove("active");
            document.getElementById("mode-live-btn").classList.remove("active");
            
            if (mode === 'PAPER') {
                document.getElementById("mode-paper-btn").classList.add("active");
                document.getElementById("live-trading-toggle-row").style.display = "none";
            } else {
                document.getElementById("mode-live-btn").classList.add("active");
                document.getElementById("live-trading-toggle-row").style.display = "flex";
            }
            if (typeof saveLocalSettings === 'function') saveLocalSettings();
        }

        // Setup TradingView Lightweight Charts variables
        let candleSeries = null;
        let ema5Series = null;
        let ema20Series = null;
        let sma10Series = null;
        let bbUpperSeries = null;
        let bbMiddleSeries = null;
        let bbLowerSeries = null;
        let activePriceLines = {};

        function initChart() {
            try {
                if (typeof LightweightCharts === 'undefined') {
                    console.error("TradingView Lightweight Charts library is not loaded yet.");
                    return;
                }
                const container = document.getElementById("chart-ha");
                if (!container) return;
                container.innerHTML = "";
                
                chart = LightweightCharts.createChart(container, {
                    width: container.clientWidth || 600,
                    height: container.clientHeight || 450,
                    layout: {
                        background: { type: 'solid', color: '#16141f' },
                        textColor: '#908caa',
                        fontSize: 10.5,
                        fontFamily: 'var(--font-family-mono)'
                    },
                    grid: {
                        vertLines: { color: 'rgba(57, 53, 82, 0.15)', style: 2 },
                        horzLines: { color: 'rgba(57, 53, 82, 0.15)', style: 2 }
                    },
                    crosshair: {
                        mode: 0, // Normal
                        vertLine: {
                            color: 'rgba(144, 140, 170, 0.5)',
                            width: 1,
                            style: 3,
                            labelBackgroundColor: '#232136'
                        },
                        horzLine: {
                            color: 'rgba(144, 140, 170, 0.5)',
                            width: 1,
                            style: 3,
                            labelBackgroundColor: '#232136'
                        }
                    },
                    rightPriceScale: {
                        borderColor: '#393552',
                        autoScale: true
                    },
                    timeScale: {
                        borderColor: '#393552',
                        timeVisible: true,
                        secondsVisible: false,
                        rightOffset: 5,
                        barSpacing: 6
                    }
                });

                candleSeries = chart.addCandlestickSeries({
                    upColor: '#3fd18a',
                    downColor: '#eb6f92',
                    borderUpColor: '#3fd18a',
                    borderDownColor: '#eb6f92',
                    wickUpColor: '#3fd18a',
                    wickDownColor: '#eb6f92'
                });

                ema5Series = chart.addLineSeries({
                    color: '#ff9f1c',
                    lineWidth: 1.5,
                    title: 'EMA 5',
                    priceLineVisible: false
                });

                ema20Series = chart.addLineSeries({
                    color: '#4c6fff',
                    lineWidth: 1.5,
                    title: 'EMA 20',
                    priceLineVisible: false
                });

                sma10Series = chart.addLineSeries({
                    color: '#9ccfd8',
                    lineWidth: 1.5,
                    title: 'SMA 10',
                    priceLineVisible: false
                });

                bbUpperSeries = chart.addLineSeries({
                    color: '#ebbcba',
                    lineWidth: 1.2,
                    lineStyle: 1, // Dashed
                    title: 'BB Upper',
                    priceLineVisible: false
                });

                bbMiddleSeries = chart.addLineSeries({
                    color: '#908caa',
                    lineWidth: 1.2,
                    lineStyle: 2, // Dotted
                    title: 'BB Basis',
                    priceLineVisible: false
                });

                bbLowerSeries = chart.addLineSeries({
                    color: '#ebbcba',
                    lineWidth: 1.2,
                    lineStyle: 1, // Dashed
                    title: 'BB Lower',
                    priceLineVisible: false
                });

                chart.subscribeCrosshairMove(param => {
                    if (param.time) {
                        const price = param.seriesData.get(candleSeries);
                        if (price) {
                            document.getElementById("tv-open").innerText = price.open.toFixed(2);
                            document.getElementById("tv-high").innerText = price.high.toFixed(2);
                            document.getElementById("tv-low").innerText = price.low.toFixed(2);
                            document.getElementById("tv-close").innerText = price.close.toFixed(2);
                            
                            const d = new Date(param.time * 1000);
                            const pad = num => String(num).padStart(2, '0');
                            document.getElementById("tv-time").innerText = `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
                        }
                    } else {
                        updateLatestOHLC();
                    }
                });

                const resizeObserver = new ResizeObserver(entries => {
                    if (entries.length === 0) return;
                    const { width, height } = entries[0].contentRect;
                    chart.resize(width, height || 450);
                });
                resizeObserver.observe(container);
            } catch (e) {
                console.error("Failed to initialize TradingView Lightweight Charts canvas:", e);
            }
        }

        // --- Client-Side Indicators Engine ---
        let activeIndicators = {
            ema5: false,
            ema20: false,
            sma10: false,
            bb: false
        };

        function toggleIndicatorsMenu() {
            const menu = document.getElementById("indicators-dropdown");
            if (menu) {
                const isShown = menu.style.display === "flex";
                menu.style.display = isShown ? "none" : "flex";
            }
        }

        function onIndicatorToggle(indicatorKey) {
            const checkbox = document.getElementById("ind-" + indicatorKey);
            if (checkbox) {
                activeIndicators[indicatorKey] = checkbox.checked;
                lastCandlesCount = -1;
            }
        }

        function calculateEMA(data, period) {
            if (data.length === 0) return [];
            let k = 2 / (period + 1);
            let emaArray = [];
            let ema = data[0].close;
            emaArray.push({ time: data[0].time, value: ema });
            for (let i = 1; i < data.length; i++) {
                let close = data[i].close;
                ema = (close * k) + (ema * (1 - k));
                emaArray.push({ time: data[i].time, value: ema });
            }
            return emaArray;
        }

        function calculateSMA(data, period) {
            let smaArray = [];
            for (let i = 0; i < data.length; i++) {
                if (i >= period - 1) {
                    let sum = 0;
                    for (let j = 0; j < period; j++) {
                        sum += data[i - j].close;
                    }
                    smaArray.push({ time: data[i].time, value: sum / period });
                }
            }
            return smaArray;
        }

        function calculateBollingerBands(data, period, multiplier) {
            let upper = [];
            let middle = [];
            let lower = [];
            for (let i = 0; i < data.length; i++) {
                if (i >= period - 1) {
                    let sum = 0;
                    for (let j = 0; j < period; j++) {
                        sum += data[i - j].close;
                    }
                    let mean = sum / period;
                    middle.push({ time: data[i].time, value: mean });
                    
                    let variance = 0;
                    for (let j = 0; j < period; j++) {
                        variance += Math.pow(data[i - j].close - mean, 2);
                    }
                    let stdDev = Math.sqrt(variance / period);
                    upper.push({ time: data[i].time, value: mean + multiplier * stdDev });
                    lower.push({ time: data[i].time, value: mean - multiplier * stdDev });
                }
            }
            return { upper, middle, lower };
        }

        function updatePriceLine(key, priceValue, options) {
            if (activePriceLines[key]) {
                try {
                    candleSeries.removePriceLine(activePriceLines[key]);
                } catch (e) {}
                delete activePriceLines[key];
            }
            if (priceValue > 0) {
                activePriceLines[key] = candleSeries.createPriceLine({
                    price: priceValue,
                    color: options.color || '#fff',
                    lineWidth: options.lineWidth || 2,
                    lineStyle: options.lineStyle || 1, // 1: Dashed, 2: Dotted
                    axisLabelVisible: true,
                    title: options.title || ''
                });
            }
        }

        function updateUIForConnectionState(connected) {
            // Always keep standard picker selects and buttons enabled
            const pickerSelects = document.querySelectorAll(".instrument-picker-card select, .instrument-picker-card button");
            pickerSelects.forEach(el => {
                el.disabled = false;
            });
            const pickerCard = document.querySelector(".instrument-picker-card");
            if (pickerCard) {
                pickerCard.style.opacity = "1";
            }
            
            // Disable/enable execution forms (but keep tab navigation working)
            const executionInputs = document.querySelectorAll("#pad-scalper select, #pad-scalper input, #pad-scalper button, #pad-standard select, #pad-standard input, #pad-standard button");
            executionInputs.forEach(el => {
                el.disabled = !connected;
            });
            const scalperPad = document.getElementById("pad-scalper");
            if (scalperPad) {
                scalperPad.style.opacity = connected ? "1" : "0.5";
            }
            const standardPad = document.getElementById("pad-standard");
            if (standardPad) {
                standardPad.style.opacity = connected ? "1" : "0.5";
            }
        }

        function resetToNifty50Defaults() {
            currentExchange = "NSE";
            currentIndex = "NIFTY";
            currentOptionType = "CE";
            currentStrike = "ATM";
            
            // Sync UI active classes for Exchange, Index, and Option Type
            document.querySelectorAll('#exchange-toggle .toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-val') === 'NSE');
            });
            
            // Re-populate Index toggle
            const indexToggle = document.getElementById("index-toggle");
            indexToggle.innerHTML = "";
            const list = indicesByExchange["NSE"] || [];
            list.forEach((idx) => {
                const btn = document.createElement("button");
                btn.className = "toggle-btn" + (idx.val === "NIFTY" ? " active" : "");
                btn.setAttribute("data-val", idx.val);
                btn.innerText = idx.name;
                btn.onclick = () => setIndex(idx.val);
                indexToggle.appendChild(btn);
            });
            
            document.querySelectorAll('#opt-type-toggle .toggle-btn').forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-val') === 'CE');
            });
            
            return loadExpiries();
        }

        // Handle execution session startup
        function toggleExecutionSession() {
            if (isRunning) {
                // stop
                fetch('/stop', { method: 'POST' })
                .then(r => r.json())
                .then(() => {
                    isRunning = false;
                    const startBtn = document.getElementById("execute-btn");
                    if (startBtn) {
                        startBtn.disabled = false;
                        startBtn.innerText = "Connect Option Stream";
                        startBtn.style.background = "var(--accent)";
                        startBtn.style.color = "#16141f";
                    }
                    document.getElementById("hud-stream-state").innerText = "DISCONNECTED";
                    document.getElementById("hud-stream-state").style.color = "var(--text-mute)";
                    logConsole("[SYSTEM] Trading Session Disconnected.");
                    updateUIForConnectionState(false);
                });
            } else {
                // start
                // Reset to Nifty 50 CE ATM defaults before starting the stream
                resetToNifty50Defaults().then(() => {
                    const isLive = (deskMode === 'MANUAL');
                    const realExec = isLive && document.getElementById("ctrl-real-exec").checked;
                    
                    const payload = {
                        mode: isLive ? "MANUAL" : "PAPER",
                        live_trading: realExec,
                        live_protection: true,
                        expiry: currentExpiry,
                        option_type: currentOptionType,
                        strike: currentStrike,
                        exchange: currentExchange,
                        index_name: currentIndex,
                        scalper_expiry: currentExpiry,
                        scalper_option_type: currentOptionType,
                        scalper_strike: currentStrike,
                        lot_size: 1,
                        timeframe: '1minute',
                        max_candles: 10,
                        brokerage_flat: 20.0,
                        slippage_pct: 0.05,
                        initial_balance: 100000.0
                    };

                    fetch('/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.error) {
                            alert(data.error);
                            return;
                        }
                        isRunning = true;
                        document.getElementById("execute-btn").innerText = "Disconnect Stream";
                        document.getElementById("execute-btn").style.background = "var(--accent-red)";
                        document.getElementById("execute-btn").style.color = "#16141f";
                        
                        const isLiveMode = (deskMode === 'MANUAL');
                        const modeStr = isLiveMode ? "LIVE" : "PAPER";
                        document.getElementById("hud-stream-state").innerText = `CONNECTED (${modeStr})`;
                        document.getElementById("hud-stream-state").style.color = "var(--green-glow)";
                        
                        initChart();
                        updateUIForConnectionState(true);
                        setTimeout(updateTelemetry, 1000);
                    });
                });
            }
        }

        // Order Fills execution
        function placeOrder(side, isScalper) {
            if (!isRunning) {
                alert("Option stream is not connected.");
                return;
            }

            let qty, target, targetType, stopLoss, stopLossType;
            if (isScalper) {
                qty = scalperLots;
                target = parseFloat(document.getElementById("sc-bracket-target").value) || 0.0;
                targetType = document.getElementById("sc-bracket-target-type").value;
                stopLoss = parseFloat(document.getElementById("sc-bracket-sl").value) || 0.0;
                stopLossType = document.getElementById("sc-bracket-sl-type").value;
            } else {
                qty = typeof selectedQty !== 'undefined' ? selectedQty : 1;
                const targetEl = document.getElementById("gtt-target-pct");
                target = targetEl ? parseFloat(targetEl.value) || 0.0 : 0.0;
                targetType = "percent";
                const slEl = document.getElementById("gtt-sl-pct");
                stopLoss = slEl ? parseFloat(slEl.value) || 0.0 : 0.0;
                stopLossType = "percent";
            }

            const endpoint = (side === 'BUY') ? '/manual/buy' : '/manual/sell';
            const payload = {
                qty: qty,
                target: target,
                target_type: targetType,
                stop_loss: stopLoss,
                stop_loss_type: stopLossType,
                is_scalper: isScalper
            };

            fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    logConsole("[ERROR] " + data.error);
                } else {
                    const symb = isScalper ? data.status.scalper_trading_symbol : data.status.trading_symbol;
                    logConsole(`[TRADE] Filled ${side} ${qty} Lots of ${symb} at Market.`);
                }
            });
        }

        function executePanicExit() {
            if (!isRunning) {
                alert("Option stream is not connected.");
                return;
            }
            fetch('/manual/panic_exit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    logConsole("[ERROR] Panic Exit failed: " + data.error);
                } else {
                    logConsole("[SYSTEM] Panic Exit Completed: " + data.message);
                }
            })
            .catch(err => {
                logConsole("[ERROR] Panic Exit failed: " + err);
            });
        }

        function setPreset(inputId, value, type) {
            const input = document.getElementById(inputId);
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('input'));
                input.dispatchEvent(new Event('change'));
                
                const typeSelect = document.getElementById(inputId + '-type');
                if (typeSelect && type) {
                    typeSelect.value = type;
                    typeSelect.dispatchEvent(new Event('change'));
                }
            }
        }

        function handleAtrChange(inputId) {
            const typeSelect = document.getElementById(inputId + '-type');
            const input = document.getElementById(inputId);
            if (!typeSelect || !input) return;
            
            if (typeSelect.value === 'atr') {
                input.readOnly = true;
                input.style.opacity = '0.7';
                fetchAtrAndUpdate(inputId);
            } else {
                input.readOnly = false;
                input.style.opacity = '1.0';
            }
            if (typeof saveLocalSettings === 'function') saveLocalSettings();
        }

        function fetchAtrAndUpdate(inputId) {
            fetch('/api/atr')
                .then(r => r.json())
                .then(data => {
                    if (data.atr) {
                        const multiplier = inputId.includes('sl') ? 1.5 : 2.0;
                        const finalVal = parseFloat((data.atr * multiplier).toFixed(2));
                        const input = document.getElementById(inputId);
                        const typeSelect = document.getElementById(inputId + '-type');
                        if (input && typeSelect && typeSelect.value === 'atr') {
                            input.value = finalVal;
                            saveLocalSettings();
                        }
                    }
                })
                .catch(err => console.error("Failed to fetch ATR:", err));
        }

        function refreshAutoAtr() {
            const slType = document.getElementById('sc-bracket-sl-type');
            if (slType && slType.value === 'atr') {
                fetchAtrAndUpdate('sc-bracket-sl');
            }
            const targetType = document.getElementById('sc-bracket-target-type');
            if (targetType && targetType.value === 'atr') {
                fetchAtrAndUpdate('sc-bracket-target');
            }
        }

        // Submit GTT trigger
        function submitGttOrder() {
            const triggerPrice = parseFloat(document.getElementById("gtt-trigger-price").value) || 0;
            const side = document.getElementById("gtt-side").value;
            const qty = parseInt(document.getElementById("gtt-qty").value) || 1;
            const mode = document.getElementById("gtt-mode").value;
            const target = parseFloat(document.getElementById("gtt-target").value) || 0;
            const targetType = document.getElementById("gtt-target-type").value;
            const stopLoss = parseFloat(document.getElementById("gtt-sl").value) || 0;
            const stopLossType = document.getElementById("gtt-sl-type").value;

            if (triggerPrice <= 0) {
                alert("Please provide a valid trigger price.");
                return;
            }

            const payload = {
                trigger_price: triggerPrice,
                side: side,
                qty: qty,
                order_type: mode,
                target: target,
                target_type: targetType,
                stop_loss: stopLoss,
                stop_loss_type: stopLossType
            };

            fetch('/manual/gtt/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    logConsole(`[GTT] Registered trigger for ${side} at ₹${triggerPrice.toFixed(2)}`);
                    switchLowerTab('gtt-registry');
                }
            });
        }

        function cancelGttOrder(id) {
            fetch('/manual/gtt/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                } else {
                    logConsole(`[GTT] Cancelled trigger ID ${id}`);
                }
            });
        }

        // Chart toolbar controls state
        let activeInterval = '1m';
        let activeChartType = 'ha';
        let prevLastCandle = null;

        function changeChartInterval(interval) {
            activeInterval = interval;
            document.querySelectorAll('.timeframe-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.innerText.toLowerCase() === interval.toLowerCase()) {
                    btn.classList.add('active');
                }
            });
            sendChartConfig();
        }

        function changeChartType(type) {
            activeChartType = type;
            document.querySelectorAll('.chart-type-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.innerText.toLowerCase() === type.toLowerCase()) {
                    btn.classList.add('active');
                }
            });
            sendChartConfig();
        }

        function sendChartConfig() {
            let backendInterval = '1minute';
            if (activeInterval === '10s') backendInterval = '10s';
            else if (activeInterval === '30s') backendInterval = '30s';
            else if (activeInterval === '1m') backendInterval = '1minute';
            else if (activeInterval === '5m') backendInterval = '5minute';
            else if (activeInterval === '15m') backendInterval = '15minute';
            
            let backendType = activeChartType === 'normal' ? 'normal' : 'heikin_ashi';
            
            // Reset trackers
            lastCandlesCount = 0;
            prevLastCandle = null;
            
            fetch('/api/chart/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    interval: backendInterval,
                    candle_type: backendType
                })
            })
            .then(r => r.json())
            .then(data => {
                logConsole(`[CHART] Updated interval to ${activeInterval}, type to ${activeChartType.toUpperCase()}`);
            });
        }

        // Live stats update loop
        let lastCandlesCount = 0;
        let latestCandle = null;

        function updateLatestOHLC() {
            if (latestCandle) {
                document.getElementById("tv-open").innerText = latestCandle.open.toFixed(2);
                document.getElementById("tv-high").innerText = latestCandle.high.toFixed(2);
                document.getElementById("tv-low").innerText = latestCandle.low.toFixed(2);
                document.getElementById("tv-close").innerText = latestCandle.close.toFixed(2);
                const timeStr = new Date(latestCandle.time * 1000).toLocaleTimeString();
                document.getElementById("tv-time").innerText = timeStr;
            }
        }

        // DOM Sizing Simulation Jitter Function
        const secHash = new Date().getSeconds();
        function getSize(price, isBid) {
            const priceHash = Math.abs(Math.sin(price * 1000)) * 1000;
            const baseSize = Math.floor((priceHash % 12) + 4) * 65; 
            const sec = new Date().getSeconds();
            const jitter = Math.sin(priceHash + sec) * 0.25; 
            return Math.floor(baseSize * (1 + jitter));
        }

        function updateTelemetry() {
            fetch('/telemetry')
            .then(r => r.json())
            .then(data => {
                const status = data.status;
                spotPrice = status.spot_price || 0.0;
                const scalpSpot = status.scalper_spot_price || 0.0;
                const scalpLotMult = status.scalper_lot_multiplier || 65;
                lotMultiplier = status.lot_size_multiplier || 65;

                // Sync badge & contracts label
                const activeContract = status.trading_symbol || "--";
                const prevContract = document.getElementById("hud-active-contract").innerText;
                if (activeContract !== "--" && activeContract !== prevContract) {
                    hasInitializedDefaults = false;
                }
                document.getElementById("hud-active-contract").innerText = activeContract;

                if (spotPrice > 0 && !hasInitializedDefaults) {
                    initDefaultOrderPadValues();
                }
                const scalpContractEl = document.getElementById("hud-scalper-contract");
                if (scalpContractEl) {
                    scalpContractEl.innerText = status.scalper_trading_symbol || "--";
                }
                
                // Get Spot Price and update Index Spot
                const niftySpot = status.nifty_spot || 0.0;
                if (niftySpot > 0) {
                    document.getElementById("hud-spot-price").innerText = "₹" + parseFloat(niftySpot).toFixed(2);
                } else if (spotPrice > 0) {
                    document.getElementById("hud-spot-price").innerText = "₹" + parseFloat(spotPrice).toFixed(2);
                }

                // Update Spot Price Label based on current selected Index
                const spotLabelEl = document.getElementById("hud-spot-label");
                if (spotLabelEl) {
                    spotLabelEl.innerText = (status.index_name || "NIFTY") + " SPOT:";
                }

                const isScalperCE = (status.scalper_option_type || "CE") === "CE";
                
                // Update Mapped buttons based on scalper's option type
                const buyBtn = document.getElementById("scalp-buy-btn");
                const sellBtn = document.getElementById("scalp-sell-btn");
                if (isScalperCE) {
                    buyBtn.firstElementChild.innerText = "Buy Call";
                    sellBtn.firstElementChild.innerText = "Sell Call";
                } else {
                    buyBtn.firstElementChild.innerText = "Buy Put";
                    sellBtn.firstElementChild.innerText = "Sell Put";
                }

                // Update Scalper display fields
                document.getElementById("sc-ltp").innerText = scalpSpot.toFixed(2);
                
                // Check if active position is scalper's position
                const isPosScalper = status.position && status.position.is_scalper;
                document.getElementById("sc-lots").innerText = isPosScalper ? status.lot_size : 0;
                document.getElementById("sc-avg").innerText = isPosScalper ? status.position.entry_price.toFixed(2) : "0.00";
                
                // Bid / Ask simulation for Scalper contract
                const bidPrice = scalpSpot > 0 ? scalpSpot - 0.05 : 0.00;
                const askPrice = scalpSpot > 0 ? scalpSpot + 0.05 : 0.00;
                document.getElementById("sc-bid").innerText = bidPrice.toFixed(2);
                document.getElementById("sc-ask").innerText = askPrice.toFixed(2);

                // P&L for Scalper position
                const contractPlEl = document.getElementById("sc-pnl");
                if (isPosScalper) {
                    const openPnl = (scalpSpot - status.position.entry_price) * (status.lot_size * scalpLotMult);
                    contractPlEl.innerText = (openPnl >= 0 ? "+" : "") + openPnl.toFixed(2);
                    contractPlEl.style.color = openPnl >= 0 ? "var(--green-glow)" : "var(--red-glow)";
                } else {
                    contractPlEl.innerText = "0.00";
                    contractPlEl.style.color = "inherit";
                }

                // Update dynamic lots subtext label
                document.getElementById("sc-selected-lots").innerText = scalperLots + " lots";
                document.getElementById("sc-selected-qty").innerText = "(" + (scalperLots * scalpLotMult) + " qty.)";

                // DOM Depth simulation rendering
                const domLadderBody = document.getElementById("dom-ladder-body");
                const domSpreadEl = document.getElementById("dom-spread");
                const activeTab = document.getElementById('pad-std-btn').classList.contains('active') ? 'standard' : 'scalper';
                const currentLtp = (activeTab === 'scalper') ? scalpSpot : spotPrice;
                
                if (currentLtp > 0) {
                    domLadderBody.innerHTML = "";
                    const spread = 0.10;
                    domSpreadEl.innerText = "Spread: " + spread.toFixed(2);
                    
                    // Generate 5 Ask levels (highest price down to lowest price)
                    const asks = [];
                    for (let i = 4; i >= 0; i--) {
                        const price = currentLtp + (spread / 2) + (i * 0.05);
                        const size = getSize(price, false);
                        asks.push({ price, size });
                    }
                    
                    asks.forEach(ask => {
                        const tr = document.createElement("tr");
                        const sizePercent = Math.min((ask.size / 2000) * 100, 100);
                        tr.style.background = `linear-gradient(to left, rgba(235,111,146,0.12) ${sizePercent}%, transparent ${sizePercent}%)`;
                        tr.innerHTML = `
                            <td style="color: var(--text-mute); font-family: var(--font-family-mono);">${ask.size}</td>
                            <td class="text-red" style="font-weight: 700; font-size: 10px; padding-right: 12px;">ASK</td>
                            <td style="font-weight: 700; font-family: var(--font-family-mono); color: var(--text-main);">₹${ask.price.toFixed(2)}</td>
                        `;
                        domLadderBody.appendChild(tr);
                    });
                    
                    // LTP row in the middle
                    const ltpTr = document.createElement("tr");
                    ltpTr.className = "dom-ltp-row";
                    ltpTr.style.background = "rgba(246, 193, 119, 0.08)";
                    ltpTr.innerHTML = `
                        <td colspan="2" style="text-align: left; color: var(--accent-amber); font-weight: 700; font-size: 10px; padding-left: 12px; letter-spacing: 0.5px;">LTP LAST PRICE</td>
                        <td style="color: var(--accent-amber); font-weight: 800; font-size: 12px; font-family: var(--font-family-mono);">₹${currentLtp.toFixed(2)}</td>
                    `;
                    domLadderBody.appendChild(ltpTr);
                    
                    // Generate 5 Bid levels (highest price down to lowest price)
                    const bids = [];
                    for (let i = 0; i < 5; i++) {
                        const price = currentLtp - (spread / 2) - (i * 0.05);
                        const size = getSize(price, true);
                        bids.push({ price, size });
                    }
                    
                    bids.forEach(bid => {
                        const tr = document.createElement("tr");
                        const sizePercent = Math.min((bid.size / 2000) * 100, 100);
                        tr.style.background = `linear-gradient(to left, rgba(63,209,138,0.12) ${sizePercent}%, transparent ${sizePercent}%)`;
                        tr.innerHTML = `
                            <td style="color: var(--text-mute); font-family: var(--font-family-mono);">${bid.size}</td>
                            <td class="text-green" style="font-weight: 700; font-size: 10px; padding-right: 12px;">BID</td>
                            <td style="font-weight: 700; font-family: var(--font-family-mono); color: var(--text-main);">₹${bid.price.toFixed(2)}</td>
                        `;
                        domLadderBody.appendChild(tr);
                    });
                } else {
                    domLadderBody.innerHTML = `<tr><td colspan="3" style="text-align:center; color: var(--text-mute); padding: 24px;">No streaming data available. Connect stream.</td></tr>`;
                    domSpreadEl.innerText = "Spread: --";
                }

                // Positions Table
                const posBody = document.getElementById("positions-table-body");
                if (status.position) {
                    const posSym = status.position.is_scalper ? status.scalper_trading_symbol : status.trading_symbol;
                    const posLtp = status.position.is_scalper ? scalpSpot : spotPrice;
                    const posLotMult = status.position.is_scalper ? scalpLotMult : lotMultiplier;
                    
                    const openPnl = (posLtp - status.position.entry_price) * (status.lot_size * posLotMult);
                    const targetStr = status.position.target_price > 0 ? "₹" + status.position.target_price.toFixed(2) : "--";
                    const slStr = status.position.stop_loss > 0 ? "₹" + status.position.stop_loss.toFixed(2) : "--";
                    
                    posBody.innerHTML = `
                        <tr>
                            <td style="font-family:var(--font-family-mono); font-weight:700;">${posSym}</td>
                            <td>₹${status.position.entry_price.toFixed(2)}</td>
                            <td>${status.lot_size}</td>
                            <td>${targetStr}</td>
                            <td>${slStr}</td>
                            <td class="${openPnl >= 0 ? 'text-green' : 'text-red'}" style="font-family:var(--font-family-mono); font-weight:700;">
                                ₹${openPnl.toFixed(2)}
                            </td>
                            <td>
                                <button onclick="placeOrder('SELL', ${status.position.is_scalper})" style="background:var(--accent-red); color:#16141f; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-weight:700;">
                                    Market Exit
                                </button>
                            </td>
                        </tr>
                    `;
                } else {
                    posBody.innerHTML = `
                        <tr>
                            <td colspan="7" style="text-align:center; color:var(--text-mute);">No active position.</td>
                        </tr>
                    `;
                }

                // GTT Registry Table
                const gttBody = document.getElementById("gtt-table-body");
                if (data.gtt_orders && data.gtt_orders.length > 0) {
                    gttBody.innerHTML = "";
                    data.gtt_orders.forEach(order => {
                        const tr = document.createElement("tr");
                        const tgtDesc = order.target > 0 ? `${order.target} ${order.target_type === 'points' ? 'pts' : '%'}` : "--";
                        const slDesc = order.stop_loss > 0 ? `${order.stop_loss} ${order.stop_loss_type === 'points' ? 'pts' : '%'}` : "--";
                        
                        let cancelAction = "";
                        if (order.status === "PENDING") {
                            cancelAction = `<button onclick="cancelGttOrder('${order.id}')" style="background:#555; color:#fff; border:none; padding:2px 6px; border-radius:4px; cursor:pointer;">Cancel</button>`;
                        }

                        tr.innerHTML = `
                            <td style="font-family:var(--font-family-mono);">${order.id}</td>
                            <td class="${order.side === 'BUY' ? 'text-green' : 'text-red'}">${order.side}</td>
                            <td>₹${order.trigger_price.toFixed(2)}</td>
                            <td>${order.qty}</td>
                            <td>Tgt: ${tgtDesc} / SL: ${slDesc}</td>
                            <td style="font-weight:700; color:${order.status === 'PENDING' ? '#ff9f1c' : (order.status === 'TRIGGERED' ? 'var(--green-glow)' : 'var(--text-mute)')}">${order.status}</td>
                            <td>${order.timestamp}</td>
                            <td>${cancelAction}</td>
                        `;
                        gttBody.appendChild(tr);
                    });
                } else {
                    gttBody.innerHTML = `
                        <tr>
                            <td colspan="8" style="text-align:center; color:var(--text-mute);">No active GTT triggers.</td>
                        </tr>
                    `;
                }

                // Order Fills registry
                const histBody = document.getElementById("history-table-body");
                if (data.trades && data.trades.length > 0) {
                    histBody.innerHTML = "";
                    data.trades.forEach(trade => {
                        const tr = document.createElement("tr");
                        const pnlText = trade.pnl !== undefined ? `₹${trade.pnl.toFixed(2)}` : "--";
                        const pnlClass = trade.pnl !== undefined ? (trade.pnl >= 0 ? "text-green" : "text-red") : "";
                        
                        tr.innerHTML = `
                            <td>${trade.timestamp}</td>
                            <td class="${trade.type === 'BUY' ? 'text-green' : 'text-red'}" style="font-weight:700;">${trade.type}</td>
                            <td>₹${trade.price.toFixed(2)}</td>
                            <td>${trade.sl > 0 ? "₹" + trade.sl.toFixed(2) : "--"}</td>
                            <td class="${pnlClass}" style="font-family:var(--font-family-mono); font-weight:700;">${pnlText}</td>
                            <td>${trade.details || trade.reason}</td>
                        `;
                        histBody.appendChild(tr);
                    });
                } else {
                    histBody.innerHTML = `
                        <tr>
                            <td colspan="6" style="text-align:center; color:var(--text-mute);">No fills recorded.</td>
                        </tr>
                    `;
                }

                // Console event logs
                const consoleDiv = document.getElementById("console-logs-div");
                consoleDiv.innerHTML = "";
                if (data.logs && data.logs.length > 0) {
                    data.logs.slice().reverse().forEach(log => {
                        const p = document.createElement("p");
                        p.className = "console-log";
                        
                        let color = "var(--text-main)";
                        if (log.includes("[TRADE]")) color = "var(--accent-blue)";
                        else if (log.includes("[ERROR]") || log.includes("REJECTED")) color = "var(--accent-red)";
                        else if (log.includes("[SYSTEM]") || log.includes("[ENGINE]")) color = "var(--text-mute)";
                        
                        p.style.color = color;
                        p.innerText = log;
                        consoleDiv.appendChild(p);
                    });
                }

                // Update Chart Candlestick series
                if (data.candles && data.candles.length > 0) {
                    try {
                        if (!chart) {
                            initChart();
                        }
                        if (chart) {
                            // Map and filter unique timestamps for TV standalone charts
                            const uniqueCandles = [];
                            const seenTimes = new Set();
                            for (let i = 0; i < data.candles.length; i++) {
                                const c = data.candles[i];
                                const t = parseInt(c.time);
                                if (!seenTimes.has(t)) {
                                    seenTimes.add(t);
                                    uniqueCandles.push({
                                        time: t,
                                        open: c.open,
                                        high: c.high,
                                        low: c.low,
                                        close: c.close
                                    });
                                }
                            }
                            uniqueCandles.sort((a, b) => a.time - b.time);

                            if (uniqueCandles.length > 0) {
                                latestCandle = data.candles[data.candles.length - 1];
                                updateLatestOHLC();

                                const lastCandle = uniqueCandles[uniqueCandles.length - 1];
                                const hasChanged = (data.candles.length !== lastCandlesCount) || 
                                                   (!prevLastCandle) ||
                                                   (lastCandle.time !== prevLastCandle.time) ||
                                                   (lastCandle.open !== prevLastCandle.open) ||
                                                   (lastCandle.high !== prevLastCandle.high) ||
                                                   (lastCandle.low !== prevLastCandle.low) ||
                                                   (lastCandle.close !== prevLastCandle.close);

                                if (hasChanged) {
                                    candleSeries.setData(uniqueCandles);

                                    // Compute technical indicators client-side
                                    if (activeIndicators.ema5) {
                                        ema5Series.setData(calculateEMA(uniqueCandles, 5));
                                    } else {
                                        ema5Series.setData([]);
                                    }

                                    if (activeIndicators.ema20) {
                                        ema20Series.setData(calculateEMA(uniqueCandles, 20));
                                    } else {
                                        ema20Series.setData([]);
                                    }

                                    if (activeIndicators.sma10) {
                                        sma10Series.setData(calculateSMA(uniqueCandles, 10));
                                    } else {
                                        sma10Series.setData([]);
                                    }

                                    if (activeIndicators.bb) {
                                        const bb = calculateBollingerBands(uniqueCandles, 20, 2);
                                        bbUpperSeries.setData(bb.upper);
                                        bbMiddleSeries.setData(bb.middle);
                                        bbLowerSeries.setData(bb.lower);
                                    } else {
                                        bbUpperSeries.setData([]);
                                        bbMiddleSeries.setData([]);
                                        bbLowerSeries.setData([]);
                                    }

                                    // Dynamic price lines (LTP, Entry, SL, Target)
                                    const chartSym = status.trading_symbol || "--";
                                    const posSym = status.position ? (status.position.is_scalper ? status.scalper_trading_symbol : status.trading_symbol) : null;
                                    const isChartPosMatch = status.position && (posSym === chartSym);

                                    // Live LTP Line
                                    updatePriceLine('ltp', currentLtp, {
                                        color: '#f6c177',
                                        lineWidth: 1.5,
                                        lineStyle: 1, // Dashed
                                        title: 'LTP'
                                    });

                                    // Active trade position annotations
                                    if (isChartPosMatch) {
                                        const pos = status.position;
                                        updatePriceLine('entry', pos.entry_price, {
                                            color: '#4c6fff',
                                            lineWidth: 1.5,
                                            lineStyle: 1, // Dashed
                                            title: 'ENTRY'
                                        });
                                        updatePriceLine('target', pos.target_price, {
                                            color: '#3fd18a',
                                            lineWidth: 1.5,
                                            lineStyle: 1, // Dashed
                                            title: 'TARGET'
                                        });
                                        updatePriceLine('sl', pos.stop_loss, {
                                            color: '#eb6f92',
                                            lineWidth: 1.5,
                                            lineStyle: 1, // Dashed
                                            title: 'SL'
                                        });
                                    } else {
                                        updatePriceLine('entry', 0, {});
                                        updatePriceLine('target', 0, {});
                                        updatePriceLine('sl', 0, {});
                                    }

                                    lastCandlesCount = data.candles.length;
                                    prevLastCandle = { 
                                        time: lastCandle.time, 
                                        open: lastCandle.open, 
                                        high: lastCandle.high, 
                                        low: lastCandle.low, 
                                        close: lastCandle.close 
                                    };
                                }
                            }
                        }
                    } catch (err) {
                        console.error("Failed to update TradingView chart values in telemetry tick loop:", err);
                    }
                }

                // Sync state and buttons (only if not loading contracts)
                if (!isMetadataLoading) {
                    const isStateRunning = ["PROCESSING", "LIVE_MONITORING", "RUNNING_BACKTEST"].includes(status.state);
                    const startBtn = document.getElementById("execute-btn");
                    if (isStateRunning) {
                        isRunning = true;
                        if (startBtn) {
                            startBtn.disabled = false;
                            startBtn.innerText = "Disconnect Stream";
                            startBtn.style.background = "var(--accent-red)";
                            startBtn.style.color = "#16141f";
                        }
                        const modeStr = status.mode === "MANUAL" ? "LIVE" : "PAPER";
                        document.getElementById("hud-stream-state").innerText = `CONNECTED (${modeStr})`;
                        document.getElementById("hud-stream-state").style.color = "var(--green-glow)";
                        updateUIForConnectionState(true);
                    } else {
                        isRunning = false;
                        if (startBtn) {
                            startBtn.disabled = false;
                            startBtn.innerText = "Connect Option Stream";
                            startBtn.style.background = "var(--accent)";
                            startBtn.style.color = "#16141f";
                        }
                        document.getElementById("hud-stream-state").innerText = "DISCONNECTED";
                        document.getElementById("hud-stream-state").style.color = "var(--text-mute)";
                        updateUIForConnectionState(false);
                    }
                }

                // Repeat update if running
                if (isRunning) {
                    if (typeof refreshAutoAtr === 'function') refreshAutoAtr();
                    setTimeout(updateTelemetry, 1000);
                }
            });
        }

        function logConsole(msg) {
            const consoleDiv = document.getElementById("console-logs-div");
            const p = document.createElement("p");
            p.className = "console-log";
            p.style.color = "var(--text-mute)";
            p.innerText = "[" + new Date().toLocaleTimeString() + "] " + msg;
            consoleDiv.insertBefore(p, consoleDiv.firstChild);
        }

        let activePad = 'scalper'; // track active pad globally

        function saveLocalSettings() {
            const settings = {
                scalperLots: scalperLots,
                scBracketSl: document.getElementById("sc-bracket-sl") ? document.getElementById("sc-bracket-sl").value : "0.0",
                scBracketSlType: document.getElementById("sc-bracket-sl-type") ? document.getElementById("sc-bracket-sl-type").value : "points",
                scBracketTarget: document.getElementById("sc-bracket-target") ? document.getElementById("sc-bracket-target").value : "0.0",
                scBracketTargetType: document.getElementById("sc-bracket-target-type") ? document.getElementById("sc-bracket-target-type").value : "points",
                deskMode: deskMode,
                selectedOrderMode: selectedOrderMode,
                activePad: activePad,
                currentExchange: currentExchange,
                currentIndex: currentIndex,
                currentOptionType: currentOptionType
            };
            localStorage.setItem("valkyrie_manual_settings", JSON.stringify(settings));
        }

        function loadLocalSettings() {
            try {
                const stored = localStorage.getItem("valkyrie_manual_settings");
                if (!stored) return;
                const settings = JSON.parse(stored);
                
                if (settings.scalperLots) {
                    scalperLots = parseInt(settings.scalperLots) || 1;
                    document.getElementById("sc-selected-lots").innerText = scalperLots + " lots";
                    if (typeof lotMultiplier !== 'undefined') {
                        document.getElementById("sc-selected-qty").innerText = "(" + (scalperLots * lotMultiplier) + " qty.)";
                    }
                }
                if (settings.scBracketSl) {
                    const el = document.getElementById("sc-bracket-sl");
                    if (el) el.value = settings.scBracketSl;
                }
                if (settings.scBracketSlType) {
                    const el = document.getElementById("sc-bracket-sl-type");
                    if (el) el.value = settings.scBracketSlType;
                }
                if (settings.scBracketTarget) {
                    const el = document.getElementById("sc-bracket-target");
                    if (el) el.value = settings.scBracketTarget;
                }
                if (settings.scBracketTargetType) {
                    const el = document.getElementById("sc-bracket-target-type");
                    if (el) el.value = settings.scBracketTargetType;
                }
                if (settings.deskMode) {
                    deskMode = settings.deskMode;
                    document.getElementById("mode-paper-btn").classList.remove("active");
                    document.getElementById("mode-live-btn").classList.remove("active");
                    if (deskMode === 'PAPER') {
                        document.getElementById("mode-paper-btn").classList.add("active");
                        document.getElementById("live-trading-toggle-row").style.display = "none";
                    } else {
                        document.getElementById("mode-live-btn").classList.add("active");
                        document.getElementById("live-trading-toggle-row").style.display = "flex";
                    }
                }
                if (settings.selectedOrderMode) {
                    selectedOrderMode = settings.selectedOrderMode;
                    document.getElementById("mode-std").classList.toggle("active", selectedOrderMode === 'STANDARD');
                    document.getElementById("mode-gtt").classList.toggle("active", selectedOrderMode === 'GTT');
                    document.getElementById("gtt-entry-row").style.display = (selectedOrderMode === 'GTT') ? 'block' : 'none';
                    const submitBtn = document.getElementById("main-exec-btn");
                    if (selectedOrderMode === 'GTT') {
                        submitBtn.innerText = "Deploy GTT Trigger";
                        submitBtn.style.background = "var(--accent-amber)";
                        submitBtn.style.color = "#16141f";
                    } else {
                        submitBtn.innerText = "Execute Standard Order";
                        submitBtn.style.background = "var(--accent-purple)";
                        submitBtn.style.color = "#fff";
                    }
                }
                if (settings.activePad) {
                    activePad = settings.activePad;
                    document.getElementById('pad-std-btn').classList.remove('active');
                    document.getElementById('pad-scalper-btn').classList.remove('active');
                    document.getElementById('pad-standard').style.display = 'none';
                    document.getElementById('pad-scalper').style.display = 'none';
                    if (activePad === 'scalper') {
                        document.getElementById('pad-scalper-btn').classList.add('active');
                        document.getElementById('pad-scalper').style.display = 'flex';
                    } else {
                        document.getElementById('pad-std-btn').classList.add('active');
                        document.getElementById('pad-standard').style.display = 'flex';
                    }
                }
                if (settings.currentExchange) {
                    currentExchange = settings.currentExchange;
                }
                if (settings.currentIndex) {
                    currentIndex = settings.currentIndex;
                }
                if (settings.currentOptionType) {
                    currentOptionType = settings.currentOptionType;
                }
            } catch (e) {
                console.error("Failed to load local settings", e);
            }
        }

        // Initialize selectors
        setExchange('NSE');
        loadLocalSettings();
        setExchange(currentExchange);
        updateUIForConnectionState(false);
        updateTelemetry();

        // Bind input listeners to save configuration changes
        document.getElementById("sc-bracket-sl").addEventListener("input", saveLocalSettings);
        document.getElementById("sc-bracket-sl-type").addEventListener("change", saveLocalSettings);
        document.getElementById("sc-bracket-target").addEventListener("input", saveLocalSettings);
        document.getElementById("sc-bracket-target-type").addEventListener("change", saveLocalSettings);
    </script>
</body>
</html>
"""


@app.route('/manual')
def manual_trading():
    return render_template_string(HTML_MANUAL_DASHBOARD)

@app.route('/manual/buy', methods=['POST'])
def manual_buy():
    global SYSTEM_STATUS, current_feed, TRADE_LOGS
    if not current_feed or not current_feed.account:
        return jsonify({"error": "Trading Desk stream is not connected. Connect first."}), 400
        
    # Allow scale-in on same instrument; block only if a DIFFERENT instrument is open
    pos = SYSTEM_STATUS.get("position")
    req_data = request.get_json() or {}
    qty = int(req_data.get("qty", 1))
    target = float(req_data.get("target", 0.0))
    target_type = req_data.get("target_type", "points")
    stop_loss = float(req_data.get("stop_loss", 0.0))
    stop_loss_type = req_data.get("stop_loss_type", "points")
    trailing_gap = float(req_data.get("trailing_gap", 0.0))
    is_scalper = bool(req_data.get("is_scalper", False))
    
    if is_scalper:
        instrument_key = SYSTEM_STATUS.get("scalper_instrument_key", SYSTEM_STATUS["instrument_key"])
        lot_mult = SYSTEM_STATUS.get("scalper_lot_multiplier", SYSTEM_STATUS["lot_size_multiplier"])
        price = SYSTEM_STATUS.get("scalper_spot_price", 0.0)
    else:
        instrument_key = SYSTEM_STATUS["instrument_key"]
        lot_mult = SYSTEM_STATUS["lot_size_multiplier"]
        price = SYSTEM_STATUS["spot_price"]

    if pos and pos.get("instrument_key") and pos["instrument_key"] != instrument_key:
        return jsonify({"error": f"Already in a position for {pos['instrument_key']}. Exit first before buying a different instrument."}), 400
        
    if price <= 0.0:
        return jsonify({"error": f"LTP is not available yet for {instrument_key}. Wait for a tick."}), 400
        
    # Set lot size for this order (scale-in preserves cumulative qty in Account.buy)
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
        # Recalculate bracket exits using avg entry price (handles scale-in)
        avg_entry = current_feed.account.entry_price
        target_price = 0.0
        stop_loss_price = 0.0
        
        if target > 0.0:
            if target_type == "points":
                target_price = avg_entry + target
            elif target_type == "percent":
                target_price = avg_entry * (1.0 + target / 100.0)
            elif target_type == "atr":
                target_price = avg_entry + target  # target already computed as ATR * multiplier
                
        if stop_loss > 0.0:
            if stop_loss_type == "points":
                stop_loss_price = avg_entry - stop_loss
            elif stop_loss_type == "percent":
                stop_loss_price = avg_entry * (1.0 - stop_loss / 100.0)
            elif stop_loss_type == "atr":
                stop_loss_price = avg_entry - stop_loss  # sl already computed as ATR * multiplier
                
        if SYSTEM_STATUS["position"]:
            SYSTEM_STATUS["position"]["target_price"] = target_price
            SYSTEM_STATUS["position"]["stop_loss"] = stop_loss_price
            SYSTEM_STATUS["position"]["is_scalper"] = is_scalper
            SYSTEM_STATUS["position"]["trailing_gap"] = trailing_gap
            SYSTEM_STATUS["position"]["highest_price"] = price
            SYSTEM_STATUS["position"]["total_qty"] = current_feed.account.qty
            
        action = "scaled in" if pos else "opened"
        return jsonify({"message": f"BUY order executed ({action}). Avg: ₹{avg_entry:.2f} | Qty: {current_feed.account.qty}", "status": SYSTEM_STATUS})
    else:
        return jsonify({"error": "Manual BUY order failed (Check funds or no active stream)."}), 400

@app.route('/manual/sell', methods=['POST'])
def manual_sell():
    global SYSTEM_STATUS, current_feed, TRADE_LOGS
    if not current_feed or not current_feed.account or not current_feed.account.position:
        return jsonify({"error": "No active position to exit."}), 400
        
    pos = SYSTEM_STATUS["position"]
    instrument_key = pos["instrument_key"]
    is_scalper = pos.get("is_scalper", False)
    
    price = SYSTEM_STATUS["scalper_spot_price"] if is_scalper else SYSTEM_STATUS["spot_price"]
    if price <= 0.0:
        return jsonify({"error": "Spot price is not available yet."}), 400
        
    success = current_feed.account.sell(
        instrument_key=instrument_key,
        price=price,
        timestamp=datetime.now(),
        reason="MANUAL_EXIT",
        details="Manual exit from dashboard"
    )
    if success:
        return jsonify({"message": "Manual SELL/EXIT order executed.", "status": SYSTEM_STATUS})
    else:
        return jsonify({"error": "Manual SELL/EXIT order failed."}), 400

@app.route('/manual/panic_exit', methods=['POST'])
def manual_panic_exit():
    global SYSTEM_STATUS, current_feed, GTT_ORDERS
    
    # 1. Cancel all PENDING GTT orders
    cancelled_count = 0
    for order in GTT_ORDERS:
        if order.get("status") == "PENDING":
            order["status"] = "CANCELLED"
            cancelled_count += 1
            log_event(f"GTT Trigger Cancelled via Panic Exit: {order['id']}", "SYSTEM")
            
    # 2. Square off active position if it exists
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
    return jsonify({"message": msg, "status": SYSTEM_STATUS})

@app.route('/manual/gtt/create', methods=['POST'])
def manual_gtt_create():
    global GTT_ORDERS, SYSTEM_STATUS
    if not current_feed:
        return jsonify({"error": "Trading Desk stream is not connected."}), 400
        
    req_data = request.get_json() or {}
    try:
        trigger_price = float(req_data.get("trigger_price", 0.0))
        qty = int(req_data.get("qty", 1))
        side = req_data.get("side", "BUY").upper()
        order_type = req_data.get("order_type", "MARKET").upper()
        price = float(req_data.get("price", 0.0))
        
        target = float(req_data.get("target", 0.0))
        target_type = req_data.get("target_type", "points")
        stop_loss = float(req_data.get("stop_loss", 0.0))
        stop_loss_type = req_data.get("stop_loss_type", "points")
        trailing_gap = float(req_data.get("trailing_gap", 0.0))
        
        if trigger_price <= 0.0:
            return jsonify({"error": "Trigger price must be greater than 0."}), 400
            
        direction = req_data.get("direction")
        if not direction:
            current_price = SYSTEM_STATUS["spot_price"]
            if current_price <= 0.0:
                current_price = trigger_price # fallback
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
        return jsonify({"message": "GTT order created successfully.", "gtt_order": gtt_order})
    except Exception as e:
        return jsonify({"error": f"Failed to create GTT order: {e}"}), 400

@app.route('/manual/gtt/cancel', methods=['POST'])
def manual_gtt_cancel():
    global GTT_ORDERS
    req_data = request.get_json() or {}
    gtt_id = req_data.get("id")
    for order in GTT_ORDERS:
        if order["id"] == gtt_id and order["status"] == "PENDING":
            order["status"] = "CANCELLED"
            log_event(f"GTT Trigger Cancelled: {order['id']}", "SYSTEM")
            return jsonify({"message": "GTT order cancelled successfully."})
    return jsonify({"error": "GTT order not found or already triggered/cancelled."}), 404


@app.route('/paper')
def paper_trading():
    return render_template_string(HTML_PAPER_DASHBOARD)

@app.route('/')
def index():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/instruments')
def get_expiry_dates():
    sync_nifty_options_csv()
    exchange = request.args.get('exchange', 'NSE')
    index_name = request.args.get('index', 'NIFTY')
    segment = "NSE_FO" if exchange == "NSE" else "BSE_FO"
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    filtered = df[(df['segment'] == segment) & (df['name'] == index_name)]
    expiries = sorted(filtered['expiry_date'].dropna().unique())
    return jsonify(expiries)

@app.route('/api/strikes')
def get_strikes():
    expiry_str = request.args.get('expiry')
    option_type = request.args.get('type', 'CE')
    exchange = request.args.get('exchange', 'NSE')
    index_name = request.args.get('index', 'NIFTY')
    segment = "NSE_FO" if exchange == "NSE" else "BSE_FO"
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    filtered = df[
        (df['segment'] == segment) & 
        (df['name'] == index_name) & 
        (df['expiry_date'] == expiry_str) & 
        (df['instrument_type'] == option_type)
    ]
    strikes = sorted(filtered['strike_price'].dropna().unique())
    return jsonify(strikes)

@app.route('/api/atr')
def get_atr():
    global current_feed
    if not current_feed or not current_feed.candles_history:
        return jsonify({"atr": 1.0, "error": "No candles data available."})
        
    candles = list(current_feed.candles_history)
    period = int(request.args.get('period', 14))
    
    if len(candles) < 3:
        return jsonify({"atr": 1.0, "warning": "Too few candles."})
        
    # Calculate True Ranges
    trs = []
    for i in range(1, len(candles)):
        h = candles[i].get('high', candles[i].get('close', 0.0))
        l = candles[i].get('low', candles[i].get('close', 0.0))
        pc = candles[i-1].get('close', 0.0)
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
        
    if not trs:
        return jsonify({"atr": 1.0})
        
    if len(trs) < period:
        atr = sum(trs) / len(trs)
    else:
        atr = sum(trs[:period]) / period
        for i in range(period, len(trs)):
            atr = (atr * (period - 1) + trs[i]) / period
            
    return jsonify({"atr": round(atr, 2)})

@app.route('/api/options/metadata')
def get_options_metadata():
    exchange = request.args.get('exchange', 'NSE')
    index_name = request.args.get('index', 'NIFTY')
    
    sync_nifty_options_csv()
    if not os.path.exists(CSV_PATH):
        return jsonify({"error": "CSV file missing"}), 404
        
    df = pd.read_csv(CSV_PATH)
    segment = "NSE_FO" if exchange == "NSE" else "BSE_FO"
    
    sub_df = df[(df['segment'] == segment) & (df['name'] == index_name)].copy()
    if sub_df.empty:
        return jsonify({"expiries": [], "spot_price": 0.0, "atm_strike": 0.0, "strikes": []})
        
    sub_df['expiry_date'] = pd.to_datetime(sub_df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    expiries = sorted(sub_df['expiry_date'].dropna().unique())
    
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
    
    atm_strike = 0.0
    if spot_price > 0:
        step = 100
        if index_name in ["NIFTY", "MIDCPNIFTY"]:
            step = 50
        atm_strike = round(spot_price / step) * step
        
    strikes = sorted([float(x) for x in sub_df['strike_price'].dropna().unique()])
    
    return jsonify({
        "expiries": expiries,
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "strikes": strikes
    })

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
        
    candle_type = SYSTEM_STATUS.get("chart_type", "heikin_ashi")
    
    if candle_type == "heikin_ashi":
        try:
            df = pd.DataFrame(merged)
            ha_df = calculate_heikin_ashi(df)
            new_candles = []
            for idx, row in ha_df.iterrows():
                new_candles.append({
                    'time': get_unix_timestamp(row['timestamp']),
                    'open': round(float(row['open']), 2),
                    'high': round(float(row['high']), 2),
                    'low': round(float(row['low']), 2),
                    'close': round(float(row['close']), 2)
                })
            HEIKIN_ASHI_CANDLES = new_candles
        except Exception as e:
            log_event(f"Failed to calculate Heikin Ashi: {e}", "ERROR")
            HEIKIN_ASHI_CANDLES = []
    else:
        # Normal candles
        HEIKIN_ASHI_CANDLES = []
        for c in merged:
            HEIKIN_ASHI_CANDLES.append({
                'time': get_unix_timestamp(c['timestamp']),
                'open': round(float(c['open']), 2),
                'high': round(float(c['high']), 2),
                'low': round(float(c['low']), 2),
                'close': round(float(c['close']), 2)
            })

@app.route('/api/chart/config', methods=['POST'])
def set_chart_config():
    global current_feed, SYSTEM_STATUS, HEIKIN_ASHI_CANDLES
    req_data = request.get_json() or {}
    interval = req_data.get("interval", "1minute")
    candle_type = req_data.get("candle_type", "heikin_ashi")
    
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
            log_event(f"Chart interval updated to {interval}. Fetched {len(current_feed.candles_history)} historical candles.", "SYSTEM")
        except Exception as e:
            log_event(f"Failed to fetch historical candles for interval {interval}: {e}", "WARNING")
            
    return jsonify({"status": "success", "chart_interval": interval, "chart_type": candle_type})

LAST_NIFTY_SPOT_TIME = 0.0
CACHED_NIFTY_SPOT = 0.0

@app.route('/telemetry')
def get_telemetry():
    global LAST_NIFTY_SPOT_TIME, CACHED_NIFTY_SPOT, current_feed, active_thread
    
    # Active connection state validation
    if SYSTEM_STATUS.get("state") in ["LIVE_MONITORING", "PROCESSING"]:
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

    return jsonify({
        "status": SYSTEM_STATUS,
        "trades": TRADE_LOGS,
        "logs": EVENT_LOGS,
        "candles": HEIKIN_ASHI_CANDLES,
        "gtt_orders": GTT_ORDERS
    })

def handle_unified_target_update(req_data):
    global SYSTEM_STATUS, current_feed, running_loop
    expiry = req_data.get("expiry")
    option_type = req_data.get("option_type", "CE")
    strike = req_data.get("strike", "ATM")
    exchange = req_data.get("exchange", "NSE")
    index_name = req_data.get("index_name", req_data.get("index", "NIFTY"))
    
    if not expiry:
        return jsonify({"error": "Expiry selection is required."}), 400
        
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
        return jsonify({"error": f"Instrument lookup failed: {e}"}), 400
        
    # Update SYSTEM_STATUS (Unify standard & scalper targets)
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
    
    # If feed is active, dynamically subscribe to the new key
    if current_feed and running_loop:
        current_feed.instrument_key = standard_key
        current_feed.scalper_key = standard_key
        current_feed.candles_history = []
        current_feed.current_candle = None
        
        # Pre-populate candles for the new key
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=3)
            active_int = SYSTEM_STATUS.get("chart_interval", "1minute")
            hist = fetch_historical_candles(standard_key, '1minute', from_date, to_date)
            if active_int in ["5minute", "15minute"]:
                hist = resample_candles(hist, active_int)
            current_feed.candles_history = hist[-100:]
            
            rebuild_telemetry_candles()
            log_event(f"Dynamically pre-populated {len(HEIKIN_ASHI_CANDLES)} candles for standard target ({active_int}).", "SYSTEM")
        except Exception as e:
            log_event(f"Failed to pre-populate HA candles for new target: {e}", "WARNING")
            
        future = asyncio.run_coroutine_threadsafe(
            current_feed.subscribe_to_keys([standard_key]),
            running_loop
        )
        try:
            future.result(timeout=2.0)
        except Exception as e:
            log_event(f"Error subscribing dynamically to {standard_key}: {e}", "ERROR")
        log_event(f"Updated Target Option dynamically: {standard_symbol}", "SYSTEM")
        
    return jsonify({"message": f"Target updated to {standard_symbol}", "status": SYSTEM_STATUS})

@app.route('/api/scalper/update_target', methods=['POST'])
def update_scalper_target():
    req_data = request.get_json() or {}
    return handle_unified_target_update(req_data)

@app.route('/api/standard/update_target', methods=['POST'])
def update_standard_target():
    req_data = request.get_json() or {}
    return handle_unified_target_update(req_data)

@app.route('/start', methods=['POST'])
def start_engine():
    global SYSTEM_STATUS, TRADE_LOGS, EVENT_LOGS, EQUITY_CURVE, HEIKIN_ASHI_CANDLES, current_feed, current_strategy, active_thread, running_loop, CURRENT_SESSION_ID
    
    req_data = request.get_json() or {}
    mode = req_data.get("mode", "BACKTEST")
    lot_size = int(req_data.get("lot_size", 1))
    live_protection = bool(req_data.get("live_protection", False))
    expiry = req_data.get("expiry")
    option_type = req_data.get("option_type", "CE")
    strike = req_data.get("strike", "ATM")
    exchange = req_data.get("exchange", "NSE")
    index_name = req_data.get("index_name", req_data.get("index", "NIFTY"))
    
    scalper_expiry = req_data.get("scalper_expiry")
    scalper_option_type = req_data.get("scalper_option_type", "CE")
    scalper_strike = req_data.get("scalper_strike", "ATM")
    
    start_date_str = req_data.get("start_date")
    end_date_str = req_data.get("end_date")
    timeframe = req_data.get("timeframe", "1minute")
    max_candles = int(req_data.get("max_candles", 10))
    cutoff_time = req_data.get("cutoff_time", "15:15")
    brokerage_flat = float(req_data.get("brokerage_flat", 20.0))
    slippage_pct = float(req_data.get("slippage_pct", 0.05))
    initial_balance = float(req_data.get("initial_balance", 100000.0))
    
    # Strategy Configurations
    strategy_name = req_data.get("strategy", "heikin_ashi_gar")
    strategy_params = {}
    if strategy_name == "heikin_ashi_gar":
        strategy_params = {
            "candle_limit": int(max_candles),
            "cut_off_time": cutoff_time
        }
    elif strategy_name == "five_ema_scalping":
        strategy_params = {
            "ema_period": int(req_data.get("five_ema_period", 5)),
            "rr_ratio": float(req_data.get("five_ema_rr", 3.0)),
            "cut_off_time": cutoff_time
        }
        
    if not expiry:
        return jsonify({"error": "Expiry selection is required."}), 400
        
    period_type = req_data.get("period_type", "custom")
    start_date, end_date = parse_predefined_period(period_type, start_date_str, end_date_str)
        
    sync_nifty_options_csv()
    
    # Calculate ATM Strike dynamically if selected
    if strike == "ATM":
        log_event(f"Strike configured as dynamic ATM for {index_name}. Retrieving spot price...", "SYSTEM")
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
            log_event(f"Could not fetch spot price for {index_name}. Falling back to default strike 22000 CE", "WARNING")
            strike_price = 22000.0
        else:
            step = 100
            if index_name in ["NIFTY", "MIDCPNIFTY"]:
                step = 50
            strike_price = round(spot_price / step) * step
            log_event(f"{index_name} Spot Price: {spot_price} | Selected ATM Strike: {strike_price}", "SYSTEM")
    else:
        strike_price = float(strike)
        
    try:
        instrument_key, trading_symbol, lot_multiplier = get_instrument_details(index_name, strike_price, expiry, option_type)
    except Exception as e:
        return jsonify({"error": f"Instrument lookup failed: {e}"}), 400
        
    # Resolve Scalper Target Details
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
        return jsonify({"error": "Session is already active. Stop it first."}), 400
 
    # Reset system metrics and GTT orders
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
        return jsonify({"message": "Backtest session initialized.", "status": SYSTEM_STATUS})
        
    elif mode in ["PAPER", "LIVE", "MANUAL"]:
        # Initialize DB Session for Paper/Live
        CURRENT_SESSION_ID = db.create_session(mode, initial_balance)
        SYSTEM_STATUS["session_id"] = CURRENT_SESSION_ID
        
        # Paper trading or real execution on websocket
        is_live_selected = req_data.get("live_trading", False)
        account_is_real = (mode == "LIVE" or (mode == "MANUAL" and is_live_selected)) and live_protection
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
                log_event(f"WebSocket session disconnected with exception: {e}", "ERROR")
            finally:
                SYSTEM_STATUS["state"] = "DISCONNECTED"
                
        active_thread = threading.Thread(target=run_websocket_loop, daemon=True)
        active_thread.start()
        
        SYSTEM_STATUS["state"] = "LIVE_MONITORING"
        return jsonify({"message": f"{mode} session engine initialized.", "status": SYSTEM_STATUS})
        
    return jsonify({"error": "Unsupported execution mode."}), 400

@app.route('/stop', methods=['POST'])
def stop_engine():
    global current_feed, running_loop, active_thread, SYSTEM_STATUS, CURRENT_SESSION_ID
    log_event("Shutdown instruction received. Stopping session engine...", "SYSTEM")
    
    if current_feed:
        current_feed.stop()
        current_feed = None
        
    if running_loop:
        try:
            running_loop.call_soon_threadsafe(running_loop.stop)
        except Exception:
            pass
        running_loop = None
        
    if CURRENT_SESSION_ID:
        db.close_session(CURRENT_SESSION_ID, SYSTEM_STATUS["balance"])
        CURRENT_SESSION_ID = None
        
    SYSTEM_STATUS["state"] = "IDLE"
    return jsonify({"message": "Session engine successfully halted.", "status": SYSTEM_STATUS})

def resume_active_session_if_any():
    global CURRENT_SESSION_ID, SYSTEM_STATUS, TRADE_LOGS, EQUITY_CURVE, current_strategy, current_feed, active_thread, running_loop
    active_session = db.get_active_session()
    if active_session:
        session_id = active_session["id"]
        db.close_session(session_id, active_session["initial_balance"])
        log_event(f"Halted previous active session {session_id} on startup.", "SYSTEM")
    SYSTEM_STATUS["state"] = "IDLE"

if __name__ == '__main__':
    sync_nifty_options_csv()
    resume_active_session_if_any()
    app.run(host='0.0.0.0', port=8081, debug=True)
