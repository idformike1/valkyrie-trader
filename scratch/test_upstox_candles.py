import requests
import urllib.parse
from datetime import datetime, timedelta

def test():
    with open("backend/token.txt", "r") as f:
        token = f.read().strip()
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    instrument_key = "NSE_FO|74892"
    encoded_key = urllib.parse.quote(instrument_key)
    
    # 1. Test Intraday
    url_intra = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded_key}/1minute"
    print("Querying Intraday:", url_intra)
    resp = requests.get(url_intra, headers=headers)
    print("Intraday Status:", resp.status_code)
    try:
        print("Intraday Sample:", resp.json().get("data", {}).get("candles", [])[:3])
        print("Intraday Total Count:", len(resp.json().get("data", {}).get("candles", [])))
    except Exception as e:
        print("Intraday Error Parse:", resp.text)
        
    # 2. Test Historical
    to_date = datetime.now()
    from_date = to_date - timedelta(days=10)
    url_hist = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/1minute/{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
    print("\nQuerying Historical:", url_hist)
    resp = requests.get(url_hist, headers=headers)
    print("Historical Status:", resp.status_code)
    try:
        print("Historical Sample:", resp.json().get("data", {}).get("candles", [])[:3])
        print("Historical Total Count:", len(resp.json().get("data", {}).get("candles", [])))
    except Exception as e:
        print("Historical Error Parse:", resp.text)

if __name__ == "__main__":
    test()
