import requests

# Read the token
with open("token.txt", "r") as f:
    token = f.read().strip()

# Fetch user profile
url = "https://api.upstox.com/v2/user/profile"
headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    print("✅ Token is valid!")
    print("Profile:", response.json())
else:
    print(f"❌ Error {response.status_code}: {response.text}")
