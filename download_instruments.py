import pandas as pd

url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"

print("Downloading master instruments file...")
df = pd.read_json(url, compression='gzip')
print(f"✅ Downloaded {len(df)} instruments")

# Let's see what columns we actually have
print("\n📋 Available columns in the JSON file:")
print(df.columns.tolist())

# Filter for Nifty 50 options (NSE_FO segment where instrument_type is CE or PE)
# Use .loc to avoid chained assignment warnings
nifty_options = df.loc[
    (df['segment'] == 'NSE_FO') & 
    (df['instrument_type'].isin(['CE', 'PE'])) &
    (df['name'] == 'NIFTY')
].copy()

print(f"\n📊 Found {len(nifty_options)} Nifty option contracts")
print("\nFirst 5 rows (instrument_key, trading_symbol, expiry, strike_price, instrument_type):")
print(nifty_options[['instrument_key', 'trading_symbol', 'expiry', 'strike_price', 'instrument_type']].head())

# Save to CSV for later reference
nifty_options.to_csv("nifty_options.csv", index=False)
print("\n✅ Saved to nifty_options.csv")

# Also save full instruments list for any other searches
df.to_csv("all_instruments.csv", index=False)
print("✅ Saved full instrument list to all_instruments.csv")

# Show unique expiry dates for available options
print("\n🔍 Available expiry dates:")
expiries = nifty_options['expiry'].dropna().unique()
for expiry in sorted(expiries)[:10]:  # Show first 10 for brevity
    print(f"  - {expiry}")
