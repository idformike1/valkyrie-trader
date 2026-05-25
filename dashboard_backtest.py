import json
import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from flask import Flask, render_template_string, jsonify, request, Response
from flask_cors import CORS
import os
import asyncio
import websockets
import MarketDataFeed_pb2 as pb

# -------------------------------
# Load access token
# -------------------------------
TOKEN_FILE = "token.txt"
ACCESS_TOKEN = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        ACCESS_TOKEN = f.read().strip()

# -------------------------------
# Helper: Lookup instrument_key from CSV
# -------------------------------
def get_instrument_key_from_csv(strike, expiry_str, option_type):
    df = pd.read_csv('nifty_options.csv')
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    mask = (df['strike_price'] == float(strike)) & (df['expiry_date'] == expiry_str) & (df['instrument_type'] == option_type)
    matches = df[mask]
    if matches.empty:
        raise ValueError(f"No instrument found for strike {strike}, expiry {expiry_str}, type {option_type}")
    return matches.iloc[0]['instrument_key']

# -------------------------------
# Resample candles (fixed)
# -------------------------------
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

# -------------------------------
# Paper Trading Account
# -------------------------------
class PaperAccount:
    def __init__(self, initial_balance=100000):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions = {}
        self.trades = []
        self.daily_pnl = 0
        self.daily_loss_limit = 20000
        self.kill_switch_triggered = False
        self.trade_callbacks = []
        self.equity_curve = []

    def register_trade_callback(self, cb):
        self.trade_callbacks.append(cb)

    def _notify_trade(self, trade):
        for cb in self.trade_callbacks:
            cb(trade)

    def _update_equity(self, timestamp):
        cumulative = sum(t['pnl'] for t in self.trades)
        self.equity_curve.append({'timestamp': timestamp.isoformat(), 'equity': cumulative})

    def place_buy_order(self, instrument_key, price, qty=75, timestamp=None):
        if self.kill_switch_triggered or instrument_key in self.positions:
            return False
        cost = price * qty
        print(f"BUY: qty={qty}, price={price}, cost={cost}, balance before={self.balance}")
        if cost > self.balance:
            return False
        self.balance -= cost
        self.positions[instrument_key] = {'qty': qty, 'entry_price': price, 'entry_time': timestamp}
        self._notify_trade({'action': 'BUY', 'price': price, 'timestamp': timestamp.isoformat() if timestamp else None})
        return True

    def place_sell_order(self, instrument_key, price, qty=75, timestamp=None, reason=""):
        if self.kill_switch_triggered:
            return False
        if instrument_key not in self.positions:
            return False
        pos = self.positions.pop(instrument_key)
        proceeds = price * qty
        self.balance += proceeds
        pnl = (price - pos['entry_price']) * qty
        print(f"DEBUG: pnl = {pnl} (price {price} - entry {pos['entry_price']}) * {qty}")
        self.daily_pnl += pnl
        print(f"DEBUG: daily_pnl updated to {self.daily_pnl}")
        trade = {
            'entry_time': pos['entry_time'].strftime('%H:%M:%S') if pos['entry_time'] else '',
            'exit_time': timestamp.strftime('%H:%M:%S') if timestamp else '',
            'entry_price': pos['entry_price'],
            'exit_price': price,
            'pnl': pnl,
            'reason': reason
        }
        self.trades.append(trade)
        self._update_equity(timestamp)
        self._notify_trade({'action': 'SELL', 'price': price, 'timestamp': timestamp.isoformat() if timestamp else None, 'reason': reason})
        if self.daily_pnl <= -self.daily_loss_limit:
            self.kill_switch_triggered = True
        return True

    def get_status(self):
        serializable_trades = []
        for t in self.trades[-20:]:
            serializable_trades.append({
                "entry_time": t["entry_time"],
                "exit_time": t["exit_time"],
                "entry_price": t["entry_price"],
                "exit_price": t["exit_price"],
                "pnl": t["pnl"],
                "reason": t["reason"]
            })
        open_positions_serializable = {}
        for k, v in self.positions.items():
            open_positions_serializable[k] = {
                "qty": v["qty"],
                "entry_price": v["entry_price"],
                "entry_time": v["entry_time"].isoformat() if v["entry_time"] else None
            }
        
        # Calculate metrics
        total_pnl = sum(t['pnl'] for t in self.trades)
        percent_return = (total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0.0
        
        # Max drawdown
        peak = self.initial_balance
        max_dd = 0.0
        for pt in self.equity_curve:
            current_equity = self.initial_balance + pt['equity']
            if current_equity > peak:
                peak = current_equity
            dd = peak - current_equity
            if dd > max_dd:
                max_dd = dd
                
        total_trades = len(self.trades)
        profitable_count = sum(1 for t in self.trades if t['pnl'] > 0)
        profitable_pct = (profitable_count / total_trades * 100) if total_trades > 0 else 0.0
        
        gains = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        profit_factor = (gains / losses) if losses > 0 else (gains if gains > 0 else 0.0)

        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': open_positions_serializable,
            'kill_switch': self.kill_switch_triggered,
            'trades': serializable_trades,
            'equity_curve': self.equity_curve[-100:],
            'total_pnl': total_pnl,
            'return_percent': percent_return,
            'max_drawdown': max_dd,
            'profit_factor': profit_factor,
            'total_trades': total_trades,
            'win_rate': profitable_pct
        }

# -------------------------------
# Heikin-Ashi Strategy (fixed)
# -------------------------------
def calculate_heikin_ashi(candles_df):
    ha = pd.DataFrame(index=candles_df.index)
    ha['close'] = (candles_df['open'] + candles_df['high'] + candles_df['low'] + candles_df['close']) / 4.0
    ha_open = np.zeros(len(candles_df))
    ha_open[0] = candles_df['open'].iloc[0]
    for i in range(1, len(candles_df)):
        ha_open[i] = (ha_open[i-1] + ha['close'].iloc[i-1]) / 2.0
    ha['open'] = ha_open
    ha['high'] = pd.concat([candles_df['high'], ha['open'], ha['close']], axis=1).max(axis=1)
    ha['low'] = pd.concat([candles_df['low'], ha['open'], ha['close']], axis=1).min(axis=1)
    return ha[['open', 'high', 'low', 'close']]

class HeikinAshiStrategy:
    def __init__(self, account, instrument_key):
        self.account = account
        self.instrument_key = instrument_key
        self.candles = []
        self.in_position = False
        self.entry_price = None
        self.entry_candle_time = None
        self.candle_callback = None
        self.pending_entry = False
        self.pending_entry_time = None

    def set_candle_callback(self, cb):
        self.candle_callback = cb

    def on_candle_close(self, candle):
        self.candles.append(candle)
        if self.candle_callback:
            self.candle_callback(candle)
        if len(self.candles) < 2:
            return
        df = pd.DataFrame(self.candles[-10:])
        ha = calculate_heikin_ashi(df)
        current_green = ha['close'].iloc[-1] >= ha['open'].iloc[-1]
        prev_green = ha['close'].iloc[-2] >= ha['open'].iloc[-2]

        print(f"Candle at {candle['timestamp']}: in_position={self.in_position}, current_green={current_green}, prev_green={prev_green}")
        if self.in_position:
            print(f"  exit checks: low={candle['low']} <= entry_price={self.entry_price} ? {candle['low'] <= self.entry_price}, not current_green={not current_green}, session_end={candle['timestamp'].time() >= datetime.strptime('14:00', '%H:%M').time()}")

        # Entry signal: previous red, current green, no open position
        if not self.in_position and (not prev_green) and current_green:
            self.pending_entry = True
            self.pending_entry_time = candle['timestamp']   # time of signal candle

        if self.pending_entry and not self.in_position:
            # Ensure we do not execute on the signal candle itself
            if candle['timestamp'] > self.pending_entry_time:
                # Execute buy at the open of the current candle (which is the next candle after signal)
                entry_price = candle['open']
                success = self.account.place_buy_order(self.instrument_key, entry_price, timestamp=candle['timestamp'])
                if success:
                    self.in_position = True
                    self.entry_price = entry_price
                    self.entry_candle_time = candle['timestamp']
                    self.pending_entry = False
                    print(f"Position opened at {candle['timestamp']} price {entry_price}")

        # Exit conditions if in position
        elif self.in_position:
            # Prevent exit on the same candle as entry
            if candle['timestamp'] <= self.entry_candle_time:
                return
            print(f"Checking exit: low={candle['low']} <= entry={self.entry_price}? {candle['low'] <= self.entry_price}, current_green={current_green}, time={candle['timestamp'].time()}")
            
            # Forced exit after 10 candles
            entry_idx = next((i for i, c in enumerate(self.candles) if c['timestamp'] == self.entry_candle_time), -1)
            if entry_idx != -1 and (len(self.candles) - entry_idx > 10):
                self.account.place_sell_order(self.instrument_key, candle['close'], timestamp=candle['timestamp'], reason="Max candles")
                self.in_position = False
                self.entry_price = None
                self.entry_candle_time = None
                return

            if candle['low'] <= self.entry_price:
                exit_reason = "Breakeven"
                exit_price = self.entry_price
                self.account.place_sell_order(self.instrument_key, exit_price, timestamp=candle['timestamp'], reason=exit_reason)
                self.in_position = False
                self.entry_price = None
                self.entry_candle_time = None
            else:
                exit_reason = None
                if not current_green:
                    exit_reason = "Red Signal"
                elif candle['timestamp'].time() >= datetime.strptime("14:00", "%H:%M").time():
                    exit_reason = "Session End"
                if exit_reason:
                    self.account.place_sell_order(self.instrument_key, candle['close'], timestamp=candle['timestamp'], reason=exit_reason)
                    self.in_position = False
                    self.entry_price = None
                    self.entry_candle_time = None

# -------------------------------
# Historical data fetcher
# -------------------------------
def fetch_historical_candles(instrument_key, interval, from_date, to_date):
    if not ACCESS_TOKEN:
        raise Exception("No access token. Run auth.py first.")
    url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/{interval}/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text}")
    data = response.json()
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

def run_backtest(strategy, candles, replay_speed=0.03):
    print(f"Backtest replay: {len(candles)} candles")
    for candle in candles:
        strategy.on_candle_close(candle)
        time.sleep(replay_speed)
    print("Backtest finished")

class LiveFeed:
    def __init__(self, instrument_key, strategy):
        self.instrument_key = instrument_key
        self.strategy = strategy
        self.current_candle = None
        self.running = True

    async def get_websocket_uri(self):
        url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {ACCESS_TOKEN}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data['data']['authorizedRedirectUri'] or data['data']['authorized_redirect_uri']

    async def connect(self):
        uri = await self.get_websocket_uri()
        print(f"Connecting to {uri}")
        async with websockets.connect(uri, max_size=2**25) as ws:
            subscribe_msg = {
                "guid": "valkyrie_paper",
                "method": "sub",
                "data": {"mode": "full", "instrumentKeys": [self.instrument_key]}
            }
            await ws.send(json.dumps(subscribe_msg))
            print(f"Subscribed to {self.instrument_key}")
            while self.running:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    await self.process_message(message)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("WebSocket closed, reconnecting...")
                    break

    async def process_message(self, raw_message):
        try:
            feed = pb.FeedResponse()
            feed.ParseFromString(raw_message)
            for feed_data in feed.feeds.values():
                if feed_data.index_ff:
                    index_data = pb.IndexMarketData()
                    index_data.ParseFromString(feed_data.index_ff.value)
                    price = None
                    if hasattr(index_data, 'ltpc'):
                        price = index_data.ltpc / 100.0
                    elif hasattr(index_data, 'indicies') and hasattr(index_data.indicies, 'ttq'):
                        price = index_data.indicies.ttq / 100.0
                    if price:
                        now = datetime.now()
                        self.on_tick(price, now)
        except Exception as e:
            print(f"Protobuf error: {e}")

    def on_tick(self, price, timestamp):
        current_minute = timestamp.replace(second=0, microsecond=0)
        if self.current_candle is None or self.current_candle['timestamp'] != current_minute:
            if self.current_candle is not None:
                self.strategy.on_candle_close(self.current_candle)
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

    def stop(self):
        self.running = False

# -------------------------------
# Flask App – Backtest Dashboard
# -------------------------------
app = Flask(__name__)
CORS(app)

current_strategy = None
current_account = None
backtest_thread = None
active_mode = None
current_feed = None

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Valkyrie Trader – Backtest</title>
    <style>
        * { box-sizing: border-box; }
        body { background: #131722; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; color: #fff; }
        .container { max-width: 1600px; margin: 0 auto; }
        .controls { background: #1e222d; border: 1px solid #2a2e39; padding: 12px; border-radius: 6px; margin-bottom: 20px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        select, input, button { background: #2a2e39; border: 1px solid #363c4e; color: #d1d4dc; padding: 8px 12px; border-radius: 6px; font-size: 13px; cursor: pointer; }
        button { background: #2962FF; border: none; font-weight: bold; color: white; }
        button:hover { background: #1e4bd6; }
        button.danger { background: #f05454; }
        button.danger:hover { background: #d94343; }
        button.kill { background: #aa2e2e; color: white; }
        .mode-selector { display: flex; gap: 8px; background: #131722; padding: 5px; border-radius: 30px; }
        .mode-option { padding: 5px 12px; border-radius: 20px; cursor: pointer; color: #d1d4dc; }
        .mode-option.active { background: #2962FF; color: white; font-weight: bold; }
        .market-status { margin-left: auto; font-size: 14px; background: #131722; padding: 5px 12px; border-radius: 20px; display: flex; align-items: center; gap: 6px; }
        .status-badge { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
        .status-open { background: #00ff9d; box-shadow: 0 0 5px #00ff9d; }
        .status-closed { background: #ff6b6b; }
        .chart-container { background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 12px; margin-bottom: 20px; }
        #equityChart { width: 100%; height: 450px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 20px; }
        .metric-card { background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 12px; text-align: center; transition: 0.2s; }
        .metric-card:hover { border-color: #2962FF; }
        .metric-value { font-size: 24px; font-weight: bold; color: #2962FF; margin-top: 8px; }
        .metric-label { font-size: 12px; text-transform: uppercase; color: #787b86; letter-spacing: 0.5px; }
        .card { background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
        .card h3 { margin-top: 0; color: #d1d4dc; border-bottom: 1px solid #2a2e39; padding-bottom: 8px; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #2a2e39; padding: 8px; text-align: left; }
        th { background: #2a2e39; color: #d1d4dc; }
        .log { background: #1e222d; padding: 10px; height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; }
        .pnl-positive { color: #00ff9d; }
        .pnl-negative { color: #ff6b6b; }
        .position-row { margin-bottom: 10px; padding: 8px; background: #131722; border-radius: 6px; }
        .close-btn { background: #f05454; color: white; border: none; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
</head>
<body>
<div class="container">
    <div class="controls">
        <div class="mode-selector" id="modeSelector">
            <span data-mode="backtest" class="mode-option active">🔁 Backtest</span>
            <span data-mode="paper" class="mode-option">📄 Paper</span>
            <span data-mode="live" class="mode-option">💰 Live</span>
        </div>
        <select id="expiry"></select>
        <select id="strike"></select>
        <select id="optionType">
            <option value="CE">CE</option>
            <option value="PE">PE</option>
        </select>
        <select id="timeframe">
            <option value="1minute">1 min</option>
            <option value="5minute">5 min</option>
            <option value="15minute">15 min</option>
            <option value="30minute">30 min</option>
            <option value="day">Day</option>
            <option value="week">Week</option>
            <option value="month">Month</option>
        </select>
        <input type="date" id="startDate">
        <input type="date" id="endDate">
        <input type="number" id="initialBalance" placeholder="Initial Balance" value="100000" step="1000">
        <button id="startBtn">▶ START</button>
        <button id="stopBtn" class="danger">⏹ STOP</button>
        <button id="killBtn" class="kill">⚠ KILL SWITCH</button>
        <button id="exportBtn">📥 Export Results</button>
        <span id="modeLabel" style="background:#1e1e2e; padding:5px 12px; border-radius:20px;">Mode: Backtest</span>
        <div class="market-status">
            <span class="status-badge" id="marketBadge"></span>
            <span id="marketText">Checking...</span>
        </div>
    </div>

    <!-- Main Chart Area -->
    <div class="chart-container">
        <div id="equityChart"></div>
    </div>

    <!-- Metrics Grid -->
    <div class="metrics-grid">
        <div class="metric-card"><div class="metric-label">Total P&L</div><div class="metric-value" id="totalPnl">₹0</div></div>
        <div class="metric-card"><div class="metric-label">Return %</div><div class="metric-value" id="returnPercent">0%</div></div>
        <div class="metric-card"><div class="metric-label">Max Drawdown</div><div class="metric-value" id="maxDrawdown">₹0</div></div>
        <div class="metric-card"><div class="metric-label">Profit Factor</div><div class="metric-value" id="profitFactor">0</div></div>
        <div class="metric-card"><div class="metric-label">Total Trades</div><div class="metric-value" id="totalTrades">0</div></div>
        <div class="metric-card"><div class="metric-label">Win Rate %</div><div class="metric-value" id="winRate">0%</div></div>
    </div>

    <!-- Trade Log Table -->
    <div class="card">
        <h3>📋 Trade Log (last 20)</h3>
        <div style="overflow-x: auto;">
            <table id="tradeTable">
                <thead><tr><th>Entry Time</th><th>Exit Time</th><th>Reason</th><th>Entry Price</th><th>Exit Price</th><th>P&L (₹)</th><th>Instrument</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>

    <!-- Event Log -->
    <div class="card">
        <h3>📝 Event Log</h3>
        <div class="log" id="logPanel"></div>
    </div>
</div>

<script>
    let eventSource = null;
    let activeDemo = false;
    let equityChart = null;

    async function loadInstruments() {
        let resp = await fetch('/api/instruments');
        let data = await resp.json();
        let expirySelect = document.getElementById('expiry');
        expirySelect.innerHTML = '';
        for (let exp of data.expiries) {
            let option = document.createElement('option');
            option.value = exp;
            option.text = exp;
            expirySelect.appendChild(option);
        }
        updateStrikes();
    }
    async function updateStrikes() {
        let expiry = document.getElementById('expiry').value;
        let type = document.getElementById('optionType').value;
        let resp = await fetch(`/api/strikes?expiry=${expiry}&type=${type}`);
        let data = await resp.json();
        let strikeSelect = document.getElementById('strike');
        strikeSelect.innerHTML = '';
        for (let s of data.strikes) {
            let option = document.createElement('option');
            option.value = s;
            option.text = s;
            strikeSelect.appendChild(option);
        }
    }
    document.getElementById('expiry').addEventListener('change', updateStrikes);
    document.getElementById('optionType').addEventListener('change', updateStrikes);
    loadInstruments();

    function updateMarketStatus() {
        let now = new Date();
        let day = now.getDay();
        let hours = now.getHours();
        let minutes = now.getMinutes();
        let time = hours + minutes/60;
        let isWeekday = (day >= 1 && day <= 5);
        let isSession = (time >= 9.25 && time <= 15.30);
        let isOpen = isWeekday && isSession;
        let badge = document.getElementById('marketBadge');
        let textSpan = document.getElementById('marketText');
        if (isOpen) {
            badge.className = 'status-badge status-open';
            textSpan.innerText = 'Market OPEN';
        } else {
            badge.className = 'status-badge status-closed';
            if (!isWeekday) textSpan.innerText = 'Market CLOSED (weekend)';
            else textSpan.innerText = 'Market CLOSED (off hours)';
        }
    }
    setInterval(updateMarketStatus, 1000);
    updateMarketStatus();

    function initEquityChart() {
        if (equityChart) {
            equityChart.destroy();
            document.getElementById('equityChart').innerHTML = '';
        }
        let options = {
            series: [{ name: 'Cumulative P&L', data: [], type: 'area' }],
            chart: {
                type: 'area',
                height: 450,
                background: '#1e222d',
                foreColor: '#d1d4dc',
                toolbar: { show: true, tools: { zoom: true, pan: true, reset: true } },
                zoom: { enabled: true, type: 'x', autoScaleYaxis: true },
                animations: { enabled: false }
            },
            stroke: { curve: 'smooth', width: 2, colors: ['#2962FF'] },
            fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.1 } },
            grid: { borderColor: '#2a2e39', row: { colors: ['transparent'], opacity: 0.5 } },
            xaxis: {
                type: 'datetime',
                labels: {
                    datetimeUTC: false,
                    format: 'HH:mm',
                    style: { colors: '#d1d4dc' }
                },
                tickAmount: 8,
                title: { text: 'Time', style: { color: '#d1d4dc' } }
            },
            yaxis: {
                labels: {
                    formatter: function(val) {
                        return '₹' + Math.round(val).toString();
                    },
                    style: { colors: '#d1d4dc' }
                },
                title: { text: 'P&L (₹)', style: { color: '#d1d4dc' } },
                tickAmount: 6
            },
            tooltip: { x: { format: 'HH:mm:ss' }, y: { formatter: (val) => '₹' + val.toFixed(2) } },
            markers: { size: 0, hover: { size: 4 } },
            title: { text: 'Equity Curve', align: 'left', style: { color: '#d1d4dc' } }
        };
        equityChart = new ApexCharts(document.querySelector("#equityChart"), options);
        equityChart.render();
    }

    function updateEquityCurve(equityPoints) {
        if (!equityChart) initEquityChart();
        let seriesData = equityPoints.map(p => ({ x: new Date(p.timestamp).getTime(), y: p.equity }));
        equityChart.updateSeries([{ data: seriesData }]);
    }

    function updateStatus(data) {
        let balEl = document.getElementById('balance');
        if (balEl) balEl.innerText = data.balance.toFixed(2);
        
        let pnlSpan = document.getElementById('dailyPnl');
        if (pnlSpan) {
            pnlSpan.innerText = '₹' + data.daily_pnl.toFixed(2);
            pnlSpan.className = (data.daily_pnl >= 0 ? 'pnl-positive' : 'pnl-negative') + ' balance-value';
        }
        
        let killSwitch = document.getElementById('killSwitch');
        if (killSwitch) killSwitch.innerText = data.kill_switch ? 'ACTIVATED' : 'OFF';
        
        let lossBar = document.getElementById('lossBar');
        if (lossBar) {
            let lossPercent = Math.min(100, Math.max(0, (-data.daily_pnl / 20000) * 100));
            lossBar.style.width = lossPercent + '%';
            let lossPercentText = document.getElementById('lossPercentText');
            if (lossPercentText) lossPercentText.innerText = lossPercent.toFixed(1) + '% used';
        }
        
        let posDiv = document.getElementById('positionsPanel');
        if (posDiv) {
            if (Object.keys(data.open_positions).length === 0) {
                posDiv.innerHTML = 'None';
            } else {
                let html = '';
                for (let [key, pos] of Object.entries(data.open_positions)) {
                    html += `<div class="position-row"><strong>${key}</strong> | Qty: ${pos.qty} | Entry: ₹${pos.entry_price.toFixed(2)}<button class="close-btn" onclick="closePosition('${key}')">CLOSE</button></div>`;
                }
                posDiv.innerHTML = html;
            }
        }
        
        let tbody = document.querySelector('#tradeTable tbody');
        if (tbody) {
            tbody.innerHTML = '';
            (data.trades || []).slice().reverse().forEach(t => {
                let row = `<tr>
                    <td>${t.entry_time || ''}</td>
                    <td>${t.exit_time || ''}</td>
                    <td>${t.reason || ''}</td>
                    <td>${t.entry_price.toFixed(2)}</td>
                    <td>${t.exit_price.toFixed(2)}</td>
                    <td class="${t.pnl>=0?'pnl-positive':'pnl-negative'}">${t.pnl.toFixed(2)}</td>
                    <td>Option</td>
                </tr>`;
                tbody.innerHTML += row;
            });
        }
        if (data.equity_curve) updateEquityCurve(data.equity_curve);

        document.getElementById('totalPnl').innerText = '₹' + (data.total_pnl || 0).toFixed(2);
        document.getElementById('returnPercent').innerText = (data.return_percent || 0).toFixed(2) + '%';
        document.getElementById('maxDrawdown').innerText = '₹' + (data.max_drawdown || 0).toFixed(2);
        document.getElementById('profitFactor').innerText = (data.profit_factor || 0).toFixed(2);
        document.getElementById('totalTrades').innerText = data.total_trades || 0;
        document.getElementById('winRate').innerText = (data.win_rate || 0).toFixed(1) + '%';

        // Total P&L
        const pnlElem = document.getElementById('totalPnl');
        const pnlVal = data.total_pnl || 0;
        pnlElem.style.color = pnlVal > 0 ? '#00ff9d' : (pnlVal < 0 ? '#ff6b6b' : '#d1d4dc');

        // Return %
        const retElem = document.getElementById('returnPercent');
        const retVal = data.return_percent || 0;
        retElem.style.color = retVal > 0 ? '#00ff9d' : (retVal < 0 ? '#ff6b6b' : '#d1d4dc');

        // Max Drawdown (negative is bad, show red)
        const ddElem = document.getElementById('maxDrawdown');
        const ddVal = data.max_drawdown || 0;
        ddElem.style.color = ddVal < 0 ? '#ff6b6b' : '#d1d4dc';

        // Profit Factor (>1 good green, <1 bad red)
        const pfElem = document.getElementById('profitFactor');
        const pfVal = data.profit_factor || 0;
        pfElem.style.color = pfVal > 1 ? '#00ff9d' : (pfVal < 1 ? '#ff6b6b' : '#d1d4dc');

        // Win Rate (>50% green, else red)
        const wrElem = document.getElementById('winRate');
        const wrVal = data.win_rate || 0;
        wrElem.style.color = wrVal > 50 ? '#00ff9d' : '#ff6b6b';

        // Total Trades (always neutral)
        document.getElementById('totalTrades').style.color = '#d1d4dc';
    }

    function addLog(msg) {
        let logDiv = document.getElementById('logPanel');
        let entry = document.createElement('div');
        entry.innerText = new Date().toLocaleTimeString() + ' ' + msg;
        logDiv.appendChild(entry);
        logDiv.scrollTop = logDiv.scrollHeight;
        if (logDiv.children.length > 100) logDiv.removeChild(logDiv.children[0]);
    }

    function closePosition(instrumentKey) {
        addLog(`Manual close requested for ${instrumentKey} (not implemented)`);
    }

    async function startBot() {
        if (activeDemo) { addLog('Bot already running. Stop first.'); return; }
        let mode = document.querySelector('.mode-option.active').dataset.mode;
        let expiry = document.getElementById('expiry').value;
        let strike = document.getElementById('strike').value;
        let optionType = document.getElementById('optionType').value;
        let timeframe = document.getElementById('timeframe').value;
        let startDate = document.getElementById('startDate').value;
        let endDate = document.getElementById('endDate').value;
        let initialBalance = parseFloat(document.getElementById('initialBalance').value);
        let payload = {
            mode: mode,
            strike: strike,
            expiry: expiry,
            option_type: optionType,
            timeframe: timeframe,
            start_date: startDate,
            end_date: endDate,
            initial_balance: initialBalance
        };
        console.log("Starting bot with mode:", mode);
        let resp = await fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        let data = await resp.json();
        if (data.status === 'started') {
            activeDemo = true;
            document.getElementById('modeLabel').innerText = `Mode: ${mode.toUpperCase()}`;
            addLog(`${mode} started`);
            initEquityChart();
            connectEventSource();
        } else {
            addLog('Error: ' + (data.error || 'Unknown'));
        }
    }

    function stopBot() {
        if (!activeDemo) return;
        fetch('/stop', { method: 'POST' }).then(() => {
            activeDemo = false;
            document.getElementById('modeLabel').innerHTML = 'Mode: Idle';
            addLog('Bot stopped');
            if (eventSource) eventSource.close();
            if (equityChart) {
                equityChart.updateSeries([{ data: [] }]);
            }
            document.getElementById('totalPnl').innerText = '₹0.00';
            document.getElementById('returnPercent').innerText = '0.00%';
            document.getElementById('maxDrawdown').innerText = '₹0.00';
            document.getElementById('profitFactor').innerText = '0.00';
            document.getElementById('totalTrades').innerText = '0';
            document.getElementById('winRate').innerText = '0.00%';
        });
    }

    function killSwitch() {
        fetch('/kill', { method: 'POST' }).then(res => res.json()).then(data => {
            addLog('Kill switch triggered');
            if (data.status === 'killed') { activeDemo = false; if (eventSource) eventSource.close(); }
        });
    }

    function exportResults() {
        window.open('/export', '_blank');
    }

    function connectEventSource() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/stream');
        eventSource.onmessage = function(event) {
            let data = JSON.parse(event.data);
            if (data.type === 'status') updateStatus(data.data);
            else if (data.type === 'log') addLog(data.data);
        };
        eventSource.onerror = () => setTimeout(connectEventSource, 3000);
    }

    document.getElementById('startBtn').onclick = startBot;
    document.getElementById('stopBtn').onclick = stopBot;
    document.getElementById('killBtn').onclick = killSwitch;
    document.getElementById('exportBtn').onclick = exportResults;

    window.onload = () => {
        fetch('/status').then(res => res.json()).then(updateStatus);
        addLog('Backtest dashboard ready. Select instrument and date range, then click START.');
    };
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/instruments')
def get_instruments():
    df = pd.read_csv('nifty_options.csv')
    expiries = sorted(df['expiry'].dropna().unique())
    expiries_dates = [pd.to_datetime(e, unit='ms').strftime('%Y-%m-%d') for e in expiries]
    return jsonify({'expiries': expiries_dates})

@app.route('/api/strikes')
def get_strikes():
    expiry_str = request.args.get('expiry')
    option_type = request.args.get('type')
    df = pd.read_csv('nifty_options.csv')
    df['expiry_date'] = pd.to_datetime(df['expiry'], unit='ms').dt.strftime('%Y-%m-%d')
    filtered = df[(df['expiry_date'] == expiry_str) & (df['instrument_type'] == option_type)]
    strikes = sorted(filtered['strike_price'].unique())
    return jsonify({'strikes': strikes})

@app.route('/start', methods=['POST'])
def start_bot():
    global current_strategy, current_account, backtest_thread, active_mode
    data = request.get_json()
    mode = data.get('mode')
    strike = data.get('strike')
    expiry = data.get('expiry')
    option_type = data.get('option_type')
    timeframe = data.get('timeframe')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    initial_balance = float(data.get('initial_balance', 100000))

    if not all([strike, expiry, option_type]):
        return jsonify({'error': 'Please select strike, expiry and option type'}), 400

    try:
        instrument_key = get_instrument_key_from_csv(strike, expiry, option_type)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    if not start_date or not end_date:
        end_date_obj = datetime.now()
        start_date_obj = end_date_obj - timedelta(days=7)
    else:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')

    if current_strategy:
        return jsonify({'error': 'Bot already running'}), 400

    if mode == 'backtest':
        try:
            candles = fetch_historical_candles(instrument_key, '1minute', start_date_obj, end_date_obj)
            if not candles:
                return jsonify({'error': 'No candles returned for this date range'}), 400
            if timeframe in ['5minute', '15minute']:
                candles = resample_candles(candles, timeframe)
            elif timeframe not in ['1minute']:
                try:
                    candles_direct = fetch_historical_candles(instrument_key, timeframe, start_date_obj, end_date_obj)
                    if candles_direct:
                        candles = candles_direct
                except:
                    candles = resample_candles(candles, timeframe)
        except Exception as e:
            return jsonify({'error': str(e)}), 400

        current_account = PaperAccount(initial_balance=initial_balance)
        current_strategy = HeikinAshiStrategy(current_account, instrument_key)

        def on_candle(candle):
            app.config['latest_candle'] = candle
        current_strategy.set_candle_callback(on_candle)

        def on_trade(trade):
            app.config['latest_trade'] = trade
        current_account.register_trade_callback(on_trade)

        def run():
            global current_strategy, current_account, backtest_thread
            run_backtest(current_strategy, candles)
            current_strategy = None
            current_account = None
            backtest_thread = None
        backtest_thread = threading.Thread(target=run, daemon=True)
        backtest_thread.start()
        active_mode = 'backtest'
        return jsonify({'status': 'started'})

    elif mode == 'paper':
        if not ACCESS_TOKEN:
            return jsonify({'error': 'No access token. Run auth.py first.'}), 400
        current_account = PaperAccount(initial_balance=initial_balance)
        current_strategy = HeikinAshiStrategy(current_account, instrument_key)
        current_feed = LiveFeed(instrument_key, current_strategy)
        app.config['live_feed'] = current_feed

        def on_candle(candle):
            app.config['latest_candle'] = candle
        current_strategy.set_candle_callback(on_candle)

        def on_trade(trade):
            app.config['latest_trade'] = trade
        current_account.register_trade_callback(on_trade)

        def run_paper():
            global current_strategy, current_account, backtest_thread, current_feed
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(current_feed.connect())
            except Exception as e:
                print(f"Paper trading error: {e}")
            finally:
                current_strategy = None
                current_account = None
                backtest_thread = None
                current_feed = None
                app.config['live_feed'] = None

        backtest_thread = threading.Thread(target=run_paper, daemon=True)
        backtest_thread.start()
        active_mode = 'paper'
        return jsonify({'status': 'started'})

    else:
        return jsonify({'error': 'Unsupported mode selected'}), 400

@app.route('/stop', methods=['POST'])
def stop_bot():
    global current_strategy, current_account, backtest_thread, active_mode
    live_feed = app.config.get('live_feed')
    if live_feed:
        live_feed.stop()
        app.config['live_feed'] = None
    current_strategy = None
    current_account = None
    backtest_thread = None
    active_mode = None
    app.config['latest_candle'] = None
    app.config['latest_trade'] = None
    return jsonify({'status': 'stopped'})

@app.route('/kill', methods=['POST'])
def kill_switch():
    global current_account, current_strategy
    if current_account:
        current_account.kill_switch_triggered = True
        for instrument_key in list(current_account.positions.keys()):
            pos = current_account.positions.pop(instrument_key)
            current_account.balance += pos['qty'] * pos['entry_price']
            current_account.trades.append({
                'entry_time': pos['entry_time'].strftime('%H:%M:%S') if pos['entry_time'] else '',
                'exit_time': datetime.now().strftime('%H:%M:%S'),
                'entry_price': pos['entry_price'],
                'exit_price': pos['entry_price'],
                'pnl': 0,
                'reason': 'Kill Switch'
            })
        current_strategy = None
    return jsonify({'status': 'killed'})

@app.route('/status')
def status():
    if current_account:
        return jsonify(current_account.get_status())
    return jsonify({'balance': 0, 'daily_pnl': 0, 'open_positions': {}, 'kill_switch': False, 'trades': [], 'equity_curve': []})

@app.route('/export')
def export_results():
    if not current_account:
        return "No results to export", 400
    import io
    output = io.StringIO()
    output.write("entry_time,exit_time,entry_price,exit_price,pnl,reason\n")
    for t in current_account.trades:
        output.write(f"{t['entry_time']},{t['exit_time']},{t['entry_price']},{t['exit_price']},{t['pnl']},{t['reason']}\n")
    output.seek(0)
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=backtest_results.csv"})

@app.route('/stream')
def stream():
    def event_stream():
        last_candle_ts = None
        last_trade = None
        last_status_hash = None
        while True:
            if current_account:
                status = current_account.get_status()
                if str(status) != last_status_hash:
                    yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                    last_status_hash = str(status)
                candle = app.config.get('latest_candle')
                if candle and (not last_candle_ts or candle['timestamp'] != last_candle_ts):
                    last_candle_ts = candle['timestamp']
                trade = app.config.get('latest_trade')
                if trade and trade != last_trade:
                    last_trade = trade
                    log_msg = f"Trade: {trade['action']} @ {trade['price']}"
                    yield f"data: {json.dumps({'type': 'log', 'data': log_msg})}\n\n"
            time.sleep(0.3)
    return app.response_class(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.config['latest_candle'] = None
    app.config['latest_trade'] = None
    app.run(debug=True, port=8080)
