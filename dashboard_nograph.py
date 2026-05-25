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
# Paper Trading Account (unchanged)
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

    def register_trade_callback(self, cb):
        self.trade_callbacks.append(cb)

    def _notify_trade(self, trade):
        for cb in self.trade_callbacks:
            cb(trade)

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
        self._notify_trade({'action': 'SELL', 'price': price, 'timestamp': timestamp.isoformat() if timestamp else None, 'reason': reason})
        if self.daily_pnl <= -self.daily_loss_limit:
            self.kill_switch_triggered = True
        return True

    def get_status(self):
        unrealised_pnl = 0
        # Convert trades to JSON-serializable format
        serializable_trades = []
        for t in self.trades[-20:]:
            entry_time_str = t["entry_time"] if isinstance(t["entry_time"], str) else t["entry_time"].strftime("%H:%M:%S")
            exit_time_str = t["exit_time"] if isinstance(t["exit_time"], str) else t["exit_time"].strftime("%H:%M:%S")
            serializable_trades.append({
                "entry_time": entry_time_str,
                "exit_time": exit_time_str,
                "entry_price": t["entry_price"],
                "exit_price": t["exit_price"],
                "pnl": t["pnl"],
                "reason": t["reason"]
            })
        # Convert open_positions to serializable dict
        open_positions_serializable = {}
        for k, v in self.positions.items():
            open_positions_serializable[k] = {
                "qty": v["qty"],
                "entry_price": v["entry_price"],
                "entry_time": v["entry_time"].isoformat() if v["entry_time"] else None
            }
        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': open_positions_serializable,
            'kill_switch': self.kill_switch_triggered,
            'trades': serializable_trades,
            'unrealised_pnl': unrealised_pnl
        }

# -------------------------------
# Heikin-Ashi Strategy (unchanged)
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

# -------------------------------
# Demo Mode Replay (unchanged)
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
    for _, row in df.iterrows():
        candle = {
            'timestamp': row['timestamp'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close']
        }
        strategy.on_candle_close(candle)
        time.sleep(0.03)
    print("Demo finished")

# -------------------------------
# Flask App – No Chart Dashboard
# -------------------------------
app = Flask(__name__)
CORS(app)

current_strategy = None
current_account = None
demo_thread = None

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Valkyrie Trader – No Chart</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial; margin: 20px; background: #1e1e2e; color: #ddd; }
        .container { max-width: 1400px; margin: auto; }
        .controls { background: #2d2d3a; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        button, select, input { padding: 8px 12px; border-radius: 6px; background: #1e1e2e; color: #ddd; border: 1px solid #00adb5; cursor: pointer; }
        button { background: #00adb5; color: #1e1e2e; font-weight: bold; }
        button.danger { background: #f05454; }
        button.kill { background: #aa2e2e; color: white; }
        .market-status { margin-left: auto; font-size: 14px; background: #1e1e2e; padding: 5px 12px; border-radius: 20px; }
        .status-badge { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
        .status-open { background: #00ff9d; box-shadow: 0 0 5px #00ff9d; }
        .status-closed { background: #ff6b6b; }
        .two-columns { display: flex; gap: 20px; margin-bottom: 20px; }
        .left-col, .right-col { flex: 1; min-width: 0; }
        .card { background: #2d2d3a; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .card h3 { margin-top: 0; color: #00adb5; font-size: 16px; border-bottom: 1px solid #00adb5; padding-bottom: 5px; }
        .balance-row { display: flex; justify-content: space-between; margin: 10px 0; }
        .balance-value { font-size: 24px; font-weight: bold; }
        .pnl-positive { color: #00ff9d; }
        .pnl-negative { color: #ff6b6b; }
        .loss-bar-container { width: 100%; background: #333; height: 8px; border-radius: 4px; margin: 8px 0; }
        .loss-bar { height: 8px; border-radius: 4px; background: #f05454; width: 0%; transition: width 0.3s; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        th { background: #3d3d4a; }
        .log { background: #2d2d3a; padding: 10px; height: 300px; overflow-y: auto; font-family: monospace; font-size: 11px; }
        .position-row { margin-bottom: 10px; padding: 8px; background: #1e1e2e; border-radius: 6px; }
        .close-btn { background: #f05454; color: white; border: none; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; }
        hr { border-color: #444; }
    </style>
</head>
<body>
<div class="container">
    <div class="controls">
        <input type="text" id="instrument" placeholder="Instrument Key" value="NSE_INDEX|NIFTY 50" size="30">
        <select id="strategy">
            <option value="heikin_ashi">Heikin-Ashi</option>
            <option value="future">Future Strategy</option>
        </select>
        <button id="startBtn">▶ START</button>
        <button id="stopBtn" class="danger">⏹ STOP</button>
        <button id="killBtn" class="kill">⚠ KILL SWITCH</button>
        <span id="modeLabel" style="background:#1e1e2e; padding:5px 12px; border-radius:20px;">Mode: PAPER</span>
        <div class="market-status">
            <span class="status-badge" id="marketBadge"></span>
            <span id="marketText">Checking...</span>
        </div>
    </div>

    <div class="two-columns">
        <!-- Left column: Balance & P&L, Open Positions -->
        <div class="left-col">
            <div class="card">
                <h3>💰 Balance & P&L</h3>
                <div class="balance-row">
                    <span>Balance:</span>
                    <span class="balance-value">₹<span id="balance">0</span></span>
                </div>
                <div class="balance-row">
                    <span>Daily Realised P&L:</span>
                    <span id="dailyPnl" class="balance-value">₹0</span>
                </div>
                <div class="balance-row">
                    <span>Unrealised P&L:</span>
                    <span id="unrealisedPnl" class="balance-value">₹0</span>
                </div>
                <div class="balance-row">
                    <span>Loss Limit: ₹20,000</span>
                    <span id="lossPercentText" style="font-size:12px;">0% used</span>
                </div>
                <div class="loss-bar-container">
                    <div class="loss-bar" id="lossBar"></div>
                </div>
                <div class="balance-row">
                    <span>Kill Switch:</span>
                    <span id="killSwitch" style="color:#f05454;">OFF</span>
                </div>
            </div>
            <div class="card">
                <h3>📊 Open Positions</h3>
                <div id="positionsPanel">None</div>
            </div>
        </div>

        <!-- Right column: Trade Log (as table) -->
        <div class="right-col">
            <div class="card">
                <h3>📋 Trade Log (last 20)</h3>
                <div style="overflow-x: auto;">
                    <table id="tradeTable">
                        <thead><tr><th>Entry Time</th><th>Exit Time</th><th>Reason</th><th>Entry Price</th><th>Exit Price</th><th>P&L (₹)</th><th>Instrument</th></tr></thead>
                        <tbody></tbody>
                    60
                </div>
            </div>
        </div>
    </div>

    <!-- Event Log (full width) -->
    <div class="card">
        <h3>📝 Event Log</h3>
        <div class="log" id="logPanel"></div>
    </div>
</div>

<script>
    let eventSource = null;
    let activeDemo = false;

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

    function updateStatus(data) {
        document.getElementById('balance').innerText = data.balance.toFixed(2);
        let pnlSpan = document.getElementById('dailyPnl');
        pnlSpan.innerText = '₹' + data.daily_pnl.toFixed(2);
        pnlSpan.className = (data.daily_pnl >= 0 ? 'pnl-positive' : 'pnl-negative') + ' balance-value';
        document.getElementById('unrealisedPnl').innerText = '₹' + (data.unrealised_pnl || 0).toFixed(2);
        document.getElementById('killSwitch').innerText = data.kill_switch ? 'ACTIVATED' : 'OFF';
        let lossPercent = Math.min(100, Math.max(0, (-data.daily_pnl / 20000) * 100));
        document.getElementById('lossBar').style.width = lossPercent + '%';
        document.getElementById('lossPercentText').innerText = lossPercent.toFixed(1) + '% used';
        // Open positions
        let posDiv = document.getElementById('positionsPanel');
        if (Object.keys(data.open_positions).length === 0) {
            posDiv.innerHTML = 'None';
        } else {
            let html = '';
            for (let [key, pos] of Object.entries(data.open_positions)) {
                html += `<div class="position-row">
                            <strong>${key}</strong> | Qty: ${pos.qty} | Entry: ₹${pos.entry_price.toFixed(2)}
                            <button class="close-btn" onclick="closePosition('${key}')">CLOSE</button>
                         </div>`;
            }
            posDiv.innerHTML = html;
        }
        // Trade table
        let tbody = document.querySelector('#tradeTable tbody');
        tbody.innerHTML = '';
        (data.trades || []).slice().reverse().forEach(t => {
            let row = `<tr>
                <td>${t.entry_time || ''}</td>
                <td>${t.exit_time || ''}</td>
                <td>${t.reason || ''}</td>
                <td>${t.entry_price.toFixed(2)}</td>
                <td>${t.exit_price.toFixed(2)}</td>
                <td class="${t.pnl>=0?'pnl-positive':'pnl-negative'}">${t.pnl.toFixed(2)}</td>
                <td>NIFTY CE</td>
            </tr>`;
            tbody.innerHTML += row;
        });
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
        addLog(`Manual close requested for ${instrumentKey} (demo: would send exit order)`);
    }

    function startBot() {
        if (activeDemo) {
            addLog('Bot already running. Stop first.');
            return;
        }
        let instr = document.getElementById('instrument').value;
        if (!instr) instr = 'NSE_INDEX|NIFTY 50';
        fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instrument_key: instr, mode: 'demo' })
        }).then(res => res.json()).then(data => {
            if (data.status === 'started') {
                activeDemo = true;
                document.getElementById('modeLabel').innerHTML = 'Mode: PAPER (DEMO)';
                addLog('Demo started');
                connectEventSource();
            } else if (data.error) {
                addLog('Error: ' + data.error);
            }
        }).catch(err => addLog('Fetch error: ' + err));
    }

    function stopBot() {
        if (!activeDemo) return;
        fetch('/stop', { method: 'POST' }).then(res => res.json()).then(() => {
            activeDemo = false;
            document.getElementById('modeLabel').innerHTML = 'Mode: PAPER (IDLE)';
            addLog('Bot stopped');
            if (eventSource) eventSource.close();
        });
    }

    function killSwitch() {
        fetch('/kill', { method: 'POST' }).then(res => res.json()).then(data => {
            addLog('Kill switch triggered via API');
            if (data.status === 'killed') {
                activeDemo = false;
                document.getElementById('modeLabel').innerHTML = 'Mode: KILLED';
                if (eventSource) eventSource.close();
            }
        }).catch(err => addLog('Kill switch error: ' + err));
    }

    function connectEventSource() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/stream');
        eventSource.onmessage = function(event) {
            let data = JSON.parse(event.data);
            if (data.type === 'status') updateStatus(data.data);
            else if (data.type === 'log') addLog(data.data);
        };
        eventSource.onerror = () => {
            addLog('SSE connection lost, reconnecting...');
            setTimeout(connectEventSource, 3000);
        };
    }

    document.getElementById('startBtn').onclick = startBot;
    document.getElementById('stopBtn').onclick = stopBot;
    document.getElementById('killBtn').onclick = killSwitch;

    window.onload = () => {
        fetch('/status').then(res => res.json()).then(updateStatus);
        addLog('No‑chart dashboard ready. Click START to begin demo.');
    };
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/start', methods=['POST'])
def start_bot():
    global current_strategy, current_account, demo_thread
    data = request.get_json()
    instrument_key = data.get('instrument_key')
    if not instrument_key:
        return jsonify({'error': 'instrument_key required'}), 400
    if current_strategy:
        return jsonify({'error': 'Bot already running'}), 400

    current_account = PaperAccount()
    current_strategy = HeikinAshiStrategy(current_account, instrument_key)

    def on_candle(candle):
        app.config['latest_candle'] = candle
    current_strategy.set_candle_callback(on_candle)

    def on_trade(trade):
        app.config['latest_trade'] = trade
    current_account.register_trade_callback(on_trade)

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
def stop_bot():
    global current_strategy, current_account, demo_thread
    current_strategy = None
    current_account = None
    demo_thread = None
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
            current_account.daily_pnl += 0
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
    return jsonify({'balance': 0, 'daily_pnl': 0, 'open_positions': {}, 'kill_switch': False, 'trades': [], 'unrealised_pnl': 0})

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
                    # Candle data not sent to frontend (no chart)
                trade = app.config.get('latest_trade')
                if trade and trade != last_trade:
                    last_trade = trade
                    # Simple log message without nested f-string issues
                    log_msg = f"Trade: {trade['action']} @ {trade['price']}"
                    yield f"data: {json.dumps({'type': 'log', 'data': log_msg})}\n\n"
            time.sleep(0.3)
    return app.response_class(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.config['latest_candle'] = None
    app.config['latest_trade'] = None
    app.run(debug=True, port=8080)
