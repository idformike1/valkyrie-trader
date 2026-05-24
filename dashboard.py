import json
import asyncio
import threading
import time
from datetime import datetime
import pandas as pd
import numpy as np
import requests
import websockets
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import os
import sys

# -------------------------------
# Load access token (only for live mode)
# -------------------------------
TOKEN_FILE = "token.txt"
ACCESS_TOKEN = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        ACCESS_TOKEN = f.read().strip()

# -------------------------------
# Paper Trading Account
# -------------------------------
class PaperAccount:
    def __init__(self, initial_balance=100000):
        self.balance = initial_balance
        self.positions = {}
        self.trades = []
        self.daily_pnl = 0
        self.daily_loss_limit = 20000
        self.kill_switch_triggered = False
        self.status_callbacks = []

    def register_callback(self, cb):
        self.status_callbacks.append(cb)

    def _notify(self):
        for cb in self.status_callbacks:
            cb(self.get_status())

    def place_buy_order(self, instrument_key, price, qty=75, timestamp=None):
        if self.kill_switch_triggered:
            return False
        if instrument_key in self.positions:
            return False
        cost = price * qty
        if cost > self.balance:
            return False
        self.balance -= cost
        self.positions[instrument_key] = {'qty': qty, 'entry_price': price, 'entry_time': timestamp}
        self._notify()
        return True

    def place_sell_order(self, instrument_key, price, qty=75, timestamp=None, reason=""):
        if instrument_key not in self.positions:
            return False
        pos = self.positions.pop(instrument_key)
        proceeds = price * qty
        self.balance += proceeds
        pnl = (price - pos['entry_price']) * qty
        self.daily_pnl += pnl
        self.trades.append({
            'entry_time': pos['entry_time'].strftime('%H:%M:%S') if pos['entry_time'] else '',
            'exit_time': timestamp.strftime('%H:%M:%S') if timestamp else '',
            'entry_price': pos['entry_price'],
            'exit_price': price,
            'pnl': pnl,
            'reason': reason
        })
        if self.daily_pnl <= -self.daily_loss_limit:
            self.kill_switch_triggered = True
        self._notify()
        return True

    def get_status(self):
        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': len(self.positions),
            'kill_switch': self.kill_switch_triggered,
            'trades': self.trades[-20:]
        }

# -------------------------------
# Heikin-Ashi and Strategy
# -------------------------------
def calculate_heikin_ashi(candles):
    df = pd.DataFrame(candles)
    ha = pd.DataFrame(index=df.index)
    ha['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4.0
    ha_open = np.zeros(len(df))
    ha_open[0] = df['open'].iloc[0]
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i-1] + ha['HA_Close'].iloc[i-1]) / 2.0
    ha['HA_Open'] = ha_open
    ha['HA_High'] = pd.concat([df['high'], ha['HA_Open'], ha['HA_Close']], axis=1).max(axis=1)
    ha['HA_Low'] = pd.concat([df['low'], ha['HA_Open'], ha['HA_Close']], axis=1).min(axis=1)
    return ha

class HeikinAshiStrategy:
    def __init__(self, account, instrument_key):
        self.account = account
        self.instrument_key = instrument_key
        self.candles = []
        self.in_position = False
        self.entry_price = None
        self.callback = None

    def set_candle_callback(self, cb):
        self.callback = cb

    def on_candle_close(self, candle):
        self.candles.append(candle)
        if len(self.candles) < 2:
            return
        ha = calculate_heikin_ashi(self.candles[-10:])
        current_green = ha['HA_Close'].iloc[-1] >= ha['HA_Open'].iloc[-1]
        prev_green = ha['HA_Close'].iloc[-2] >= ha['HA_Open'].iloc[-2]
        if not self.in_position and (not prev_green) and current_green:
            entry_price = candle['close']
            self.account.place_buy_order(self.instrument_key, entry_price, timestamp=candle['timestamp'])
            self.in_position = True
            self.entry_price = entry_price
        elif self.in_position:
            exit_reason = None
            if candle['low'] <= self.entry_price:
                exit_reason = "Breakeven"
            elif not current_green:
                exit_reason = "Red Signal"
            elif candle['timestamp'].time() >= datetime.strptime("14:00", "%H:%M").time():
                exit_reason = "Session End"
            if exit_reason:
                self.account.place_sell_order(self.instrument_key, candle['close'], timestamp=candle['timestamp'], reason=exit_reason)
                self.in_position = False
                self.entry_price = None
        if self.callback:
            self.callback(candle)

# -------------------------------
# Demo Mode
# -------------------------------
def demo_mode(instrument_key, strategy, csv_file='backtest_output.csv'):
    if not os.path.exists(csv_file):
        print(f"❌ {csv_file} not found. Run strategy_simulator.py first.")
        return
    df = pd.read_csv(csv_file)
    if 'timestamp' not in df.columns:
        print("CSV missing 'timestamp' column")
        return
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    print(f"Demo mode: replaying {len(df)} candles at 1-second intervals")
    for idx, row in df.iterrows():
        candle = {
            'timestamp': row['timestamp'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close']
        }
        strategy.on_candle_close(candle)
        time.sleep(0.5)
    print("Demo replay finished.")

# -------------------------------
# Live WebSocket Feed (stub if pb missing)
# -------------------------------
try:
    import MarketDataFeed_pb2 as pb
except ImportError:
    pb = None

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
        ws_uri = data['data']['authorizedRedirectUri'] or data['data']['authorized_redirect_uri']
        return ws_uri

    async def connect(self):
        uri = await self.get_websocket_uri()
        print(f"Connecting to {uri}")
        async with websockets.connect(uri, max_size=2**25) as ws:
            subscribe_msg = {
                "guid": "valkyrie_dashboard",
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": [self.instrument_key]
                }
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
        if pb is None:
            return
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
# Flask App
# -------------------------------
app = Flask(__name__)
CORS(app)

# Global state
current_feed = None
current_strategy = None
current_account = None
feed_thread = None
demo_thread = None
is_demo_mode = False

# HTML Template (same as before)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Valkyrie Trader</title>
    <script src="/static/lightweight-charts.standalone.js"></script>
    <style>
        body { font-family: Arial; margin: 20px; background: #1e1e1e; color: #ddd; }
        .container { max-width: 1400px; margin: auto; }
        .controls { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        button { padding: 8px 16px; margin: 0 5px; cursor: pointer; }
        #chart { width: 100%; height: 500px; margin-bottom: 20px; }
        .status-panel { display: flex; gap: 20px; margin-bottom: 20px; }
        .card { background: #2d2d2d; padding: 15px; border-radius: 8px; flex: 1; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        th { background: #3d3d3d; }
    </style>
</head>
<body>
<div class="container">
    <h1>⚡ Valkyrie Trader</h1>
    <div class="controls">
        <label>Instrument: </label>
        <input type="text" id="instrument" placeholder="NSE_INDEX|NIFTY 50" size="30">
        <button id="startBtn">▶ START (Live)</button>
        <button id="demoBtn">🎬 DEMO (Historical)</button>
        <button id="stopBtn">⏹ STOP</button>
        <span style="margin-left:20px">Mode: <span id="modeLabel">Idle</span></span>
    </div>
    <div id="chart"></div>
    <div class="status-panel">
        <div class="card">
            <h3>Balance & P&L</h3>
            <div>Balance: ₹<span id="balance">0</span></div>
            <div>Daily P&L: ₹<span id="dailyPnl">0</span></div>
            <div>Loss Limit: ₹20,000</div>
            <div>Kill Switch: <span id="killSwitch">OFF</span></div>
        </div>
        <div class="card">
            <h3>Open Positions</h3>
            <div id="positions">None</div>
        </div>
    </div>
    <div class="card">
        <h3>Trade Log (last 20)</h3>
        <table id="tradeTable">
            <thead><tr><th>#</th><th>Entry Time</th><th>Exit Time</th><th>Entry Price</th><th>Exit Price</th><th>P&L (₹)</th><th>Reason</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
</div>
<script>
    let chart = null;
    let candleSeries = null;

    function initChart() {
        chart = LightweightCharts.createChart(document.getElementById('chart'), {
            width: document.getElementById('chart').clientWidth,
            height: 500,
            layout: { background: { color: '#1e1e1e' }, textColor: '#ddd' },
            grid: { vertLines: { color: '#333' }, horzLines: { color: '#333' } }
        });
        candleSeries = chart.addCandlestickSeries();
    }

    function updateStatus(data) {
        document.getElementById('balance').innerText = data.balance.toFixed(2);
        document.getElementById('dailyPnl').innerText = data.daily_pnl.toFixed(2);
        document.getElementById('killSwitch').innerText = data.kill_switch ? 'ACTIVATED' : 'OFF';
        let posHtml = '';
        if (data.open_positions && typeof data.open_positions === 'object') {
            for (let key in data.open_positions) {
                posHtml += `${key}: ${data.open_positions[key].qty} lots @ ₹${data.open_positions[key].entry_price}<br>`;
            }
        } else if (data.open_positions) {
            posHtml = `${data.open_positions} open position(s)`;
        }
        document.getElementById('positions').innerHTML = posHtml || 'None';
        let tbody = document.querySelector('#tradeTable tbody');
        tbody.innerHTML = '';
        (data.trades || []).slice().reverse().forEach((t, idx) => {
            let row = `<tr>
                <td>${idx+1}</td>
                <td>${t.entry_time || ''}</td>
                <td>${t.exit_time || ''}</td>
                <td>${t.entry_price.toFixed(2)}</td>
                <td>${t.exit_price.toFixed(2)}</td>
                <td style="color: ${t.pnl>=0?'green':'red'}">${t.pnl.toFixed(2)}</td>
                <td>${t.reason || ''}</td>
            </tr>`;
            tbody.innerHTML += row;
        });
    }

    function addCandle(candle) {
        if (!candleSeries) return;
        candleSeries.update({
            time: candle.timestamp,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close
        });
    }

    function startBot(mode) {
        let instr = document.getElementById('instrument').value;
        if (!instr) instr = 'NSE_INDEX|NIFTY 50';
        fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instrument_key: instr, mode: mode })
        }).then(res => res.json()).then(data => {
            console.log(data);
            document.getElementById('modeLabel').innerText = mode === 'demo' ? 'DEMO (replaying)' : 'LIVE';
            connectEventSource();
        });
    }

    function stopBot() {
        fetch('/stop', { method: 'POST' }).then(res => res.json()).then(console.log);
        document.getElementById('modeLabel').innerText = 'Idle';
        if (eventSource) eventSource.close();
    }

    let eventSource = null;
    function connectEventSource() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/stream');
        eventSource.onmessage = function(event) {
            let data = JSON.parse(event.data);
            if (data.type === 'status') updateStatus(data.data);
            else if (data.type === 'candle') addCandle(data.data);
        };
        eventSource.onerror = function() {
            setTimeout(connectEventSource, 3000);
        };
    }

    window.onload = () => {
        initChart();
        document.getElementById('startBtn').onclick = () => startBot('live');
        document.getElementById('demoBtn').onclick = () => startBot('demo');
        document.getElementById('stopBtn').onclick = stopBot;
        fetch('/status').then(res => res.json()).then(data => updateStatus(data));
    };
    window.onresize = () => { if (chart) chart.resize(document.getElementById('chart').clientWidth, 500); };
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/start', methods=['POST'])
def start_bot():
    global current_feed, current_strategy, current_account, feed_thread, demo_thread, is_demo_mode
    data = request.get_json()
    instrument_key = data.get('instrument_key')
    mode = data.get('mode', 'live')
    if not instrument_key:
        return jsonify({'error': 'instrument_key required'}), 400
    if current_feed or demo_thread:
        return jsonify({'error': 'Bot already running'}), 400
    current_account = PaperAccount()
    current_strategy = HeikinAshiStrategy(current_account, instrument_key)
    def broadcast_candle(candle):
        app.config['latest_candle'] = candle
    current_strategy.set_candle_callback(broadcast_candle)
    is_demo_mode = (mode == 'demo')
    if mode == 'demo':
        def run_demo():
            global demo_thread, current_strategy, current_account
            demo_mode(instrument_key, current_strategy, 'backtest_output.csv')
            demo_thread = None
            current_strategy = None
            current_account = None
        demo_thread = threading.Thread(target=run_demo, daemon=True)
        demo_thread.start()
    else:
        current_feed = LiveFeed(instrument_key, current_strategy)
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(current_feed.connect())
        feed_thread = threading.Thread(target=run_async, daemon=True)
        feed_thread.start()
    return jsonify({'status': 'started', 'instrument': instrument_key, 'mode': mode})

@app.route('/stop', methods=['POST'])
def stop_bot():
    global current_feed, current_strategy, current_account, feed_thread, demo_thread, is_demo_mode
    if current_feed:
        current_feed.stop()
        current_feed = None
    # Demo thread will exit on its own, just clear references
    current_strategy = None
    current_account = None
    feed_thread = None
    demo_thread = None
    is_demo_mode = False
    return jsonify({'status': 'stopped'})

@app.route('/status')
def status():
    if current_account:
        return jsonify(current_account.get_status())
    else:
        return jsonify({'balance': 0, 'daily_pnl': 0, 'open_positions': 0, 'kill_switch': False, 'trades': []})

@app.route('/stream')
def stream():
    def event_stream():
        last_candle_ts = None
        while True:
            if current_account:
                status = current_account.get_status()
                yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                candle = app.config.get('latest_candle')
                if candle and (not last_candle_ts or candle['timestamp'] != last_candle_ts):
                    last_candle_ts = candle['timestamp']
                    candle_copy = candle.copy()
                    candle_copy['timestamp'] = candle_copy['timestamp'].isoformat()
                    yield f"data: {json.dumps({'type': 'candle', 'data': candle_copy})}\n\n"
            time.sleep(1)
    return app.response_class(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.config['latest_candle'] = None
    app.run(debug=True, port=8080, threaded=True)
