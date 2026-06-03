import os
from dotenv import load_dotenv
import requests

load_dotenv()

client_id = os.getenv("UPSTOX_API_KEY")
client_secret = os.getenv("UPSTOX_CLIENT_SECRET")
redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")

print("--- Loaded Credentials ---")
print(f"API Key (Client ID): '{client_id}'")
print(f"Client Secret      : '{client_secret}'")
print(f"Redirect URI       : '{redirect_uri}'")
print("--------------------------")
