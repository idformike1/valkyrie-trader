import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("UPSTOX_API_KEY")
client_secret = os.getenv("UPSTOX_CLIENT_SECRET")

if not client_id or not client_secret:
    print("Error: Missing credentials in .env")
    sys.exit(1)

code = input("Enter the authorization code: ").strip()

redirect_uris = [
    "https://127.0.0.1:3000",
    "https://127.0.0.1:3000/",
    "http://localhost:3000",
    "http://localhost:3000/",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3000/",
    "https://localhost:3000",
    "https://localhost:3000/",
]

url = "https://api.upstox.com/v2/login/authorization/token"
success = False

for r_uri in redirect_uris:
    print(f"\nTrying redirect_uri: '{r_uri}'...")
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": r_uri,
        "grant_type": "authorization_code"
    }
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=10)
        body = resp.json()
        if resp.status_code == 200:
            access_token = body.get("access_token")
            if access_token:
                print(f"✅ SUCCESS with redirect_uri: '{r_uri}'!")
                
                # Write to both root and backend token files to be absolutely sure
                root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
                token_paths = [
                    os.path.join(root_path, "token.txt"),
                    os.path.join(root_path, "backend", "token.txt")
                ]
                
                for path in token_paths:
                    with open(path, "w") as f:
                        f.write(access_token)
                    print(f"Access token successfully saved to {path}")
                
                # Also let's update the .env file with the successful redirect URI if it differs!
                env_path = os.path.join(root_path, ".env")
                if os.path.exists(env_path):
                    with open(env_path, "r") as f:
                        lines = f.readlines()
                    with open(env_path, "w") as f:
                        for line in lines:
                            if line.startswith("UPSTOX_REDIRECT_URI="):
                                f.write(f"UPSTOX_REDIRECT_URI={r_uri}\n")
                            else:
                                f.write(line)
                    print(f"Updated {env_path} with matching redirect URI.")
                
                success = True
                break
        else:
            print(f"❌ Failed: HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"⚠️ Connection error: {e}")

if not success:
    print("\n❌ All attempted redirect URIs failed. Please generate a new code and try again.")
