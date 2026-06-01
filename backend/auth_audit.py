"""
TOKEN AUTHENTICATION REALITY AUDIT
Uses the exact same code path as app.py:
  - load_upstox_token() -> reads from token.txt
  - requests.get() with Authorization: Bearer {token}
  - No proxies (per audit scope)
"""
import os
import sys
import json
import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT_DIR, "backend", "token.txt")

# ── PHASE 1: Token Source ──────────────────────────────────────────────────────
def load_upstox_token():
    """Exact replica of app.py load_upstox_token()"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return os.getenv("UPSTOX_ACCESS_TOKEN", "")

def call_upstox(endpoint, token):
    url = f"https://api.upstox.com{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {
            "url": url,
            "auth_header_present": True,
            "http_status": resp.status_code,
            "body": body
        }
    except Exception as e:
        return {
            "url": url,
            "auth_header_present": True,
            "http_status": None,
            "body": str(e)
        }

if __name__ == "__main__":
    results = {}

    # ── PHASE 1 ────────────────────────────────────────────────────────────────
    token = load_upstox_token()
    token_len = len(token)
    token_source = TOKEN_FILE if os.path.exists(TOKEN_FILE) else "ENV:UPSTOX_ACCESS_TOKEN"
    token_present = bool(token)

    results["phase1_token_source"] = {
        "file": TOKEN_FILE,
        "function": "load_upstox_token() in app.py L156",
        "token_source": token_source,
        "token_length": token_len,
        "token_present": token_present,
        "token_prefix": token[:30] + "..." if token else "EMPTY"
    }

    # ── PHASE 2: Profile ───────────────────────────────────────────────────────
    results["phase2_profile"] = call_upstox("/v2/user/profile", token)

    # ── PHASE 3: Funds ────────────────────────────────────────────────────────
    results["phase3_funds"] = call_upstox("/v2/user/get-funds-and-margin?segment=SEC", token)

    # ── PHASE 4: Token Validity ────────────────────────────────────────────────
    profile_resp = results["phase2_profile"]
    http_status = profile_resp["http_status"]
    body = profile_resp["body"]

    if http_status == 200:
        validity = "VALID"
        error_code = None
    elif http_status == 401:
        errors = body.get("errors", []) if isinstance(body, dict) else []
        error_code = errors[0].get("errorCode", "UNKNOWN") if errors else "UNKNOWN"
        error_msg = errors[0].get("message", "Unknown error") if errors else str(body)
        if "UDAPI100050" in str(error_code):
            validity = "INVALID_TOKEN"
        elif "expire" in error_msg.lower():
            validity = "EXPIRED"
        else:
            validity = "INVALID"
    elif http_status is None:
        validity = "NETWORK_ERROR"
        error_code = None
    else:
        validity = f"HTTP_{http_status}"
        error_code = None

    results["phase4_validity"] = {
        "status": validity,
        "http_code": http_status,
        "upstox_error_code": error_code,
        "message": body.get("errors", [{}])[0].get("message", "") if isinstance(body, dict) else str(body)
    }

    # ── PHASE 5: Refresh ──────────────────────────────────────────────────────
    results["phase5_refresh"] = {
        "auto_refresh_exists": False,
        "refresh_token_exists": False,
        "backend_renews_automatically": False,
        "manual_login_required": True,
        "status": "MISSING",
        "note": "load_upstox_token() only reads token.txt. auth.py exchanges auth_code once. No refresh loop found."
    }

    # ── Print ─────────────────────────────────────────────────────────────────
    print(json.dumps(results, indent=2))
