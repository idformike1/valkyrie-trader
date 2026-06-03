import sys
import time
import json
import requests
from playwright.sync_api import sync_playwright

def get_positions_from_api():
    try:
        r = requests.get("http://localhost:8081/api/broker/positions", timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", []) or []
            return ", ".join([p.get("trading_symbol") for p in data if p.get("trading_symbol")])
    except Exception as e:
        print(f"Error fetching positions: {e}")
    return "NONE"

def get_orders_from_api():
    try:
        r = requests.get("http://localhost:8081/api/broker/orders", timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", []) or []
            return ", ".join([o.get("trading_symbol") for o in data if o.get("trading_symbol")])
    except Exception as e:
        print(f"Error fetching orders: {e}")
    return "NONE"

def get_trades_from_api():
    try:
        r = requests.get("http://localhost:8081/api/broker/trades", timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", []) or []
            return ", ".join([t.get("trading_symbol") for t in data if t.get("trading_symbol")])
    except Exception as e:
        print(f"Error fetching trades: {e}")
    return "NONE"

def main():
    print("Starting Forensic Verification Audit...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print("Navigating to http://localhost:3000...")
        page.goto("http://localhost:3000", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Ensure we are on the Option Chain tab
        option_chain_tab = page.locator('button:has-text("Option Chain")').first
        if option_chain_tab.is_visible():
            option_chain_tab.click()
            page.wait_for_timeout(1000)

        # Helpers to retrieve UI state
        def get_watchlist_active():
            active_row = page.locator('div[class*="bg-cyan-500/10"] span.truncate').first
            return active_row.inner_text() if active_row.count() > 0 else "N/A"

        def get_chart_header():
            select = page.locator('select.text-cyan-400').first
            return select.input_value() if select.count() > 0 else "N/A"

        def get_order_ticket():
            hud = page.locator('div:has-text("CONTRACT:")').last
            if hud.is_visible():
                return hud.locator('span.font-bold.text-cyan-400.uppercase').inner_text()
            return "N/A"

        def get_active_target():
            hud = page.locator('div:has-text("Active Target:")').last
            if hud.is_visible():
                return hud.locator('span.font-bold.text-cyan-400.font-mono').inner_text()
            return "N/A"

        def run_state_dump(label):
            print(f"\n======================================")
            print(f"STATE DUMP FOR: {label}")
            print(f"======================================")
            
            watchlist_val = get_watchlist_active()
            chart_val = get_chart_header()
            order_ticket_val = get_order_ticket()
            active_target_val = get_active_target()
            
            positions_val = get_positions_from_api()
            orders_val = get_orders_from_api()
            trades_val = get_trades_from_api()
            
            print(f"WATCHLIST={watchlist_val}")
            print(f"CHART={chart_val}")
            print(f"ORDER_TICKET={order_ticket_val}")
            print(f"ACTIVE_TARGET={active_target_val}")
            print(f"POSITIONS={positions_val}")
            print(f"ORDERS={orders_val}")
            print(f"TRADES={trades_val}")

        # ----------------------------------------------------
        # 1. BANKNIFTY Underlying State
        # ----------------------------------------------------
        banknifty_span = page.locator('span.truncate.uppercase.font-medium:text-is("BANKNIFTY")')
        if banknifty_span.is_visible():
            row = banknifty_span.locator('xpath=./ancestor::div[contains(@class, "grid-cols-12")]')
            row.click()
            page.wait_for_timeout(1000)
        else:
            print("BANKNIFTY row not visible in watchlist, clicking dropdown directly...")
            index_select = page.locator('select.bg-slate-950').first
            index_select.select_option("BANKNIFTY")
            page.wait_for_timeout(1000)

        # Wait for option chain strikes to load
        page.wait_for_selector('tr:has-text("53600")', timeout=15000)
        page.wait_for_timeout(1000)
        
        run_state_dump("BANKNIFTY underlying")

        # ----------------------------------------------------
        # 2. BANKNIFTY 53600 CE State
        # ----------------------------------------------------
        row_53600 = page.locator('tr:has-text("53600")').first
        if row_53600.is_visible():
            ce_button = row_53600.locator('button').first
            ce_button.click()
            page.wait_for_timeout(2000)
            
            run_state_dump("BANKNIFTY 53600 CE")
        else:
            print("Strike 53600 row not found for CE selection.")

        # ----------------------------------------------------
        # 3. BANKNIFTY 53600 PE State
        # ----------------------------------------------------
        row_53600 = page.locator('tr:has-text("53600")').first
        if row_53600.is_visible():
            pe_button = row_53600.locator('button').nth(1)
            pe_button.click()
            page.wait_for_timeout(2000)
            
            run_state_dump("BANKNIFTY 53600 PE")
        else:
            print("Strike 53600 row not found for PE selection.")

        # ----------------------------------------------------
        # 4. Final Watchlist localStorage export
        # ----------------------------------------------------
        print("\n======================================")
        print("FINAL LOCALSTORAGE WATCHLIST EXPORT:")
        print("======================================")
        valkyrie_watchlist = page.evaluate("window.localStorage.getItem('valkyrie_watchlist')")
        if valkyrie_watchlist:
            try:
                parsed = json.loads(valkyrie_watchlist)
                print(json.dumps(parsed, indent=2))
            except Exception as e:
                print(valkyrie_watchlist)
        else:
            print("NONE")

        browser.close()

if __name__ == "__main__":
    main()
