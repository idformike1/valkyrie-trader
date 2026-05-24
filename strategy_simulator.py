import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time
import os

# Load your access token
TOKEN_FILE = "token.txt"
if not os.path.exists(TOKEN_FILE):
    print("❌ token.txt not found. Run auth.py first.")
    exit(1)

with open(TOKEN_FILE, "r") as f:
    token = f.read().strip()

# -------------------------------
# Heikin-Ashi Calculation (your function)
# -------------------------------
def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates Heikin-Ashi candles from a standard OHLC DataFrame.
    Expects columns: 'open', 'high', 'low', 'close'
    Returns DataFrame with HA columns only.
    """
    # Create a copy to avoid modifying the original
    ha = pd.DataFrame(index=df.index)
    
    # 1. HA-Close (fully vectorized)
    ha['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4.0
    
    # 2. HA-Open (sequential, using .loc to avoid chained assignment)
    ha_open = np.zeros(len(df))
    ha_open[0] = df['open'].iloc[0]
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i-1] + ha['HA_Close'].iloc[i-1]) / 2.0
    ha['HA_Open'] = ha_open
    
    # 3. HA-High and HA-Low (vectorized across the relevant columns)
    ha['HA_High'] = pd.concat([df['high'], ha['HA_Open'], ha['HA_Close']], axis=1).max(axis=1)
    ha['HA_Low']  = pd.concat([df['low'],  ha['HA_Open'], ha['HA_Close']], axis=1).min(axis=1)
    
    return ha

# -------------------------------
# Fetch historical 1-min candles from Upstox
# -------------------------------
def fetch_historical(instrument_key, days_back=5):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/1minute/{end_date.strftime('%Y-%m-%d')}/{start_date.strftime('%Y-%m-%d')}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    
    print(f"Fetching historical data for {instrument_key}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None
    
    data = response.json()
    candles = data.get('data', {}).get('candles', [])
    if not candles:
        print("No candles returned")
        return None
    
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    return df

# -------------------------------
# Strategy: Long only, exit on red HA, breakeven, or 2 PM
# -------------------------------
def run_strategy(df):
    ha = calculate_heikin_ashi(df)
    # Add HA columns to the original dataframe without chained assignment
    df = df.assign(
        HA_Open=ha['HA_Open'],
        HA_High=ha['HA_High'],
        HA_Low=ha['HA_Low'],
        HA_Close=ha['HA_Close']
    )
    # Determine candle color: 1 = green (close >= open)
    df['HA_Green'] = df['HA_Close'] >= df['HA_Open']
    # Entry signal: previous candle red (False), current green (True)
    df['Entry'] = (df['HA_Green'] == True) & (df['HA_Green'].shift(1) == False)
    # ... rest of the function (trades loop) unchanged
    ha = calculate_heikin_ashi(df)
    df['HA_Open'] = ha['HA_Open']
    df['HA_High'] = ha['HA_High']
    df['HA_Low'] = ha['HA_Low']
    df['HA_Close'] = ha['HA_Close']
    
    # Determine candle color: 1 = green, 0 = red
    df['HA_Green'] = df['HA_Close'] >= df['HA_Open']
    
    # Entry signal: previous candle red, current green, no open position
    df['Entry'] = (df['HA_Green'] == True) & (df['HA_Green'].shift(1) == False)
    
    trades = []
    in_position = False
    entry_price = 0
    entry_time = None
    
    for idx, row in df.iterrows():
        # Exit conditions if in position
        if in_position:
            exit_signal = False
            exit_reason = ""
            
            # 1. Red HA candle (signal-based exit)
            if row['HA_Green'] == False:
                exit_signal = True
                exit_reason = "Red Signal"
            # 2. Breakeven stop: price <= entry price (using low)
            elif row['low'] <= entry_price:
                exit_signal = True
                exit_reason = "Breakeven"
            # 3. Session end: 2:00 PM
            elif row['timestamp'].time() >= datetime.strptime("14:00", "%H:%M").time():
                exit_signal = True
                exit_reason = "Session End"
            
            if exit_signal:
                exit_price = row['close']  # exit at close of that minute
                pnl = (exit_price - entry_price) * 75  # 1 lot = 75 shares
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': exit_reason
                })
                in_position = False
        
        # Entry signal only if not already in position
        if not in_position and row['Entry']:
            in_position = True
            entry_price = row['close']  # enter at close of signal candle
            entry_time = row['timestamp']
    
    return trades, df

# -------------------------------
# Main: ask user for contract and run
# -------------------------------
if __name__ == "__main__":
    # Load instruments CSV to search for user input
    if not os.path.exists("nifty_options.csv"):
        print("❌ nifty_options.csv not found. Run download_instruments.py first.")
        exit(1)
    
    opts_df = pd.read_csv("nifty_options.csv")
    # Convert expiry timestamp to datetime
    opts_df['expiry_date'] = pd.to_datetime(opts_df['expiry'], unit='ms')
    
    print("\n📊 Available expiry dates (sample):")
    expiries = opts_df['expiry_date'].dt.strftime('%Y-%m-%d').unique()
    for e in sorted(expiries)[:10]:
        print(f"  {e}")
    
    strike = float(input("\nEnter strike price (e.g., 24800): "))
    expiry_str = input("Enter expiry date (YYYY-MM-DD, e.g., 2026-05-26): ")
    option_type = input("Option type (CE or PE): ").upper()
    
    # Find matching instrument
    mask = (opts_df['strike_price'] == strike) & \
           (opts_df['expiry_date'].dt.strftime('%Y-%m-%d') == expiry_str) & \
           (opts_df['instrument_type'] == option_type)
    
    matches = opts_df[mask]
    if matches.empty:
        print("❌ No matching option found. Check strike, expiry, and type.")
        exit(1)
    
    instrument_key = matches.iloc[0]['instrument_key']
    print(f"\n✅ Selected: {matches.iloc[0]['trading_symbol']}")
    print(f"   Instrument key: {instrument_key}")
    
    # Fetch historical data
    df = fetch_historical(instrument_key, days_back=5)
    if df is None:
        exit(1)
    
    print(f"✅ Fetched {len(df)} minutes of data")
    
    # Run strategy
    trades, df_with_signals = run_strategy(df)
    
    print(f"\n📈 Total trades generated: {len(trades)}")
    if trades:
        total_pnl = sum(t['pnl'] for t in trades)
        print(f"�� Total P&L: ₹{total_pnl:.2f}")
        print("\nTrade details:")
        for i, t in enumerate(trades, 1):
            print(f"  {i}. Entry: {t['entry_time']} @ ₹{t['entry_price']:.2f} | Exit: {t['exit_time']} @ ₹{t['exit_price']:.2f} | P&L: ₹{t['pnl']:.2f} | Reason: {t['exit_reason']}")
    else:
        print("No trades triggered in this historical period.")
    
    # Save to CSV for inspection
    df_with_signals.to_csv("backtest_output.csv", index=False)
    print("\n✅ Detailed backtest saved to backtest_output.csv")
