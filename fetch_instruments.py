import requests
import pandas as pd
import os

TOKEN_FILE = "token.txt"

def get_instruments():
    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()
    
    # Download master contract (NSE FO, etc.)
    url = "https://api.upstox.com/v2/instrument"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # The response is a list of instruments
        instruments = data.get("data", [])
        print(f"Downloaded {len(instruments)} instruments")
        # Save to CSV for later lookup
        df = pd.DataFrame(instruments)
        df.to_csv("instruments.csv", index=False)
        print("Saved to instruments.csv")
        # Show first few rows
        print(df[["symbol", "instrument_key", "exchange", "instrument_type"]].head())
    else:
        print(f"Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    get_instruments()
