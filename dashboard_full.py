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
# Paper Trading Account (with trade callbacks)
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
        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': len(self.positions),
            'kill_switch': self.kill_switch_triggered,
            'trades': self.trades[-20:]
        }

# -------------------------------
# Heikin-Ashi Strategy (same as before)
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
    # Store volume if exists, else default to 1000
    if 'volume' not in df.columns:
        df['volume'] = 1000
    app.config['full_historical'] = df.to_dict('records')
    print(f"Demo replay: {len(df)} candles")
    for _, row in df.iterrows():
        candle = {
            'timestamp': row['timestamp'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row.get('volume', 1000)
        }
        strategy.on_candle_close(candle)
        time.sleep(0.03)
    print("Demo finished")

# -------------------------------
# Flask App with Full Dashboard
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
    <title>Valkyrie Trader - Full Features</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #1e1e1e; color: #ddd; }
        .container { max-width: 1600px; margin: auto; }
        .controls { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        button, select, input { padding: 8px 12px; border-radius: 4px; background: #1e1e1e; color: #ddd; border: 1px solid #00adb5; cursor: pointer; }
        button { background: #00adb5; color: #1e1e1e; font-weight: bold; }
        button.danger { background: #f05454; }
        .toggle-group { display: flex; align-items: center; gap: 10px; }
        #chart { width: 100%; height: 600px; margin-bottom: 20px; }
        .status-panel { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
        .card { background: #2d2d2d; padding: 15px; border-radius: 8px; flex: 1; min-width: 150px; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        th { background: #3d3d3d; }
        .log { background: #2d2d2d; padding: 10px; height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; margin-top: 20px; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
</head>
<body>
<div class="container">
    <h1>⚡ Valkyrie Trader (Full Features)</h1>
    <div class="controls">
        <input type="text" id="instrument" placeholder="Instrument Key" value="NSE_INDEX|NIFTY 50" size="30">
        <button id="demoBtn">▶ DEMO</button>
        <button id="stopBtn" class="danger">⏹ STOP</button>
        <select id="timeframe">
            <option value="1">1 min</option>
            <option value="5">5 min</option>
            <option value="15">15 min</option>
            <option value="60">1 hour</option>
        </select>
        <div class="toggle-group">
            <span>Heikin-Ashi</span>
            <label><input type="checkbox" id="haToggle"> Show HA candles</label>
        </div>
        <span id="modeLabel">Mode: Idle</span>
    </div>
    <div id="chart"></div>
    <div class="status-panel">
        <div class="card"><h3>Balance</h3><div>₹<span id="balance">0</span></div></div>
        <div class="card"><h3>Daily P&L</h3><div>₹<span id="dailyPnl">0</span></div>
            <div style="font-size:10px;">Loss limit: -₹20,000</div>
            <div style="width:100%; background:#333; height:4px; margin-top:5px;">
                <div id="lossBar" style="width:0%; background:#f05454; height:4px;"></div>
            </div>
        </div>
        <div class="card"><h3>Kill Switch</h3><div><span id="killSwitch">OFF</span></div></div>
        <div class="card"><h3>Open Positions</h3><div id="positions">None</div></div>
    </div>
    <div class="card"><h3>Trade Log (last 20)</h3>
        <table id="tradeTable"><thead><tr><th>Exit Time</th><th>Reason</th><th>Exit Price</th><th>P&L (₹)</th><th>Entry Price</th></tr></thead><tbody></tbody>能有</div>
    <div class="log" id="logPanel"></div>
</div>
<script>
    let chart = null;
    let rawCandles = [];      // store raw OHLCV objects as they arrive
    let displayCandles = [];   // current series data (raw or HA)
    let annotations = [];
    let entryPriceLine = null;
    let eventSource = null;
    let useHeikinAshi = false;
    let allHistorical = [];     // pre-loaded full historical data (for resampling)

    // Heikin-Ashi transformation (client-side)
    function computeHeikinAshi(candles) {
        if (candles.length === 0) return [];
        let ha = [];
        let prevHAOpen = null;
        let prevHAClose = null;
        for (let i = 0; i < candles.length; i++) {
            let c = candles[i];
            let haClose = (c.open + c.high + c.low + c.close) / 4;
            let haOpen = (i === 0) ? c.open : (prevHAOpen + prevHAClose) / 2;
            let haHigh = Math.max(c.high, haOpen, haClose);
            let haLow = Math.min(c.low, haOpen, haClose);
            ha.push({
                x: c.x,
                open: haOpen,
                high: haHigh,
                low: haLow,
                close: haClose,
                volume: c.volume
            });
            prevHAOpen = haOpen;
            prevHAClose = haClose;
        }
        return ha;
    }

    // Resample candles to higher timeframe (minutes)
    function resampleCandles(candles, minutes) {
        if (minutes <= 1) return candles;
        let groups = {};
        for (let c of candles) {
            let date = new Date(c.x);
            let bucket = new Date(date);
            bucket.setMinutes(Math.floor(date.getMinutes() / minutes) * minutes);
            bucket.setSeconds(0, 0);
            let key = bucket.getTime();
            if (!groups[key]) {
                groups[key] = {
                    x: key,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume
                };
            } else {
                groups[key].high = Math.max(groups[key].high, c.high);
                groups[key].low = Math.min(groups[key].low, c.low);
                groups[key].close = c.close;
                groups[key].volume += c.volume;
            }
        }
        return Object.values(groups).sort((a,b) => a.x - b.x);
    }

    // Get current candles (raw or HA) after resampling
    function getDisplayCandles() {
        let base = useHeikinAshi ? computeHeikinAshi(rawCandles) : rawCandles.slice();
        let tf = parseInt(document.getElementById('timeframe').value);
        let resampled = resampleCandles(base, tf);
        return resampled;
    }

    // Update chart series and annotations
    function updateChart() {
        if (!chart) return;
        let display = getDisplayCandles();
        // convert to series format {x, y: [open, high, low, close]}
        let seriesData = display.map(c => ({ x: c.x, y: [c.open, c.high, c.low, c.close] }));
        chart.updateSeries([{ name: 'Candles', data: seriesData }]);
        // Update volume series if present (we'll add a second series later – for simplicity, skip volume now)
        // Update annotations
        chart.updateOptions({ annotations: { yaxis: entryPriceLine ? [entryPriceLine] : [], points: annotations } });
    }

    function addRawCandle(candle) {
        rawCandles.push({
            x: new Date(candle.timestamp).getTime(),
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
            volume: candle.volume || 1000
        });
        if (rawCandles.length > 1000) rawCandles.shift();
        updateChart();
    }

    function addTradeMarker(trade) {
        let color = trade.action === 'BUY' ? '#00ff9d' : '#ff6b6b';
        let shape = trade.action === 'BUY' ? 'circle' : 'square';
        annotations.push({
            x: new Date(trade.timestamp).getTime(),
            y: trade.price,
            marker: { size: 8, fillColor: color, strokeColor: color, shape: shape },
            label: { text: trade.action, style: { color: '#fff', background: color } }
        });
        if (annotations.length > 30) annotations.shift();
        if (trade.action === 'BUY') {
            entryPriceLine = {
                y: trade.price,
                yaxis: 'left',
                borderColor: '#ffcc00',
                strokeDashArray: 4,
                label: { text: `Entry ₹${trade.price.toFixed(2)}`, style: { color: '#ffcc00', background: '#333' } }
            };
        } else if (trade.action === 'SELL') {
            entryPriceLine = null;
        }
        updateChart();
    }

    // Initialize chart with candlestick + volume (dual axis)
    function initChart() {
        let options = {
            series: [{ name: 'Candles', data: [] }],
            chart: { type: 'candlestick', height: 600, background: '#1e1e1e', foreColor: '#ddd', animations: { enabled: false }, zoom: { enabled: true }, toolbar: { show: true } },
            title: { text: 'Price Chart', align: 'left', style: { color: '#ddd' } },
            xaxis: { type: 'datetime', labels: { datetimeUTC: false }, tickAmount: 12 },
            yaxis: { labels: { formatter: (val) => val.toFixed(2) } },
            plotOptions: { candlestick: { colors: { upward: '#00ff9d', downward: '#ff6b6b' } } },
            grid: { borderColor: '#333' },
            annotations: { points: [], yaxis: [] },
            tooltip: { x: { format: 'HH:mm:ss' } }
        };
        chart = new ApexCharts(document.querySelector("#chart"), options);
        chart.render();
    }

    function resetChartData() {
        rawCandles = [];
        annotations = [];
        entryPriceLine = null;
        updateChart();
    }

    function updateStatus(data) {
        document.getElementById('balance').innerText = data.balance.toFixed(2);
        document.getElementById('dailyPnl').innerText = data.daily_pnl.toFixed(2);
        document.getElementById('killSwitch').innerText = data.kill_switch ? 'ACTIVATED' : 'OFF';
        document.getElementById('positions').innerHTML = data.open_positions ? `${data.open_positions} position(s)` : 'None';
        // loss bar percentage (0% = no loss, 100% = reached limit)
        let lossPercent = Math.min(100, Math.max(0, (-data.daily_pnl / 20000) * 100));
        document.getElementById('lossBar').style.width = lossPercent + '%';
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
            if (data.status === 'started') {
                document.getElementById('modeLabel').innerText = 'Mode: DEMO';
                addLog('Demo mode started');
                if (chart) chart.destroy();
                initChart();
                connectEventSource();
            } else if (data.error) {
                addLog('Error: ' + data.error);
            }
        }).catch(err => console.error(err));
    }

    function stopBot() {
        fetch('/stop', { method: 'POST' }).then(res => res.json()).then(() => {
            document.getElementById('modeLabel').innerText = 'Mode: Idle';
            addLog('Bot stopped');
            if (eventSource) eventSource.close();
            // Clear chart data without destroying chart
            resetChartData();
        });
    }

    function connectEventSource() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/stream');
        eventSource.onmessage = function(event) {
            let data = JSON.parse(event.data);
            if (data.type === 'status') updateStatus(data.data);
            else if (data.type === 'candle') addRawCandle(data.data);
            else if (data.type === 'trade') addTradeMarker(data.data);
            else if (data.type === 'log') addLog(data.data);
        };
        eventSource.onerror = () => setTimeout(connectEventSource, 3000);
    }

    // Event listeners
    document.getElementById('demoBtn').onclick = startDemo;
    document.getElementById('stopBtn').onclick = stopBot;
    document.getElementById('timeframe').onchange = () => updateChart();
    document.getElementById('haToggle').onchange = (e) => {
        useHeikinAshi = e.target.checked;
        updateChart();
        addLog(`Heikin-Ashi mode ${useHeikinAshi ? 'ON' : 'OFF'}`);
    };

    window.onload = () => {
        fetch('/status').then(res => res.json()).then(updateStatus);
        addLog('Full-feature dashboard ready. Click DEMO to start.');
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
        # Ensure volume exists
        if 'volume' not in candle:
            candle['volume'] = 1000
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

@app.route('/status')
def status():
    if current_account:
        return jsonify(current_account.get_status())
    return jsonify({'balance': 0, 'daily_pnl': 0, 'open_positions': 0, 'kill_switch': False, 'trades': []})

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
                    candle_copy = candle.copy()
                    candle_copy['timestamp'] = candle_copy['timestamp'].isoformat()
                    yield f"data: {json.dumps({'type': 'candle', 'data': candle_copy})}\n\n"
                trade = app.config.get('latest_trade')
                if trade and trade != last_trade:
                    last_trade = trade
                    yield f"data: {json.dumps({'type': 'trade', 'data': trade})}\n\n"
            time.sleep(0.3)
    return app.response_class(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.config['latest_candle'] = None
    app.config['latest_trade'] = None
    app.run(debug=True, port=8080)
