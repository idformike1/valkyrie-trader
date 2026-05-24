import os
import requests
from dotenv import load_dotenv

def get_access_token(auth_code):
    load_dotenv()
    
    client_id = os.getenv("UPSTOX_API_KEY")
    client_secret = os.getenv("UPSTOX_CLIENT_SECRET")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")
    
    if not all([client_id, client_secret, redirect_uri]):
        print("Error: Missing credentials in .env")
        return
    
    url = "https://api.upstox.com/v2/login/authorization/token"
    payload = {
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            if access_token:
                print("✅ Authentication successful!")
                with open("token.txt", "w") as f:
                    f.write(access_token)
                print("Access token saved to token.txt")
            else:
                print("Error: No access_token in response")
                print(data)
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    code = input("Enter the authorization code from redirect URL: ").strip()
    get_access_token(code)
