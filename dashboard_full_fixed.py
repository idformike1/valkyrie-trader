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
        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': len(self.positions),
            'kill_switch': self.kill_switch_triggered,
            'trades': self.trades[-20:]
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
# Flask App with Fixed Frontend
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
    <title>Valkyrie Trader - Fixed Frontend</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial; margin: 20px; background: #1e1e2e; color: #ddd; }
        .container { max-width: 1600px; margin: auto; }
        .controls { background: #2d2d3a; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        button, select, input { padding: 8px 12px; border-radius: 6px; background: #1e1e2e; color: #ddd; border: 1px solid #00adb5; cursor: pointer; }
        button { background: #00adb5; color: #1e1e2e; font-weight: bold; }
        button.danger { background: #f05454; }
        .toggle-group { display: flex; align-items: center; gap: 8px; background: #1e1e2e; padding: 5px 12px; border-radius: 20px; }
        #chart { width: 100%; height: 550px; margin-bottom: 20px; background: #1e1e2e; border-radius: 8px; }
        .two-columns { display: flex; gap: 20px; margin-bottom: 20px; }
        .left-col { flex: 1; min-width: 0; }
        .right-col { flex: 1; min-width: 0; }
        .card { background: #2d2d3a; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .card h3 { margin-top: 0; color: #00adb5; font-size: 16px; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        th { background: #3d3d4a; }
        .log { background: #2d2d3a; padding: 10px; height: 300px; overflow-y: auto; font-family: monospace; font-size: 11px; }
        .loss-bar-container { width: 100%; background: #333; height: 8px; border-radius: 4px; margin: 8px 0; }
        .loss-bar { height: 8px; border-radius: 4px; background: #f05454; width: 0%; transition: width 0.3s; }
        .loss-percent { font-size: 11px; color: #f05454; }
        .status-panel { display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 20px; }
        .status-card { background: #2d2d3a; padding: 12px; border-radius: 8px; flex: 1; min-width: 120px; text-align: center; }
        .status-card .value { font-size: 20px; font-weight: bold; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
</head>
<body>
<div class="container">
    <h1>⚡ Valkyrie Trader (Fixed Frontend)</h1>
    <div class="controls">
        <input type="text" id="instrument" placeholder="Instrument" value="NSE_INDEX|NIFTY 50" size="30">
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
            <input type="checkbox" id="haToggle">
        </div>
        <span id="modeLabel">Mode: Idle</span>
    </div>
    <div id="chart"></div>
    <div class="status-panel">
        <div class="status-card"><div>Balance</div><div class="value">₹<span id="balance">0</span></div></div>
        <div class="status-card"><div>Daily P&L</div><div class="value" id="dailyPnlVal">0</div>
            <div class="loss-bar-container"><div class="loss-bar" id="lossBar"></div></div>
            <div class="loss-percent" id="lossPercent">0% of limit</div>
        </div>
        <div class="status-card"><div>Kill Switch</div><div><span id="killSwitch">OFF</span></div></div>
        <div class="status-card"><div>Open Positions</div><div id="positions">None</div></div>
    </div>
    <div class="two-columns">
        <div class="left-col">
            <div class="card"><h3>Trade Log (last 20)</h3>
                <table id="tradeTable"><thead><tr><th>Exit Time</th><th>Reason</th><th>Exit Price</th><th>P&L (₹)</th><th>Entry Price</th></tr></thead><tbody></tbody>能有
            </div>
        </div>
        <div class="right-col">
            <div class="card"><h3>Event Log</h3><div class="log" id="logPanel"></div></div>
        </div>
    </div>
</div>
<script>
    let chart = null;
    let rawCandles = [];        // store {x, open, high, low, close, volume}
    let annotations = [];
    let entryPriceLine = null;
    let eventSource = null;
    let useHeikinAshi = false;
    let activeDemo = false;     // prevent multiple concurrent demos

    // ----- Helper: compute Heikin-Ashi from raw candles (client-side) -----
    function computeHeikinAshi(candles) {
        if (candles.length === 0) return [];
        let result = [];
        let prevHAOpen = null;
        let prevHAClose = null;
        for (let i = 0; i < candles.length; i++) {
            let c = candles[i];
            let haClose = (c.open + c.high + c.low + c.close) / 4;
            let haOpen = (i === 0) ? c.open : (prevHAOpen + prevHAClose) / 2;
            let haHigh = Math.max(c.high, haOpen, haClose);
            let haLow = Math.min(c.low, haOpen, haClose);
            result.push({
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
        return result;
    }

    // ----- Resample candles by minutes (timezone-safe using UTC timestamps) -----
    function resampleCandles(candles, minutes) {
        if (minutes <= 1) return candles;
        const groups = new Map();
        for (let c of candles) {
            // Convert timestamp to UTC date to avoid timezone shifts
            let d = new Date(c.x);
            let year = d.getUTCFullYear();
            let month = d.getUTCMonth();
            let day = d.getUTCDate();
            let hour = d.getUTCHours();
            let minute = Math.floor(d.getUTCMinutes() / minutes) * minutes;
            let bucket = Date.UTC(year, month, day, hour, minute, 0, 0);
            if (!groups.has(bucket)) {
                groups.set(bucket, {
                    x: bucket,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                    volume: c.volume
                });
            } else {
                let grp = groups.get(bucket);
                grp.high = Math.max(grp.high, c.high);
                grp.low = Math.min(grp.low, c.low);
                grp.close = c.close;
                grp.volume += c.volume;
            }
        }
        return Array.from(groups.values()).sort((a,b) => a.x - b.x);
    }

    // ----- Get current display candles (raw or HA) after resampling -----
    function getDisplayCandles() {
        let base = useHeikinAshi ? computeHeikinAshi(rawCandles) : rawCandles.slice();
        let tf = parseInt(document.getElementById('timeframe').value);
        return resampleCandles(base, tf);
    }

    // ----- Update chart (candlestick + volume bars) -----
    function updateChart() {
        if (!chart) return;
        let display = getDisplayCandles();
        let seriesData = display.map(c => ({ x: c.x, y: [c.open, c.high, c.low, c.close] }));
        let volumeData = display.map(c => ({ x: c.x, y: c.volume }));
        chart.updateOptions({
            series: [
                { name: 'Candles', data: seriesData, type: 'candlestick' },
                { name: 'Volume', data: volumeData, type: 'bar' }
            ]
        });
        chart.updateOptions({ annotations: { yaxis: entryPriceLine ? [entryPriceLine] : [], points: annotations } });
    }

    function addRawCandle(candle) {
        // deduplicate by timestamp (millisecond precision)
        let ts = new Date(candle.timestamp).getTime();
        if (rawCandles.some(c => c.x === ts)) return;
        rawCandles.push({
            x: ts,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
            volume: candle.volume || 1000
        });
        // keep last 500 candles for performance
        if (rawCandles.length > 500) rawCandles.shift();
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

function initChart() {
    let options = {
        series: [{ name: "Candles", data: [] }],
        chart: { type: "candlestick", height: 550, background: "#1e1e2e", foreColor: "#ddd", animations: { enabled: false }, zoom: { enabled: true }, toolbar: { show: true } },
        title: { text: "Price Chart", align: "left", style: { color: "#ddd" } },
        xaxis: { type: "datetime", labels: { datetimeUTC: true, format: "HH:mm" }, tickAmount: 12 },
        yaxis: { title: { text: "Price" }, labels: { formatter: (val) => val.toFixed(2) } },
        plotOptions: { candlestick: { colors: { upward: "#00ff9d", downward: "#ff6b6b" } } },
        grid: { borderColor: "#333" },
        annotations: { points: [], yaxis: [] },
        tooltip: { x: { format: "HH:mm:ss" } }
    };
    if (chart) chart.destroy();
    chart = new ApexCharts(document.querySelector("#chart"), options);
    chart.render();
}


    function resetChartData() {
        rawCandles = [];
        annotations = [];
        entryPriceLine = null;
        if (chart) {
            chart.updateSeries([{ name: 'Candles', data: [] }, { name: 'Volume', data: [] }]);
            chart.updateOptions({ annotations: { points: [], yaxis: [] } });
        }
    }

    function updateStatus(data) {
        document.getElementById('balance').innerText = data.balance.toFixed(2);
        let pnlSpan = document.getElementById('dailyPnlVal');
        pnlSpan.innerText = data.daily_pnl.toFixed(2);
        pnlSpan.style.color = data.daily_pnl >= 0 ? '#00ff9d' : '#ff6b6b';
        document.getElementById('killSwitch').innerText = data.kill_switch ? 'ACTIVATED' : 'OFF';
        document.getElementById('positions').innerHTML = data.open_positions ? `${data.open_positions} position(s)` : 'None';
        let lossPercent = Math.min(100, Math.max(0, (-data.daily_pnl / 20000) * 100));
        document.getElementById('lossBar').style.width = lossPercent + '%';
        document.getElementById('lossPercent').innerText = `${lossPercent.toFixed(1)}% of ₹20k limit`;
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
        if (logDiv.children.length > 100) logDiv.removeChild(logDiv.children[0]);
    }

    function startDemo() {
        if (activeDemo) {
            addLog('⚠️ Demo already running. Stop first or wait.');
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
                document.getElementById('modeLabel').innerText = 'Mode: DEMO';
                addLog('Demo mode started');
                initChart();
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
            document.getElementById('modeLabel').innerText = 'Mode: Idle';
            addLog('Bot stopped');
            if (eventSource) eventSource.close();
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
        eventSource.onerror = () => {
            addLog('SSE connection lost, reconnecting...');
            setTimeout(connectEventSource, 3000);
        };
    }

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
        addLog('Fixed frontend ready. Click DEMO to start.');
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
