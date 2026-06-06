import pandas as pd
import numpy as np
from strategy_heikin_ashi_gar import calculate_heikin_ashi, HeikinAshiGarStrategy, HeikinAshiGarStrategyV2

def test_heikin_ashi_calculation():
    print("Testing Heikin Ashi calculation math...")
    # Standard raw candles
    mock_data = {
        'open':  [100.0, 102.0, 101.0],
        'high':  [105.0, 104.0, 103.0],
        'low':   [98.0,  99.0,  97.0],
        'close': [102.0, 100.0, 102.0]
    }
    df = pd.DataFrame(mock_data)
    ha_df = calculate_heikin_ashi(df)
    
    # Calculate hand-computed values to verify:
    # Candle 0:
    # close = (100+105+98+102)/4 = 101.25
    # open = 100
    # high = max(105, 100, 101.25) = 105
    # low = min(98, 100, 101.25) = 98
    
    # Candle 1:
    # close = (102+104+99+100)/4 = 101.25
    # open = (100 + 101.25)/2 = 100.625
    # high = max(104, 100.625, 101.25) = 104
    # low = min(99, 100.625, 101.25) = 99
    
    assert np.isclose(ha_df['close'].iloc[0], 101.25)
    assert np.isclose(ha_df['open'].iloc[0], 100.0)
    assert np.isclose(ha_df['close'].iloc[1], 101.25)
    assert np.isclose(ha_df['open'].iloc[1], 100.625)
    print("✅ Heikin Ashi calculation math matches formulas perfectly!")

def test_strategy_signals():
    print("Testing Strategy Entry and Exit triggers...")
    
    # We need at least 3 rows to evaluate (prior [-2], completed [-1], current live tick)
    # Scenario: prior is Red, completed is Green and Strong, current tick is running
    mock_raw = {
        'timestamp': ['2026-05-25 09:30:00', '2026-05-25 09:31:00', '2026-05-25 09:32:00'],
        'open':  [100.0, 99.0, 101.0],
        # Let's ensure prior [-2] is Red: open=100.0, close=98.0
        # completed [-1] is Green & Strong: open=99.0, close=101.0, low=99.0 (no lower wick)
        'high':  [101.0, 102.0, 103.0],
        'low':   [97.0,  99.0,  100.0],
        'close': [98.0,  101.0, 102.0]
    }
    df = pd.DataFrame(mock_raw)
    
    # Verify calculated HA values
    ha = calculate_heikin_ashi(df)
    # Candle 0 (prior, index 0): open=100.0, close=98.5
    # Candle 1 (completed, index 1): open=(100+98.5)/2=99.25, close=(99+102+99+101)/4=100.25, low=min(99, 99.25, 100.25)=99.0
    # Let's check is_strong_green: abs(open - low) = abs(99.25 - 99.0) = 0.25.
    # To pass is_strong_green: abs(open - low) <= 0.05.
    # Let's tweak mock values to make completed candle HA open exactly equal to HA low.
    # If raw open=99.0, close=101.0, low=99.0, high=101.0. Let's make HA open = 99.0.
    # For HA open of Candle 1 to be 99.0, Candle 0 HA open + Candle 0 HA close must be 198.0.
    # E.g. Candle 0 raw open = 99.0, close = 99.0.
    
    # Let's use a systematic data list to trigger BUY
    # We will build a series of candles:
    # C0: Red candle
    # C1: Red candle
    # C2: Strong Green candle
    # C3: Live Tick
    data = {
        'timestamp': [
            '2026-05-25 09:15:00',
            '2026-05-25 09:16:00',
            '2026-05-25 09:17:00',
            '2026-05-25 09:18:00'
        ],
        'open':  [100.0, 85.0, 92.0, 110.0],
        'high':  [100.0, 100.0, 110.0, 111.0],
        'low':   [100.0, 70.0, 92.0, 109.0],
        'close': [100.0, 75.0, 110.0, 110.0]
    }
    df = pd.DataFrame(data)
    ha_df = calculate_heikin_ashi(df)
    
    # Let's print colors of completed candles to verify:
    # Index 1: prior completed (C1)
    # Index 2: last completed (C2)
    # Index 3: live tick (C3)
    c_prior = ha_df.iloc[1]
    c_comp = ha_df.iloc[2]
    
    print(f"Prior: Open={c_prior['open']:.2f}, Close={c_prior['close']:.2f} (Red: {c_prior['close'] < c_prior['open']})")
    print(f"Completed: Open={c_comp['open']:.2f}, Low={c_comp['low']:.2f}, Close={c_comp['close']:.2f} (Green: {c_comp['close'] > c_comp['open']})")
    print(f"Open-Low Diff: {abs(c_comp['open'] - c_comp['low']):.4f}")
    
    strat = HeikinAshiGarStrategy()
    signal, meta = strat.evaluate(df)
    print(f"Triggered Signal: {signal} | Meta: {meta}")
    
    assert signal == "BUY"
    assert strat.is_holding == True
    assert strat.stop_loss_level == df['open'].iloc[1] # raw open of prior candle
    
    # Now let's evaluate exit trigger (reversal red candle)
    # We add a new candle C4 which turns red
    # C3 (now completed): open=95, close=90 (Red)
    # C4 (live tick): open=90, close=90
    data_exit = {
        'timestamp': [
            '2026-05-25 09:15:00',
            '2026-05-25 09:16:00',
            '2026-05-25 09:17:00',
            '2026-05-25 09:18:00',
            '2026-05-25 09:19:00'
        ],
        'open':  [100.0, 85.0, 92.0, 95.0, 90.0],
        'high':  [100.0, 100.0, 110.0, 95.0, 91.0],
        'low':   [100.0, 70.0, 92.0, 86.0, 89.0],
        'close': [100.0, 75.0, 110.0, 90.0, 90.0]
    }
    df_exit = pd.DataFrame(data_exit)
    signal_exit, meta_exit = strat.evaluate(df_exit)
    print(f"Triggered Exit Signal: {signal_exit} | Meta: {meta_exit}")
    
    assert signal_exit == "EXIT"
    assert meta_exit["reason"] == "TECHNICAL_REVERSAL"
    assert strat.is_holding == False
    
    print("✅ Strategy Entry and Exit triggers behave exactly as expected!")

def test_strategy_v2_signals():
    print("Testing Strategy V2 Entry and Exit triggers (no wick restriction, SL at red low, immediate exit on red)...")
    
    # For V2, we evaluate the latest closed candle (iloc[-1]) and the one before it (iloc[-2]).
    # We pass 3 candles:
    # C0: Neutral / green
    # C1: Red candle (index 1, prior completed)
    # C2: Green candle (index 2, completed - should trigger BUY immediately on close, despite bottom wick)
    data = {
        'timestamp': [
            '2026-05-25 09:15:00',
            '2026-05-25 09:16:00',
            '2026-05-25 09:17:00'
        ],
        'open':  [100.0, 100.0, 95.0],
        'high':  [100.0, 101.0, 110.0],
        'low':   [100.0, 90.0, 92.0], # C1 low is 90.0 (previous red low point)
        'close': [100.0, 92.0, 108.0]  # C2 close is 108.0 (green)
    }
    df = pd.DataFrame(data)
    ha_df = calculate_heikin_ashi(df)
    
    c_prior = ha_df.iloc[-2] # C1
    c_comp = ha_df.iloc[-1]  # C2
    
    print(f"V2 Prior: Open={c_prior['open']:.2f}, Close={c_prior['close']:.2f} (Red: {c_prior['close'] < c_prior['open']})")
    print(f"V2 Completed: Open={c_comp['open']:.2f}, Low={c_comp['low']:.2f}, Close={c_comp['close']:.2f} (Green: {c_comp['close'] > c_comp['open']})")
    
    strat = HeikinAshiGarStrategyV2()
    signal, meta = strat.evaluate(df)
    print(f"Triggered V2 Signal: {signal} | Meta: {meta}")
    
    assert signal == "BUY"
    assert strat.is_holding == True
    # Stop loss level should be equal to previous red low (raw low of C1 = 90.0)
    assert strat.stop_loss_level == 90.0
    
    # Now test exit: add C3 closed as a Red candle
    data_exit = {
        'timestamp': [
            '2026-05-25 09:15:00',
            '2026-05-25 09:16:00',
            '2026-05-25 09:17:00',
            '2026-05-25 09:18:00'
        ],
        'open':  [100.0, 100.0, 95.0, 98.0],
        'high':  [100.0, 101.0, 110.0, 98.0],
        'low':   [100.0, 90.0, 92.0, 94.0],
        'close': [100.0, 92.0, 108.0, 95.0]  # C3 closed red (open 98, close 95)
    }
    df_exit = pd.DataFrame(data_exit)
    signal_exit, meta_exit = strat.evaluate(df_exit)
    print(f"Triggered V2 Exit Signal: {signal_exit} | Meta: {meta_exit}")
    
    assert signal_exit == "EXIT"
    assert meta_exit["reason"] == "TECHNICAL_REVERSAL"
    assert strat.is_holding == False
    print("✅ Strategy V2 Entry and Exit triggers behave exactly as expected!")

if __name__ == "__main__":
    test_heikin_ashi_calculation()
    test_strategy_signals()
    test_strategy_v2_signals()
    print("🎉 All verification tests passed successfully!")
