import time
from playwright.sync_api import sync_playwright

def main():
    print("Starting Phase 9D Reproduction Audit...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print("Navigating to http://localhost:3000...")
        page.goto("http://localhost:3000", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Mount Option Chain Panel
        option_chain_tab = page.locator('button:has-text("Option Chain")').first
        if option_chain_tab.is_visible():
            option_chain_tab.click()
            page.wait_for_timeout(1000)

        def capture_identifiers(step_label):
            print(f"\n--- CAPTURED IDENTIFIERS FOR: {step_label} ---")
            
            # Watchlist Active
            active_watchlist = page.locator('div[class*="bg-cyan-500/10"] span.truncate').first
            watchlist_val = active_watchlist.inner_text() if active_watchlist.count() > 0 else "N/A"
            
            # Chart Dropdown
            chart_select = page.locator('select.text-cyan-400').first
            chart_val = chart_select.input_value() if chart_select.count() > 0 else "N/A"
            
            # Order Ticket Contract
            ticket_hud = page.locator('div:has-text("CONTRACT:")').last
            ticket_val = ticket_hud.locator('span.font-bold.text-cyan-400.uppercase').inner_text() if ticket_hud.is_visible() else "N/A"
            
            # Active Target Banner
            target_hud = page.locator('div:has-text("Active Target:")').last
            target_val = target_hud.locator('span.font-bold.text-cyan-400.font-mono').inner_text() if target_hud.is_visible() else "N/A"
            
            # Key value label inside Option Chain Panel
            key_hud = page.locator('span:has-text("Key:")').last
            key_val = key_hud.inner_text().strip() if key_hud.is_visible() else "N/A"
            
            print(f"Watchlist Item: {watchlist_val}")
            print(f"Chart Header Select: {chart_val}")
            print(f"Order Ticket Contract: {ticket_val}")
            print(f"Active Target Banner: {target_val}")
            print(f"Option Chain Key Label: {key_val}")

        # Step 1: Select BANKNIFTY
        print("\n[Step 1] Selecting BANKNIFTY in watchlist...")
        banknifty_span = page.locator('span.truncate.uppercase.font-medium:text-is("BANKNIFTY")')
        if banknifty_span.is_visible():
            row = banknifty_span.locator('xpath=./ancestor::div[contains(@class, "grid-cols-12")]')
            row.click()
            page.wait_for_timeout(2000)
        else:
            print("BANKNIFTY watchlist item not visible.")
            
        capture_identifiers("1. Select BANKNIFTY")

        # Step 2: Select ATM CE
        # Wait for option chain strikes to load
        page.wait_for_selector('tr:has-text("53600")', timeout=15000)
        print("\n[Step 2] Selecting ATM CE (Clicking CE button in strike 53600 row)...")
        row_53600 = page.locator('tr:has-text("53600")').first
        if row_53600.is_visible():
            ce_button = row_53600.locator('button').first
            ce_button.click()
            page.wait_for_timeout(2000)
        else:
            print("Strike 53600 row not visible.")
            
        capture_identifiers("2. Select ATM CE")

        # Step 3: Refresh page
        print("\n[Step 3] Refreshing page...")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # Ensure Option Chain Tab is clicked back
        option_chain_tab = page.locator('button:has-text("Option Chain")').first
        if option_chain_tab.is_visible():
            option_chain_tab.click()
            page.wait_for_timeout(1000)
            
        capture_identifiers("3. Refresh Page")

        # Step 4: Change expiry
        print("\n[Step 4] Changing expiry to next weekly contract...")
        expiry_select = page.locator('select.bg-slate-950').nth(1)  # Expiry dropdown
        if expiry_select.is_visible():
            options = expiry_select.locator('option').all_inner_texts()
            if len(options) > 1:
                print(f"Selecting next expiry: {options[1]}")
                expiry_select.select_option(options[1])
                page.wait_for_timeout(3000)
            else:
                print("Only one expiry option available.")
        else:
            print("Expiry dropdown not visible.")
            
        capture_identifiers("4. Change Expiry")

        # Step 5: Change underlying
        print("\n[Step 5] Changing underlying index back to NIFTY 50...")
        nifty_span = page.locator('span.truncate.uppercase.font-medium:text-is("NIFTY 50")')
        if nifty_span.is_visible():
            row = nifty_span.locator('xpath=./ancestor::div[contains(@class, "grid-cols-12")]')
            row.click()
            page.wait_for_timeout(3000)
        else:
            print("NIFTY 50 watchlist item not visible.")
            
        capture_identifiers("5. Change Underlying")

        browser.close()

if __name__ == "__main__":
    main()
