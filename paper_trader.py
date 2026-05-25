import json
import asyncio
import threading
import time
import requests
import websockets
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import os

# -------------------------------
# Load access token
# -------------------------------
TOKEN_FILE = "token.txt"
ACCESS_TOKEN = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        ACCESS_TOKEN = f.read().strip()

# -------------------------------
# Helper: Get instrument_key from CSV
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
# Paper Trading Account (with metrics)
# -------------------------------
class PaperAccount:
    def __init__(self, initial_balance=100000):
        self.balance = initial_balance
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
        if cost > self.balance:
            return False
        self.balance -= cost
        self.positions[instrument_key] = {'qty': qty, 'entry_price': price, 'entry_time': timestamp}
        self._notify_trade({'action': 'BUY', 'price': price, 'timestamp': timestamp.isoformat() if timestamp else None})
        return True

    def place_sell_order(self, instrument_key, price, qty=75, timestamp=None, reason=""):
        if instrument_key not in self.positions:
            return False
        pos = self.positions.pop(instrument_key)
        proceeds = price * qty
        self.balance += proceeds
        pnl = (price - pos['entry_price']) * qty
        self.daily_pnl += pnl
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
        open_positions_serializable = {k: {"qty": v["qty"], "entry_price": v["entry_price"]} for k, v in self.positions.items()}
        total_pnl = sum(t['pnl'] for t in self.trades)
        total_trades = len(self.trades)
        profitable_trades = sum(1 for t in self.trades if t['pnl'] > 0)
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        gains = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        profit_factor = gains / losses if losses > 0 else 0
        # max drawdown from equity curve
        max_drawdown = 0
        peak = 0
        for point in self.equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            drawdown = peak - point['equity']
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': open_positions_serializable,
            'kill_switch': self.kill_switch_triggered,
            'trades': serializable_trades,
            'equity_curve': self.equity_curve[-100:],
            'total_pnl': total_pnl,
            'return_percent': (total_pnl / self.balance) * 100 if self.balance > 0 else 0,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'total_trades': total_trades,
            'win_rate': win_rate
        }

# -------------------------------
# Heikin-Ashi Strategy (same as backtest)
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
        self.pending_entry = False
        self.pending_entry_time = None
        self.candle_callback = None

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

        if not self.in_position and (not prev_green) and current_green:
            self.pending_entry = True
            self.pending_entry_time = candle['timestamp']

        if self.pending_entry and not self.in_position and candle['timestamp'] > self.pending_entry_time:
            entry_price = candle['open']
            success = self.account.place_buy_order(self.instrument_key, entry_price, timestamp=candle['timestamp'])
            if success:
                self.in_position = True
                self.entry_price = entry_price
                self.entry_candle_time = candle['timestamp']
                self.pending_entry = False

        if self.in_position and candle['timestamp'] > self.entry_candle_time:
            exit_reason = None
            if candle['low'] <= self.entry_price:
                exit_reason = "Breakeven"
                exit_price = self.entry_price
            elif not current_green:
                exit_reason = "Red Signal"
                exit_price = candle['close']
            elif candle['timestamp'].time() >= datetime.strptime("14:00", "%H:%M").time():
                exit_reason = "Session End"
                exit_price = candle['close']
            if exit_reason:
                self.account.place_sell_order(self.instrument_key, exit_price, timestamp=candle['timestamp'], reason=exit_reason)
                self.in_position = False
                self.entry_price = None
                self.entry_candle_time = None

# -------------------------------
# Live WebSocket Feed
# -------------------------------
import MarketDataFeed_pb2 as pb

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
                "guid": "paper_trader",
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
# Flask App – Full Paper Trading Dashboard
# -------------------------------
app = Flask(__name__)
CORS(app)

current_strategy = None
current_account = None
live_thread = None
current_feed = None

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Valkyrie Trader – Paper Trading</title>
    <style>
        * { box-sizing: border-box; }
        body { background: #131722; color: #d1d4dc; font-family: 'Inter', sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 1600px; margin: auto; }
        .controls { background: #1e222d; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        button, select, input { padding: 8px 12px; border-radius: 6px; background: #2a2e39; color: #fff; border: 1px solid #2962FF; cursor: pointer; }
        button { background: #2962FF; }
        button.danger { background: #f05454; }
        .chart-container { background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 12px; margin-bottom: 20px; }
        #equityChart { width: 100%; height: 400px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 20px; }
        .metric-card { background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 12px; text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; color: #2962FF; }
        .card { background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #2a2e39; padding: 6px; text-align: left; }
        .log { background: #1e222d; height: 150px; overflow-y: auto; font-family: monospace; padding: 10px; margin-top: 20px; }
        .pnl-positive { color: #00ff9d; }
        .pnl-negative { color: #ff6b6b; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
</head>
<body>
<div class="container">
    <h1>📄 Valkyrie Trader – Paper Trading</h1>
    <div class="controls">
        <select id="expiry"></select>
        <select id="strike"></select>
        <select id="optionType">
            <option value="CE">CE</option>
            <option value="PE">PE</option>
        </select>
        <input type="number" id="initialBalance" placeholder="Balance" value="100000" step="1000">
        <button id="startBtn">▶ START</button>
        <button id="stopBtn" class="danger">⏹ STOP</button>
        <button id="killBtn" class="danger">⚠ KILL SWITCH</button>
        <span id="modeLabel">Mode: PAPER</span>
    </div>
    <div class="chart-container">
        <div id="equityChart"></div>
    </div>
    <div class="metrics-grid">
        <div class="metric-card"><div>Total P&L</div><div class="metric-value" id="totalPnl">₹0</div></div>
        <div class="metric-card"><div>Return %</div><div class="metric-value" id="returnPercent">0%</div></div>
        <div class="metric-card"><div>Max Drawdown</div><div class="metric-value" id="maxDrawdown">₹0</div></div>
        <div class="metric-card"><div>Profit Factor</div><div class="metric-value" id="profitFactor">0</div></div>
        <div class="metric-card"><div>Total Trades</div><div class="metric-value" id="totalTrades">0</div></div>
        <div class="metric-card"><div>Win Rate %</div><div class="metric-value" id="winRate">0%</div></div>
    </div>
    <div class="card">
        <h3>📊 Open Positions</h3>
        <div id="positionsPanel">None</div>
    </div>
    <div class="card">
        <h3>📋 Trade Log (last 20)</h3>
        <div style="overflow-x: auto;">
            <table id="tradeTable">
                <thead><tr><th>Entry Time</th><th>Exit Time</th><th>Reason</th><th>Entry Price</th><th>Exit Price</th><th>P&L (₹)</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    <div class="log" id="logPanel"></div>
</div>

<script>
    let eventSource = null;
    let active = false;
    let equityChart = null;

    // Load instruments from CSV
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

    function initEquityChart() {
        if (equityChart) equityChart.destroy();
        let options = {
            series: [{ name: 'Cumulative P&L', data: [], type: 'area' }],
            chart: { type: 'area', height: 400, background: '#1e222d', foreColor: '#d1d4dc', toolbar: { show: true }, zoom: { enabled: true }, animations: { enabled: false } },
            stroke: { curve: 'smooth', width: 2, colors: ['#2962FF'] },
            fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.1 } },
            xaxis: { type: 'datetime', labels: { datetimeUTC: false, format: 'HH:mm' }, title: { text: 'Time' } },
            yaxis: { labels: { formatter: (val) => '₹' + Math.round(val) }, title: { text: 'P&L (₹)' } },
            tooltip: { x: { format: 'HH:mm:ss' }, y: { formatter: (val) => '₹' + val.toFixed(2) } }
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
        document.getElementById('totalPnl').innerText = '₹' + (data.total_pnl || 0).toFixed(2);
        document.getElementById('returnPercent').innerText = (data.return_percent || 0).toFixed(2) + '%';
        document.getElementById('maxDrawdown').innerText = '₹' + (data.max_drawdown || 0).toFixed(2);
        document.getElementById('profitFactor').innerText = (data.profit_factor || 0).toFixed(2);
        document.getElementById('totalTrades').innerText = data.total_trades || 0;
        document.getElementById('winRate').innerText = (data.win_rate || 0).toFixed(1) + '%';
        let posDiv = document.getElementById('positionsPanel');
        if (Object.keys(data.open_positions).length === 0) {
            posDiv.innerHTML = 'None';
        } else {
            let html = '';
            for (let [key, pos] of Object.entries(data.open_positions)) {
                html += `<div><strong>${key}</strong> | Qty: ${pos.qty} | Entry: ₹${pos.entry_price.toFixed(2)}</div>`;
            }
            posDiv.innerHTML = html;
        }
        let tbody = document.querySelector('#tradeTable tbody');
        tbody.innerHTML = '';
        (data.trades || []).slice().reverse().forEach(t => {
            let row = `<tr>
                <td>${t.entry_time}</td>
                <td>${t.exit_time}</td>
                <td>${t.reason}</td>
                <td>${t.entry_price.toFixed(2)}</td>
                <td>${t.exit_price.toFixed(2)}</td>
                <td class="${t.pnl>=0?'pnl-positive':'pnl-negative'}">${t.pnl.toFixed(2)}</td>
            </tr>`;
            tbody.innerHTML += row;
        });
        if (data.equity_curve) updateEquityCurve(data.equity_curve);
    }

    // Event log helper
    function addLog(msg) {
        let logDiv = document.getElementById('logPanel');
        let entry = document.createElement('div');
        entry.innerText = new Date().toLocaleTimeString() + ' ' + msg;
        logDiv.appendChild(entry);
        logDiv.scrollTop = logDiv.scrollHeight;
        if (logDiv.children.length > 100) logDiv.removeChild(logDiv.children[0]);
    }

    async function startBot() {
        if (active) { addLog('Already running'); return; }
        let expiry = document.getElementById('expiry').value;
        let strike = document.getElementById('strike').value;
        let optionType = document.getElementById('optionType').value;
        let initialBalance = parseFloat(document.getElementById('initialBalance').value);
        let payload = {
            mode: 'paper',
            strike: strike,
            expiry: expiry,
            option_type: optionType,
            initial_balance: initialBalance
        };
        let resp = await fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        let data = await resp.json();
        if (data.status === 'started') {
            active = true;
            addLog('Paper trading started');
            initEquityChart();
            connectEventSource();
        } else {
            addLog('Error: ' + (data.error || 'Unknown'));
        }
    }

    function stopBot() {
        fetch('/stop', { method: 'POST' }).then(() => {
            active = false;
            addLog('Bot stopped');
            if (eventSource) eventSource.close();
            if (equityChart) equityChart.destroy();
            equityChart = null;
        });
    }

    function killSwitch() {
        fetch('/kill', { method: 'POST' }).then(() => addLog('Kill switch triggered'));
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
    window.onload = () => {
        fetch('/status').then(res => res.json()).then(updateStatus);
        addLog('Paper trading dashboard ready. Select instrument and click START.');
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
    global current_strategy, current_account, live_thread, current_feed
    data = request.get_json()
    strike = data.get('strike')
    expiry = data.get('expiry')
    option_type = data.get('option_type')
    initial_balance = float(data.get('initial_balance', 100000))
    if not all([strike, expiry, option_type]):
        return jsonify({'error': 'Please select strike, expiry and option type'}), 400
    if current_strategy:
        return jsonify({'error': 'Bot already running'}), 400
    if not ACCESS_TOKEN:
        return jsonify({'error': 'No access token. Run auth.py first.'}), 400
    try:
        instrument_key = get_instrument_key_from_csv(strike, expiry, option_type)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    current_account = PaperAccount(initial_balance=initial_balance)
    current_strategy = HeikinAshiStrategy(current_account, instrument_key)
    current_feed = LiveFeed(instrument_key, current_strategy)

    def on_candle(candle):
        app.config['latest_candle'] = candle
    current_strategy.set_candle_callback(on_candle)

    def on_trade(trade):
        app.config['latest_trade'] = trade
    current_account.register_trade_callback(on_trade)

    def run():
        global current_strategy, current_account, live_thread, current_feed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(current_feed.connect())
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            current_strategy = None
            current_account = None
            current_feed = None
            live_thread = None

    live_thread = threading.Thread(target=run, daemon=True)
    live_thread.start()
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop_bot():
    global current_strategy, current_account, live_thread, current_feed
    if current_feed:
        current_feed.stop()
    current_strategy = None
    current_account = None
    current_feed = None
    live_thread = None
    return jsonify({'status': 'stopped'})

@app.route('/kill', methods=['POST'])
def kill_switch():
    global current_account
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
    return jsonify({'status': 'killed'})

@app.route('/status')
def status():
    if current_account:
        return jsonify(current_account.get_status())
    return jsonify({'balance': 0, 'daily_pnl': 0, 'open_positions': {}, 'kill_switch': False, 'trades': [], 'equity_curve': [], 'total_pnl': 0, 'return_percent': 0, 'max_drawdown': 0, 'profit_factor': 0, 'total_trades': 0, 'win_rate': 0})

@app.route('/stream')
def stream():
    def event_stream():
        last_trade = None
        last_status_hash = None
        while True:
            if current_account:
                status = current_account.get_status()
                if str(status) != last_status_hash:
                    yield f"data: {json.dumps({'type': 'status', 'data': status})}\n\n"
                    last_status_hash = str(status)
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
    app.run(debug=True, port=3000, ssl_context=('cert.pem', 'key.pem'))
