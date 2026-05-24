import json
import asyncio
import websockets
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from collections import deque
import threading
import time

# -------------------------------
# Load access token
# -------------------------------
TOKEN_FILE = "token.txt"
if not os.path.exists(TOKEN_FILE):
    print("❌ token.txt not found. Run auth.py first.")
    sys.exit(1)

with open(TOKEN_FILE, "r") as f:
    ACCESS_TOKEN = f.read().strip()

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
        if self.kill_switch_triggered:
            print("❌ Kill switch active – order rejected")
            return False
        if instrument_key in self.positions:
            print("⚠️ Already in position")
            return False
        cost = price * qty
        if cost > self.balance:
            print(f"❌ Insufficient balance: ₹{cost:.2f} > ₹{self.balance:.2f}")
            return False
        self.balance -= cost
        self.positions[instrument_key] = {'qty': qty, 'entry_price': price, 'entry_time': timestamp}
        print(f"✅ BUY {qty} @ ₹{price:.2f} | Balance: ₹{self.balance:.2f}")
        return True

    def place_sell_order(self, instrument_key, price, qty=75, timestamp=None, reason=""):
        if instrument_key not in self.positions:
            print("⚠️ No position to sell")
            return False
        pos = self.positions.pop(instrument_key)
        proceeds = price * qty
        self.balance += proceeds
        pnl = (price - pos['entry_price']) * qty
        self.daily_pnl += pnl
        self.trades.append({
            'entry_time': pos['entry_time'],
            'exit_time': timestamp,
            'entry_price': pos['entry_price'],
            'exit_price': price,
            'pnl': pnl,
            'reason': reason
        })
        print(f"✅ SELL {qty} @ ₹{price:.2f} | P&L: ₹{pnl:.2f} | Balance: ₹{self.balance:.2f} | Reason: {reason}")
        if self.daily_pnl <= -self.daily_loss_limit:
            print(f"💀 DAILY LOSS LIMIT REACHED: ₹{self.daily_pnl:.2f} (limit ₹{self.daily_loss_limit})")
            self.kill_switch_triggered = True
        return True

    def get_status(self):
        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': len(self.positions),
            'kill_switch': self.kill_switch_triggered
        }

# -------------------------------
# Heikin-Ashi calculation
# -------------------------------
def calculate_heikin_ashi(candles):
    """
    candles: list of dicts with keys: timestamp, open, high, low, close
    Returns DataFrame with HA columns.
    """
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

# -------------------------------
# Strategy logic (run on each completed 1-min candle)
# -------------------------------
class HeikinAshiStrategy:
    def __init__(self, account, instrument_key):
        self.account = account
        self.instrument_key = instrument_key
        self.candles = []          # store recent candles for HA calculation
        self.in_position = False
        self.entry_price = None
        self.last_ha_green = None  # track previous HA color

    def on_candle_close(self, candle):
        """Called when a 1-minute candle is completed."""
        self.candles.append(candle)
        # Keep only last 100 candles
        if len(self.candles) > 100:
            self.candles = self.candles[-100:]
        if len(self.candles) < 2:
            return

        ha = calculate_heikin_ashi(self.candles)
        current_green = ha['HA_Close'].iloc[-1] >= ha['HA_Open'].iloc[-1]
        prev_green = ha['HA_Close'].iloc[-2] >= ha['HA_Open'].iloc[-2]

        # Entry: previous red, current green, no position
        if not self.in_position and (not prev_green) and current_green:
            entry_price = candle['close']
            print(f"\n🔔 ENTRY SIGNAL at {candle['timestamp']} price {entry_price:.2f}")
            self.account.place_buy_order(self.instrument_key, entry_price, timestamp=candle['timestamp'])
            self.in_position = True
            self.entry_price = entry_price

        # Exit if in position
        elif self.in_position:
            exit_reason = None
            # Breakeven stop: low <= entry price
            if candle['low'] <= self.entry_price:
                exit_reason = "Breakeven"
            # Red HA candle
            elif not current_green:
                exit_reason = "Red Signal"
            # Session end (2:00 PM IST)
            elif candle['timestamp'].time() >= datetime.strptime("14:00", "%H:%M").time():
                exit_reason = "Session End"

            if exit_reason:
                print(f"\n🔔 EXIT SIGNAL at {candle['timestamp']} price {candle['close']:.2f} reason: {exit_reason}")
                self.account.place_sell_order(self.instrument_key, candle['close'], timestamp=candle['timestamp'], reason=exit_reason)
                self.in_position = False
                self.entry_price = None

# -------------------------------
# WebSocket client with candle aggregation
# -------------------------------
class LiveFeed:
    def __init__(self, instrument_key, strategy):
        self.instrument_key = instrument_key
        self.strategy = strategy
        self.current_candle = None
        self.last_tick_time = None

    async def run(self):
        # 1. Get WebSocket URI
        uri = await self.get_websocket_uri()
        print(f"Connecting to: {uri}")

        async with websockets.connect(uri, max_size=2**25) as ws:
            # 2. Subscribe to the instrument
            subscribe_msg = {
                "guid": "valkyrie_client",
                "method": "sub",
                "data": {
                    "instrumentKeys": [self.instrument_key],
                    "mode": "full"  # or "full" for more data
                }
            }
            await ws.send(json.dumps(subscribe_msg))
            print(f"Subscribed to {self.instrument_key}")

            # 3. Process incoming messages
            async for message in ws:
                await self.process_message(message)

    async def get_websocket_uri(self):
        url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {ACCESS_TOKEN}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        # The response may contain 'data' key with either 'authorizedRedirectUri' or 'authorized_redirect_uri'
        if 'data' in data:
            ws_uri = data['data'].get('authorizedRedirectUri') or data['data'].get('authorized_redirect_uri')
            if ws_uri:
                return ws_uri
        # Fallback: if response is directly the URI string
        if isinstance(data, str):
            return data
        raise Exception("Could not extract WebSocket URI from response")["data"]["authorized_redirect_uri"]

    async def process_message(self, raw_message):
        # Decode protobuf
        try:
            import MarketDataFeed_pb2 as pb
            feed = pb.FeedResponse()
            feed.ParseFromString(raw_message)
            for key, feed_data in feed.feeds.items():
                if feed_data.ff:
                    # LTP (last traded price) message
                    ltp_data = pb.LtpMarketData()
                    ltp_data.ParseFromString(feed_data.ff.value)
                    price = ltp_data.ltp / 100.0  # convert paise to rupees
                    now = datetime.now()
                    self.on_tick(price, now)
                elif feed_data.index_ff:
                    index_data = pb.IndexMarketData()
                    index_data.ParseFromString(feed_data.index_ff.value)
                    # For index, use ttq (total traded quantity) as price
                    price = index_data.indicies.ttq / 100.0
                    now = datetime.now()
                    self.on_tick(price, now)
        except Exception as e:
            print(f"Protobuf decode error: {e}")

    def on_tick(self, price, timestamp):
        """Aggregate ticks into 1-minute candles."""
        current_minute = timestamp.replace(second=0, microsecond=0)
        if self.current_candle is None or self.current_candle['timestamp'] != current_minute:
            # Candle complete – notify strategy
            if self.current_candle is not None:
                self.strategy.on_candle_close(self.current_candle)
            # Start new candle
            self.current_candle = {
                'timestamp': current_minute,
                'open': price,
                'high': price,
                'low': price,
                'close': price
            }
        else:
            # Update current candle
            self.current_candle['high'] = max(self.current_candle['high'], price)
            self.current_candle['low'] = min(self.current_candle['low'], price)
            self.current_candle['close'] = price

# -------------------------------
# Main entry point
# -------------------------------
async def main():
    # Ask for instrument key (or use NIFTY 50 for testing)
    instrument_key = input("Enter instrument_key (e.g., NSE_INDEX|NIFTY 50): ").strip()
    if not instrument_key:
        print("No instrument provided, exiting.")
        return

    account = PaperAccount()
    strategy = HeikinAshiStrategy(account, instrument_key)
    feed = LiveFeed(instrument_key, strategy)

    print(f"Starting live feed for {instrument_key}...")
    await feed.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
