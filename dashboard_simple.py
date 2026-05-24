import json
import threading
import time
from datetime import datetime
import pandas as pd
import numpy as np
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import os

# -------------------------------
# Load token (not used in demo)
# -------------------------------
TOKEN_FILE = "token.txt"
ACCESS_TOKEN = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        ACCESS_TOKEN = f.read().strip()

# -------------------------------
# Paper Trading Account (same)
# -------------------------------
class PaperAccount:
    def __init__(self, initial_balance=100000):
        self.balance = initial_balance
        self.positions = {}
        self.trades = []
        self.daily_pnl = 0
        self.daily_loss_limit = 20000
        self.kill_switch_triggered = False

    def place_buy_order(self, instrument_key, price, qty=75, timestamp=None):
        if self.kill_switch_triggered or instrument_key in self.positions:
            return False
        cost = price * qty
        if cost > self.balance:
            return False
        self.balance -= cost
        self.positions[instrument_key] = {'qty': qty, 'entry_price': price, 'entry_time': timestamp}
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
# Heikin-Ashi Strategy
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
        self.log_callback = None

    def set_log_callback(self, cb):
        self.log_callback = cb

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
            if self.log_callback:
                self.log_callback(f"🔔 BUY at {candle['timestamp'].strftime('%H:%M:%S')} @ ₹{entry_price:.2f}")
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
                if self.log_callback:
                    self.log_callback(f"🔔 SELL at {candle['timestamp'].strftime('%H:%M:%S')} @ ₹{candle['close']:.2f} ({exit_reason})")
        if self.log_callback:
            self.log_callback(f"📊 Candle: {candle['timestamp'].strftime('%H:%M')} O:{candle['open']:.2f} H:{candle['high']:.2f} L:{candle['low']:.2f} C:{candle['close']:.2f}")

# -------------------------------
# Demo Mode Replay
# -------------------------------
def demo_replay(strategy, csv_file='backtest_output.csv'):
    if not os.path.exists(csv_file):
        print(f"❌ {csv_file} not found")
        return
    df = pd.read_csv(csv_file)
    if 'timestamp' not in df.columns:
        print("CSV missing 'timestamp' column")
        return
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    print(f"Demo replay: {len(df)} candles")
    for idx, row in df.iterrows():
        candle = {
            'timestamp': row['timestamp'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close']
        }
        strategy.on_candle_close(candle)
        time.sleep(0.1)  # fast replay
    print("Demo finished")

# -------------------------------
# Flask App
# -------------------------------
app = Flask(__name__)
CORS(app)

current_strategy = None
current_account = None
demo_thread = None
log_messages = []

def add_log(msg):
    log_messages.append({'time': datetime.now().strftime('%H:%M:%S'), 'msg': msg})
    if len(log_messages) > 50:
        log_messages.pop(0)

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Valkyrie Trader - Simple</title>
    <style>
        body { font-family: monospace; margin: 20px; background: #1e1e1e; color: #ddd; }
        .container { max-width: 1200px; margin: auto; }
        button { padding: 8px 16px; margin: 5px; font-size: 14px; }
        .status { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .log { background: #2d2d2d; padding: 15px; border-radius: 8px; height: 400px; overflow-y: scroll; font-size: 12px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        th { background: #3d3d3d; }
    </style>
</head>
<body>
<div class="container">
    <h1>⚡ Valkyrie Trader - Simple Demo</h1>
    <div>
        <button id="demoBtn">▶ START DEMO</button>
        <button id="stopBtn">⏹ STOP</button>
    </div>
    <div class="status">
        <div>Balance: ₹<span id="balance">0</span></div>
        <div>Daily P&L: ₹<span id="dailyPnl">0</span></div>
        <div>Kill Switch: <span id="killSwitch">OFF</span></div>
    </div>
    <div class="log" id="log"></div>
    <div>
        <h3>Trade Log (last 20)</h3>
        <table id="tradeTable">
            <thead><tr><th>Time</th><th>Type</th><th>Price</th><th>P&L</th><th>Reason</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
</div>
<script>
    function updateStatus(data) {
        document.getElementById('balance').innerText = data.balance.toFixed(2);
        document.getElementById('dailyPnl').innerText = data.daily_pnl.toFixed(2);
        document.getElementById('killSwitch').innerText = data.kill_switch ? 'ACTIVATED' : 'OFF';
        let tbody = document.querySelector('#tradeTable tbody');
        tbody.innerHTML = '';
        data.trades.slice().reverse().forEach(t => {
            let row = `<tr><td>${t.exit_time}</td><td>${t.reason}</td><td>${t.exit_price.toFixed(2)}</td><td style="color:${t.pnl>=0?'green':'red'}">${t.pnl.toFixed(2)}</td><td>${t.reason}</td></tr>`;
            tbody.innerHTML += row;
        });
    }
    function addLog(msg) {
        let logDiv = document.getElementById('log');
        let entry = document.createElement('div');
        entry.innerText = msg;
        logDiv.appendChild(entry);
        logDiv.scrollTop = logDiv.scrollHeight;
    }
    function startDemo() {
        fetch('/start', {method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({mode:'demo'})})
        .then(res => res.json())
        .then(data => console.log(data));
    }
    function stopBot() {
        fetch('/stop', {method: 'POST'}).then(res => res.json());
    }
    function pollStatus() {
        fetch('/status').then(res => res.json()).then(data => updateStatus(data));
        fetch('/logs').then(res => res.json()).then(data => { data.logs.forEach(l => addLog(`${l.time} ${l.msg}`)); });
        setTimeout(pollStatus, 1000);
    }
    window.onload = () => {
        document.getElementById('demoBtn').onclick = startDemo;
        document.getElementById('stopBtn').onclick = stopBot;
        pollStatus();
    };
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/start', methods=['POST'])
def start():
    global current_strategy, current_account, demo_thread
    if current_strategy:
        return jsonify({'error': 'Bot already running'}), 400
    current_account = PaperAccount()
    current_strategy = HeikinAshiStrategy(current_account, "NSE_INDEX|NIFTY 50")
    def run():
        global current_strategy, current_account, demo_thread
        demo_replay(current_strategy, 'backtest_output.csv')
        current_strategy = None
        current_account = None
        demo_thread = None
    demo_thread = threading.Thread(target=run, daemon=True)
    demo_thread.start()
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop():
    global current_strategy, current_account, demo_thread
    current_strategy = None
    current_account = None
    demo_thread = None
    return jsonify({'status': 'stopped'})

@app.route('/status')
def status():
    if current_account:
        return jsonify(current_account.get_status())
    return jsonify({'balance':0,'daily_pnl':0,'kill_switch':False,'trades':[]})

@app.route('/logs')
def logs():
    return jsonify({'logs': log_messages})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
