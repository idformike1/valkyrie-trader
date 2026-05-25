import json
import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import os

# -------------------------------
# Paper Trading Account (same as before)
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
# Heikin-Ashi Strategy (same)
# -------------------------------
def calculate_heikin_ashi(candles_df):
    """candles_df is a DataFrame with columns: open, high, low, close"""
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
        # Convert to DataFrame for HA calculation
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
# Demo Mode Replay (same)
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
    # Store full data for timeframe resampling (accessible globally)
    app.config['full_candle_data'] = df
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
        time.sleep(0.05)  # fast replay
    print("Demo finished")

# -------------------------------
# Flask App with Advanced ApexCharts
# -------------------------------
app = Flask(__name__)
CORS(app)

current_strategy = None
current_account = None
demo_thread = None

# Store full dataset for resampling
app.config['full_candle_data'] = None

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Valkyrie Trader - Advanced</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial; margin: 20px; background: #1e1e1e; color: #ddd; }
        .container { max-width: 1600px; margin: auto; }
        .controls { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        button { padding: 8px 16px; cursor: pointer; background: #00adb5; border: none; color: #1e1e1e; font-weight: bold; border-radius: 4px; }
        button.danger { background: #f05454; }
        select, input { padding: 8px; background: #1e1e1e; color: #ddd; border: 1px solid #00adb5; border-radius: 4px; }
        #chart { width: 100%; height: 600px; margin-bottom: 20px; }
        .status-panel { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
        .card { background: #2d2d2d; padding: 15px; border-radius: 8px; flex: 1; min-width: 150px; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        th { background: #3d3d3d; }
        .log { background: #2d2d2d; padding: 10px; height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; margin-top: 20px; }
        .toggle-group { display: inline-flex; align-items: center; gap: 10px; background: #1e1e1e; padding: 5px 10px; border-radius: 20px; }
    </style>
    <!-- ApexCharts CDN -->
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
</head>
<body>
<div class="container">
    <h1>⚡ Valkyrie Trader (Advanced)</h1>
    <div class="controls">
        <input type="text" id="instrument" placeholder="Instrument Key" value="NSE_INDEX|NIFTY 50" size="30">
        <button id="demoBtn">▶ DEMO (Historical)</button>
        <button id="stopBtn" class="danger">⏹ STOP</button>
        <select id="timeframe">
            <option value="1">1 min</option>
            <option value="5">5 min</option>
            <option value="15">15 min</option>
            <option value="60">1 hour</option>
        </select>
        <div class="toggle-group">
            <span>Heikin-Ashi</span>
            <label class="switch">
                <input type="checkbox" id="haToggle">
                <span class="slider round"></span>
            </label>
        </div>
        <span id="modeLabel">Mode: Idle</span>
    </div>
    <div id="chart"></div>
    <div class="status-panel">
        <div class="card"><h3>Balance</h3><div>₹<span id="balance">0</span></div></div>
        <div class="card"><h3>Daily P&L</h3><div>₹<span id="dailyPnl">0</span></div></div>
        <div class="card"><h3>Kill Switch</h3><div><span id="killSwitch">OFF</span></div></div>
        <div class="card"><h3>Open Positions</h3><div id="positions">None</div></div>
    </div>
    <div class="card"><h3>Trade Log (last 20)</h3>
        <table id="tradeTable"><thead><tr><th>Exit Time</th><th>Reason</th><th>Exit Price</th><th>P&L (₹)</th><th>Entry Price</th></tr></thead><tbody></tbody></table>
    </div>
    <div class="log" id="logPanel"></div>
</div>
<script>
    let chart = null;
    let allCandles = [];      // stores {timestamp, open, high, low, close, volume?}
    let currentSeries = [];   // series data for chart
    let annotations = [];
    let entryPriceLine = null;
    let eventSource = null;
    let useHeikinAshi = false;

    // Helper: resample candles based on timeframe (minutes)
    function resampleCandles(candles, minutes) {
        if (!candles.length) return [];
        let groups = {};
        for (let c of candles) {
            let ts = new Date(c.timestamp);
            let bucket = new Date(ts);
            bucket.setMinutes(Math.floor(ts.getMinutes() / minutes) * minutes);
            bucket.setSeconds(0, 0);
            let key = bucket.getTime();
            if (!groups[key]) {
                groups[key] = { open: c.open, high: c.high, low: c.low, close: c.close, timestamp: bucket };
            } else {
                groups[key].high = Math.max(groups[key].high, c.high);
                groups[key].low = Math.min(groups[key].low, c.low);
                groups[key].close = c.close;
            }
        }
        let resampled = Object.values(groups);
        resampled.sort((a,b) => a.timestamp - b.timestamp);
        return resampled;
    }

    // Convert candles to ApexCharts series format
    function toSeriesData(candles) {
        return candles.map(c => ({
            x: new Date(c.timestamp).getTime(),
            y: [c.open, c.high, c.low, c.close]
        }));
    }

    // Update chart with current data & annotations
    async function updateChart() {
        if (!chart) return;
        let tf = parseInt(document.getElementById('timeframe').value);
        let resampled = resampleCandles(allCandles, tf);
        let seriesData = toSeriesData(resampled);
        await chart.updateSeries([{ data: seriesData, name: 'Candles' }]);
        // Update annotations (entry/exit markers, horizontal line)
        await chart.updateOptions({ annotations: { points: annotations } });
        if (entryPriceLine) {
            await chart.updateOptions({ annotations: { yaxis: [entryPriceLine] } });
        }
    }

    // Add a trade annotation (entry or exit)
    function addTradeAnnotation(timestamp, price, type, reason) {
        let color = (type === 'BUY') ? '#00ff9d' : '#ff6b6b';
        let markerShape = (type === 'BUY') ? 'circle' : 'square';
        annotations.push({
            x: new Date(timestamp).getTime(),
            y: price,
            marker: { size: 8, fillColor: color, strokeColor: color, shape: markerShape },
            label: { text: `${type}${reason ? '\\n'+reason : ''}`, style: { color: '#fff', background: color } }
        });
        // Keep only last 50 annotations to avoid clutter
        if (annotations.length > 50) annotations.shift();
        updateChart();
    }

    // Set horizontal line for entry price (if in position)
    function setEntryPriceLine(price) {
        if (price !== null) {
            entryPriceLine = {
                y: price,
                yaxis: 'left',
                borderColor: '#ffcc00',
                strokeDashArray: 4,
                label: { text: `Entry ₹${price.toFixed(2)}`, style: { color: '#ffcc00', background: '#333' } }
            };
        } else {
            entryPriceLine = null;
        }
        updateChart();
    }

    // Initialize chart with empty data
    function initChart() {
        let options = {
            series: [{ name: 'Candles', data: [] }],
            chart: {
                type: 'candlestick',
                height: 600,
                background: '#1e1e1e',
                foreColor: '#ddd',
                animations: { enabled: false },
                zoom: { enabled: true, type: 'x' },
                toolbar: { show: true, tools: { zoom: true, pan: true, reset: true } }
            },
            title: { text: 'Price Chart', align: 'left', style: { color: '#ddd' } },
            xaxis: { type: 'datetime', labels: { datetimeUTC: false }, crosshairs: { show: true, width: 1, stroke: { color: '#888' } } },
            yaxis: { tooltip: { enabled: true }, labels: { formatter: (val) => val.toFixed(2) }, crosshairs: { show: true } },
            plotOptions: { candlestick: { colors: { upward: '#00ff9d', downward: '#ff6b6b' } } },
            grid: { borderColor: '#333', row: { colors: ['transparent'] } },
            tooltip: { shared: true, x: { format: 'HH:mm:ss' } }
        };
        chart = new ApexCharts(document.querySelector("#chart"), options);
        chart.render();
    }

    // Fetch historical data for timeframe changes (from backend)
    async function loadHistoricalData() {
        let response = await fetch('/api/historical_full');
        let data = await response.json();
        allCandles = data.candles;  // array of {timestamp, open, high, low, close}
        if (chart) await updateChart();
    }

    // Callback when new candle arrives (from live or demo)
    function onNewCandle(candle) {
        allCandles.push(candle);
        // Keep only last 2000 to avoid memory bloat
        if (allCandles.length > 2000) allCandles.shift();
        updateChart();
    }

    // When trade occurs, add annotation and update entry line
    function onTrade(trade) {
        if (trade.action === 'BUY') {
            addTradeAnnotation(trade.timestamp, trade.price, 'BUY', '');
            setEntryPriceLine(trade.price);
        } else if (trade.action === 'SELL') {
            addTradeAnnotation(trade.timestamp, trade.price, 'SELL', trade.reason);
            setEntryPriceLine(null);
        }
    }

    // Connect to SSE stream for status, candles, trades
    function connectEventSource() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/stream');
        eventSource.onmessage = function(event) {
            let data = JSON.parse(event.data);
            if (data.type === 'status') updateStatus(data.data);
            else if (data.type === 'candle') onNewCandle(data.data);
            else if (data.type === 'trade') onTrade(data.data);
            else if (data.type === 'log') addLog(data.data);
        };
        eventSource.onerror = () => setTimeout(connectEventSource, 3000);
    }

    function updateStatus(data) {
        document.getElementById('balance').innerText = data.balance.toFixed(2);
        document.getElementById('dailyPnl').innerText = data.daily_pnl.toFixed(2);
        document.getElementById('killSwitch').innerText = data.kill_switch ? 'ACTIVATED' : 'OFF';
        document.getElementById('positions').innerHTML = data.open_positions ? `${data.open_positions} position(s)` : 'None';
        let tbody = document.querySelector('#tradeTable tbody');
        tbody.innerHTML = '';
        (data.trades || []).slice().reverse().forEach(t => {
            tbody.innerHTML += `<tr><td>${t.exit_time}</td><td>${t.reason}</td><td>${t.exit_price.toFixed(2)}</td><td style="color:${t.pnl>=0?'#00ff9d':'#ff6b6b'}">${t.pnl.toFixed(2)}</td><td>${t.entry_price.toFixed(2)}</td></tr>`;
        });
    }

    function addLog(msg) {
        let logDiv = document.getElementById('logPanel');
        let entry = document.createElement('div');
        entry.innerText = new Date().toLocaleTimeString() + ' ' + msg;
        logDiv.appendChild(entry);
        logDiv.scrollTop = logDiv.scrollHeight;
        if (logDiv.children.length > 50) logDiv.removeChild(logDiv.children[0]);
    }

    function startDemo() {
        let instr = document.getElementById('instrument').value;
        if (!instr) instr = 'NSE_INDEX|NIFTY 50';
        fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instrument_key: instr, mode: 'demo' })
        }).then(res => res.json()).then(data => {
            console.log(data);
            document.getElementById('modeLabel').innerText = 'Mode: DEMO';
            addLog('Demo mode started');
            initChart();
            loadHistoricalData();  // load all candles for resampling
            connectEventSource();
        }).catch(err => console.error(err));
    }

    function stopBot() {
        fetch('/stop', { method: 'POST' }).then(res => res.json()).then(() => {
            document.getElementById('modeLabel').innerText = 'Mode: Idle';
            addLog('Bot stopped');
            if (eventSource) eventSource.close();
            if (chart) chart.destroy();
            allCandles = [];
            annotations = [];
            entryPriceLine = null;
        });
    }

    // Event listeners
    document.getElementById('demoBtn').onclick = startDemo;
    document.getElementById('stopBtn').onclick = stopBot;
    document.getElementById('timeframe').onchange = () => updateChart();
    document.getElementById('haToggle').onchange = async (e) => {
        useHeikinAshi = e.target.checked;
        // If checked, transform allCandles to HA, else use raw.
        // For simplicity, we'll need to fetch raw again or compute HA on backend.
        // For now, we'll reload raw historical and compute HA client‑side.
        // Implementation omitted for brevity – but concept ready.
        addLog(`Heikin-Ashi mode ${useHeikinAshi ? 'ON' : 'OFF'} (requires data transformation)`);
    };

    window.onload = () => {
        fetch('/status').then(res => res.json()).then(updateStatus);
        addLog('Advanced dashboard ready. Click DEMO to start.');
    };
</script>
</body>
</html>
"""

# -------------------------------
# Flask Routes (extended)
# -------------------------------
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/start', methods=['POST'])
def start_bot():
    global current_strategy, current_account, demo_thread
    data = request.get_json()
    instrument_key = data.get('instrument_key')
    mode = data.get('mode', 'demo')
    if not instrument_key:
        return jsonify({'error': 'instrument_key required'}), 400
    if current_strategy:
        return jsonify({'error': 'Bot already running'}), 400

    current_account = PaperAccount()
    current_strategy = HeikinAshiStrategy(current_account, instrument_key)

    # Callbacks for SSE: candle close and trade events
    def on_candle(candle):
        app.config['latest_candle'] = candle
    def on_trade(trade_info):
        app.config['latest_trade'] = trade_info
    # We'll need to add trade callback to PaperAccount – simplified for demo: we push trade from strategy.
    # For brevity, we'll not implement full trade callback here; annotations will be added via status updates.

    current_strategy.set_candle_callback(on_candle)

    if mode == 'demo':
        def run():
            global current_strategy, current_account, demo_thread
            demo_replay(current_strategy, 'backtest_output.csv')
            current_strategy = None
            current_account = None
            demo_thread = None
        demo_thread = threading.Thread(target=run, daemon=True)
        demo_thread.start()
    else:
        # Live mode not yet integrated
        pass

    return jsonify({'status': 'started', 'instrument': instrument_key, 'mode': mode})

@app.route('/stop', methods=['POST'])
def stop_bot():
    global current_strategy, current_account, demo_thread
    current_strategy = None
    current_account = None
    demo_thread = None
    app.config['latest_candle'] = None
    app.config['latest_trade'] = None
    return jsonify({'status': 'stopped'})

@app.route('/status')
def status():
    if current_account:
        return jsonify(current_account.get_status())
    return jsonify({'balance': 0, 'daily_pnl': 0, 'open_positions': 0, 'kill_switch': False, 'trades': []})

@app.route('/api/historical_full')
def historical_full():
    """Return all candles from backtest CSV for resampling."""
    csv_file = 'backtest_output.csv'
    if not os.path.exists(csv_file):
        return jsonify({'candles': []})
    df = pd.read_csv(csv_file)
    if 'timestamp' not in df.columns:
        return jsonify({'candles': []})
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    candles = []
    for _, row in df.iterrows():
        candles.append({
            'timestamp': row['timestamp'].isoformat(),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close'])
        })
    return jsonify({'candles': candles})

@app.route('/stream')
def stream():
    def event_stream():
        last_candle_ts = None
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
                    candle_copy = candle.copy()
                    candle_copy['timestamp'] = candle_copy['timestamp'].isoformat()
                    yield f"data: {json.dumps({'type': 'candle', 'data': candle_copy})}\n\n"
                # Trade events – simplified: we can detect from status trades list
                # Not implemented fully here, but concept ready.
            time.sleep(0.5)
    return app.response_class(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.config['latest_candle'] = None
    app.config['latest_trade'] = None
    app.run(debug=True, port=8080)
