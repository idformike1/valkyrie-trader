import requests

with open("token.txt") as f:
    token = f.read().strip()

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json"
}

keys = [
    "NSE_INDEX:Nifty 50",
    "NSE_INDEX:Nifty Bank",
    "NSE_EQ:INE002A01018",
    "NSE_EQ:INE467B01029",
    "NSE_EQ:INE009A01021"
]

url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={','.join(keys)}"
resp = requests.get(url, headers=headers)
print("STATUS:", resp.status_code)
print("DATA KEYS:", list(resp.json().get("data", {}).keys()))
