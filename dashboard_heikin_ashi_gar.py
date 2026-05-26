import os
import json
import threading
import time
import asyncio
from datetime import datetime, timedelta
import requests
import pandas as pd
import numpy as np
import websockets
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import MarketDataFeed_pb2 as pb
from strategy_heikin_ashi_gar import HeikinAshiGarStrategy, calculate_heikin_ashi

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
    "live_protection": False,
    "lot_size": 1,
    "spot_price": 0.0,
    "total_pnl": 0.0,
    "return_percent": 0.0,
    "max_drawdown": 0.0,
    "profit_factor": 0.0,
    "total_trades": 0,
    "win_rate": 0.0
}

TRADE_LOGS = []
EVENT_LOGS = []
EQUITY_CURVE = []

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
            if df.empty or 'expiry' not in df.columns:
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
            nifty_options = df.loc[
                (df['segment'] == 'NSE_FO') & 
                (df['instrument_type'].isin(['CE', 'PE'])) &
                (df['name'] == 'NIFTY')
            ].copy()
            nifty_options.to_csv(CSV_PATH, index=False)
            log_event(f"Successfully saved {len(nifty_options)} active options to nifty_options.csv", "SYSTEM")
        except Exception as e:
            log_event(f"Failed to synchronize instruments: {e}", "ERROR")

# -------------------------------
# Upstox API Quotes Helper
# -------------------------------
def get_nifty_spot_price():
    token = load_upstox_token()
    if not token:
        return 0.0
    url = "https://api.upstox.com/v2/market-quote/ltp?instrument_key=NSE_INDEX%7CNifty%2050"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get("data", {}).get("NSE_INDEX|Nifty 50", {}).get("last_price", 0.0)
            return float(price)
    except Exception as e:
        log_event(f"Error fetching NIFTY spot price: {e}", "ERROR")
    return 0.0

def get_instrument_details(strike, expiry_str, option_type):
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    mask = (df['strike_price'] == float(strike)) & (df['expiry_date'] == expiry_str) & (df['instrument_type'] == option_type)
    matches = df[mask]
    if matches.empty:
        raise ValueError(f"No contract matching strike {strike}, expiry {expiry_str}, type {option_type}")
    return matches.iloc[0]['instrument_key'], matches.iloc[0]['trading_symbol']

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
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
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
    global SYSTEM_STATUS
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
    def __init__(self, initial_balance=100000.0, is_real=False, lot_size=1, brokerage_flat=20.0, slippage_pct=0.05):
        self.is_real = is_real
        self.lot_size = lot_size
        self.qty = lot_size * 75
        self.position = None
        self.entry_price = 0.0
        self.brokerage_flat = brokerage_flat
        self.slippage_pct = slippage_pct
        self.buy_cost = 0.0
        
    def buy(self, instrument_key, price, timestamp):
        if self.position:
            return False
            
        self.position = instrument_key
        self.entry_price = price
        self.buy_cost = self.brokerage_flat + (price * (self.slippage_pct / 100.0) * self.qty)
        SYSTEM_STATUS["balance"] -= self.buy_cost
        
        SYSTEM_STATUS["position"] = {
            "instrument_key": instrument_key,
            "entry_price": price,
            "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        }
        
        TRADE_LOGS.append({
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, 'strftime') else str(timestamp),
            "type": "BUY",
            "price": price,
            "sl": SYSTEM_STATUS["position"].get("stop_loss", 0.0),
            "reason": "SIGNAL_TRIGGER"
        })
        log_event(f"Position opened. BUY {self.qty} @ ₹{price:.2f} | Cost: ₹{self.buy_cost:.2f}", "TRADE")
        
        # Real Execution Call
        if self.is_real:
            execute_order(instrument_key, self.qty, "BUY")
        return True

    def sell(self, instrument_key, price, timestamp, reason):
        if not self.position or self.position != instrument_key:
            return False
            
        sell_cost = self.brokerage_flat + (price * (self.slippage_pct / 100.0) * self.qty)
        SYSTEM_STATUS["balance"] -= sell_cost
        
        gross_pnl = (price - self.entry_price) * self.qty
        SYSTEM_STATUS["balance"] += gross_pnl
        net_pnl = gross_pnl - (self.buy_cost + sell_cost)
        
        TRADE_LOGS.append({
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(timestamp, 'strftime') else str(timestamp),
            "type": "EXIT",
            "price": price,
            "reason": reason,
            "pnl": net_pnl
        })
        log_event(f"Position closed. SELL {self.qty} @ ₹{price:.2f} | Net P&L: ₹{net_pnl:.2f} (Gross: ₹{gross_pnl:.2f}, Cost: ₹{self.buy_cost + sell_cost:.2f}) | Reason: {reason}", "TRADE")
        
        # Real Execution Call
        if self.is_real:
            execute_order(instrument_key, self.qty, "SELL")
            
        self.position = None
        self.entry_price = 0.0
        SYSTEM_STATUS["position"] = None
        
        EQUITY_CURVE.append({
            "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
            "equity": SYSTEM_STATUS["balance"]
        })
        update_telemetry_metrics()
        return True

# -------------------------------
# WebSocket Market Data Client
# -------------------------------
class LiveFeed:
    def __init__(self, instrument_key, strategy_engine, account):
        self.instrument_key = instrument_key
        self.strategy = strategy_engine
        self.account = account
        self.current_candle = None
        self.candles_history = []
        self.running = True

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
            subscribe_msg = {
                "guid": "valkyrie_heikin_ashi_gar",
                "method": "sub",
                "data": {"mode": "full", "instrumentKeys": [self.instrument_key]}
            }
            await ws.send(json.dumps(subscribe_msg))
            log_event(f"Subscribed to market feed for: {self.instrument_key}", "WS")
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

    async def process_message(self, raw_message):
        try:
            feed = pb.FeedResponse()
            feed.ParseFromString(raw_message)
            for key, feed_data in feed.feeds.items():
                price = None
                if feed_data.ff:
                    ltp_data = pb.LtpMarketData()
                    ltp_data.ParseFromString(feed_data.ff.value)
                    price = ltp_data.ltp / 100.0
                elif feed_data.index_ff:
                    index_data = pb.IndexMarketData()
                    index_data.ParseFromString(feed_data.index_ff.value)
                    price = index_data.indicies.ttq / 100.0
                    
                if price:
                    SYSTEM_STATUS["spot_price"] = price
                    self.on_tick(price, datetime.now())
        except Exception as e:
            log_event(f"Protobuf processing error: {e}", "ERROR")

    def on_tick(self, price, timestamp):
        current_minute = timestamp.replace(second=0, microsecond=0)
        
        # Live trailing price exit check
        if self.account.position:
            if price <= self.strategy.stop_loss_level:
                self.account.sell(self.instrument_key, price, timestamp, "STOP_LOSS")
                self.strategy.reset_state()
            
        if self.current_candle is None or self.current_candle['timestamp'] != current_minute:
            if self.current_candle is not None:
                self.on_candle_close(self.current_candle)
            self.current_candle = {
                'timestamp': current_minute,
                'open': price,
                'high': price,
                'low': price,
                'close': price
            }
        else:
            self.current_candle['high'] = max(self.current_candle['high'], price)
            self.current_candle['low'] = min(self.current_candle['low'], price)
            self.current_candle['close'] = price

    def on_candle_close(self, candle):
        self.candles_history.append(candle)
        log_event(f"1-min candle closed: {candle['timestamp'].strftime('%H:%M:%S')} | O: {candle['open']} H: {candle['high']} L: {candle['low']} C: {candle['close']}", "ENGINE")
        
        if len(self.candles_history) < 3:
            return
            
        df = pd.DataFrame(self.candles_history)
        signal, meta = self.strategy.evaluate(df)
        
        if signal == "BUY":
            self.account.buy(self.instrument_key, candle['close'], candle['timestamp'])
            self.strategy.stop_loss_level = meta["stop_loss"]
        elif signal == "EXIT":
            self.account.sell(self.instrument_key, candle['close'], candle['timestamp'], meta.get("reason", "TECHNICAL_REVERSAL"))

    def stop(self):
        self.running = False

# -------------------------------
# Historical backtest fetcher & runner
# -------------------------------
def fetch_historical_candles(instrument_key, interval, from_date, to_date):
    token = load_upstox_token()
    if not token:
        raise Exception("Access token missing in token.txt")
    url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/{interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
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

def run_historical_backtest(instrument_key, lot_size, start_date, end_date, timeframe, max_candles, cutoff_time, brokerage_flat, slippage_pct):
    global TRADE_LOGS, EQUITY_CURVE
    log_event("Historical backtest sequence started...", "BACKTEST")
    
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
    
    backtest_account = EngineAccount(initial_balance=100000.0, is_real=False, lot_size=lot_size, brokerage_flat=brokerage_flat, slippage_pct=slippage_pct)
    backtest_strategy = HeikinAshiGarStrategy(candle_limit=max_candles, cut_off_time=cutoff_time)
    
    for i in range(2, len(raw_df)):
        current_tick = raw_df.iloc[i]
        candle_completed = ha_df.iloc[i-1]
        candle_prior = ha_df.iloc[i-2]
        
        tick_time_str = str(current_tick['timestamp']).split()[-1][:5]
        current_time = datetime.strptime(tick_time_str, "%H:%M").time()
        
        if backtest_strategy.is_holding:
            backtest_strategy.candles_held += 1
            if current_tick['low'] <= backtest_strategy.stop_loss_level:
                backtest_account.sell(instrument_key, backtest_strategy.stop_loss_level, current_tick['timestamp'], "STOP_LOSS")
                backtest_strategy.reset_state()
            elif current_time >= backtest_strategy.cut_off_time:
                backtest_account.sell(instrument_key, current_tick['close'], current_tick['timestamp'], "SESSION_END")
                backtest_strategy.reset_state()
            elif backtest_strategy.candles_held >= backtest_strategy.candle_limit:
                backtest_account.sell(instrument_key, current_tick['close'], current_tick['timestamp'], "MAX_DURATION")
                backtest_strategy.reset_state()
            elif candle_completed['close'] < candle_completed['open']:
                backtest_account.sell(instrument_key, current_tick['close'], current_tick['timestamp'], "TECHNICAL_REVERSAL")
                backtest_strategy.reset_state()
        else:
            prior_is_red = candle_prior['close'] < candle_prior['open']
            completed_is_green = candle_completed['close'] > candle_completed['open']
            is_strong_green = abs(candle_completed['open'] - candle_completed['low']) <= 0.05
            
            if current_time >= backtest_strategy.cut_off_time:
                continue
                
            if prior_is_red and completed_is_green and is_strong_green:
                backtest_strategy.is_holding = True
                backtest_strategy.entry_price = current_tick['close']
                backtest_strategy.stop_loss_level = raw_df.iloc[i-2]['open'] # raw open of prior candle
                backtest_strategy.candles_held = 0
                backtest_strategy.entry_timestamp = current_tick['timestamp']
                
                backtest_account.buy(instrument_key, current_tick['close'], current_tick['timestamp'])
                
    log_event("Historical backtest sequence execution complete.", "BACKTEST")

# -------------------------------
# Dashboard HTML Page Template
# -------------------------------
HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Valkyrie HEIKIN-ASHI GAR Command Room</title>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
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
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Valkyrie HEIKIN-ASHI GAR Control Room</h1>
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
                <div class="card">
                    <h2>Performance Equity Curve</h2>
                    <div id="chart"></div>
                </div>
                <div class="card">
                    <h2>Live Trade Registry</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Type</th>
                                <th>Fill Price</th>
                                <th>Stop Loss</th>
                                <th>Outcome/Reason</th>
                            </tr>
                        </thead>
                        <tbody id="trade-rows">
                            <tr><td colspan="5" style="text-align:center; color: var(--text-mute);">No trades executed in this active engine instance.</td></tr>
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
                        <h3 style="font-size: 13px; text-transform: uppercase; color: var(--gold-accent); margin-bottom: 12px; letter-spacing: 0.5px;">Backtest &amp; Tuner Config</h3>
                        <div class="control-row">
                            <div class="control-item">
                                <label>Start Date</label>
                                <input type="date" id="start-date">
                            </div>
                            <div class="control-item">
                                <label>End Date</label>
                                <input type="date" id="end-date">
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
                                <label>Max Hold (Candles)</label>
                                <input type="number" id="max-candles" value="10" min="1">
                            </div>
                        </div>

                        <div class="control-row">
                            <div class="control-item">
                                <label>Cutoff Time</label>
                                <input type="text" id="cutoff-time" value="15:15" placeholder="HH:MM">
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
                height: 320, 
                background: 'transparent',
                toolbar: { show: false } 
            },
            colors: ['#66fcf1'],
            dataLabels: { enabled: false },
            stroke: { curve: 'smooth', width: 2 },
            grid: { borderColor: 'rgba(255,255,255,0.05)' },
            theme: { mode: 'dark' },
            xaxis: { labels: { style: { colors: '#94a3b8' } } },
            yaxis: { labels: { style: { colors: '#94a3b8' } } }
        };
        let chart = new ApexCharts(document.querySelector("#chart"), chartOptions);
        chart.render();

        let isRunning = false;

        // Set default dates
        const today = new Date();
        const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        document.getElementById("start-date").value = lastWeek.toISOString().split('T')[0];
        document.getElementById("end-date").value = today.toISOString().split('T')[0];

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
                        slippage_pct: slippage_pct
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

                // Update trade registry
                if(data.trades.length > 0) {
                    let html = '';
                    data.trades.forEach(t => {
                        html += `<tr>
                            <td>${t.timestamp}</td>
                            <td><span style="color:${t.type=='BUY'?'#2ec4b6':'#ff4d4d'}; font-weight: 700;">${t.type}</span></td>
                            <td>₹${t.price.toFixed(2)}</td>
                            <td>${t.sl ? '₹'+t.sl.toFixed(2) : '-'}</td>
                            <td><span style="color:${t.reason=='STOP_LOSS'?'#ff4d4d':'#fff'}; font-weight: 500;">${t.reason}</span></td>
                        </tr>`;
                    });
                    document.getElementById("trade-rows").innerHTML = html;
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
                let balancePoints = [100000];
                let currentVal = 100000;
                data.trades.forEach(t => {
                    if (t.type === 'EXIT') {
                        currentVal += (t.pnl || 0);
                        balancePoints.push(currentVal);
                    }
                });
                chart.updateSeries([{ name: 'Account Balance', data: balancePoints }]);

                if (data.status.state === "COMPLETED" || data.status.state === "FAILED" || data.status.state === "DISCONNECTED" || data.status.state === "IDLE") {
                    isRunning = false;
                    const btn = document.getElementById("start-btn");
                    btn.innerText = "Initialize Engine Session";
                    btn.className = "btn";
                }

                if(isRunning) {
                    setTimeout(updateTelemetry, 2000);
                }
            });
        }
    </script>
</body>
</html>
"""

# -------------------------------
# Routes
# -------------------------------
@app.route('/')
def index():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/instruments')
def get_expiry_dates():
    sync_nifty_options_csv()
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    expiries = sorted(df['expiry_date'].dropna().unique())
    return jsonify(expiries)

@app.route('/api/strikes')
def get_strikes():
    expiry_str = request.args.get('expiry')
    option_type = request.args.get('type')
    df = pd.read_csv(CSV_PATH)
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    filtered = df[(df['expiry_date'] == expiry_str) & (df['instrument_type'] == option_type)]
    strikes = sorted(filtered['strike_price'].dropna().unique())
    return jsonify(strikes)

@app.route('/telemetry')
def get_telemetry():
    return jsonify({
        "status": SYSTEM_STATUS,
        "trades": TRADE_LOGS,
        "logs": EVENT_LOGS
    })

@app.route('/start', methods=['POST'])
def start_engine():
    global SYSTEM_STATUS, TRADE_LOGS, EVENT_LOGS, EQUITY_CURVE, current_feed, current_strategy, active_thread, running_loop
    
    req_data = request.get_json() or {}
    mode = req_data.get("mode", "BACKTEST")
    lot_size = int(req_data.get("lot_size", 1))
    live_protection = bool(req_data.get("live_protection", False))
    expiry = req_data.get("expiry")
    option_type = req_data.get("option_type", "CE")
    strike = req_data.get("strike", "ATM")
    
    start_date_str = req_data.get("start_date")
    end_date_str = req_data.get("end_date")
    timeframe = req_data.get("timeframe", "1minute")
    max_candles = int(req_data.get("max_candles", 10))
    cutoff_time = req_data.get("cutoff_time", "15:15")
    brokerage_flat = float(req_data.get("brokerage_flat", 20.0))
    slippage_pct = float(req_data.get("slippage_pct", 0.05))
    
    if not expiry:
        return jsonify({"error": "Expiry selection is required."}), 400
        
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    else:
        start_date = datetime.now() - timedelta(days=7)
        
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        end_date = end_date.replace(hour=23, minute=59, second=59)
    else:
        end_date = datetime.now()
        
    sync_nifty_options_csv()
    
    # Calculate ATM Strike dynamically if selected
    if strike == "ATM":
        log_event("Strike configured as dynamic ATM. Retrieving spot price...", "SYSTEM")
        spot_price = get_nifty_spot_price()
        if spot_price == 0.0:
            log_event("Could not fetch NIFTY spot price. Falling back to default strike 22000 CE", "WARNING")
            strike_price = 22000.0
        else:
            strike_price = round(spot_price / 50.0) * 50
            log_event(f"NIFTY Spot Price: {spot_price} | Selected ATM Strike: {strike_price}", "SYSTEM")
    else:
        strike_price = float(strike)
        
    try:
        instrument_key, trading_symbol = get_instrument_details(strike_price, expiry, option_type)
    except Exception as e:
        return jsonify({"error": f"Instrument lookup failed: {e}"}), 400
        
    if SYSTEM_STATUS["state"] in ["PROCESSING", "LIVE_MONITORING", "RUNNING_BACKTEST"]:
        return jsonify({"error": "Session is already active. Stop it first."}), 400

    # Reset system metrics
    TRADE_LOGS = []
    EVENT_LOGS = []
    EQUITY_CURVE = [{"timestamp": datetime.now().isoformat(), "equity": 100000.0}]
    
    SYSTEM_STATUS.update({
        "state": "PROCESSING",
        "mode": mode,
        "balance": 100000.0,
        "initial_balance": 100000.0,
        "position": None,
        "instrument_key": instrument_key,
        "trading_symbol": trading_symbol,
        "strike": strike_price,
        "expiry": expiry,
        "option_type": option_type,
        "live_protection": live_protection,
        "lot_size": lot_size,
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
                    slippage_pct
                )
                SYSTEM_STATUS["state"] = "COMPLETED"
            except Exception as e:
                log_event(f"Backtest execution failed: {e}", "ERROR")
                SYSTEM_STATUS["state"] = "FAILED"
        active_thread = threading.Thread(target=run_backtest_thread, daemon=True)
        active_thread.start()
        return jsonify({"message": "Backtest session initialized.", "status": SYSTEM_STATUS})
        
    elif mode in ["PAPER", "LIVE"]:
        # Paper trading or real execution on websocket
        account_is_real = (mode == "LIVE" and live_protection)
        log_event(f"Starting {mode} session engine. Real Execution active: {account_is_real}", "SYSTEM")
        
        current_strategy = HeikinAshiGarStrategy(candle_limit=max_candles, cut_off_time=cutoff_time)
        engine_account = EngineAccount(
            initial_balance=100000.0, 
            is_real=account_is_real, 
            lot_size=lot_size, 
            brokerage_flat=brokerage_flat, 
            slippage_pct=slippage_pct
        )
        current_feed = LiveFeed(instrument_key, current_strategy, engine_account)
        
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
    global current_feed, running_loop, active_thread, SYSTEM_STATUS
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
        
    SYSTEM_STATUS["state"] = "IDLE"
    return jsonify({"message": "Session engine successfully halted.", "status": SYSTEM_STATUS})

# -------------------------------
# Application Main Entry Point
# -------------------------------
if __name__ == '__main__':
    sync_nifty_options_csv()
    app.run(host='0.0.0.0', port=8081, debug=True)
