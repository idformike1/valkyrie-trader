import requests

with open("token.txt") as f:
    token = f.read().strip()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

url = "https://api.upstox.com/v2/charges/margin"

# Let's test with bar first (NSE_FO|57028)
payload_bar = {
    "instruments": [
        {
            "instrument_key": "NSE_FO|57026",
            "quantity": 50,
            "transaction_type": "BUY",
            "product": "D"
        }
    ]
}
resp_bar = requests.post(url, json=payload_bar, headers=headers)
print("BAR RESP:", resp_bar.status_code, resp_bar.text)

# Let's test with colon (NSE_FO:57028)
payload_colon = {
    "instruments": [
        {
            "instrument_key": "NSE_FO:57028",
            "quantity": 50,
            "transaction_type": "BUY",
            "product": "D"
        }
    ]
}
resp_colon = requests.post(url, json=payload_colon, headers=headers)
print("COLON RESP:", resp_colon.status_code, resp_colon.text)
