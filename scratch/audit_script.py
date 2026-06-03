import sys
import time
import json
from playwright.sync_api import sync_playwright

def main():
    print("Starting Playwright Audit Script...")
    with sync_playwright() as p:
        # Launch Chromium headless
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print("Navigating to http://localhost:3000...")
        page.goto("http://localhost:3000", wait_until="networkidle")
        
        # Wait for the main app container to load
        page.wait_for_timeout(3000)

        # ----------------------------------------------------
        # 1. Click BANKNIFTY in the Watchlist panel
        # ----------------------------------------------------
        print("\n--- STEP 1: Click BANKNIFTY ---")
        
        banknifty_span = page.locator('span.truncate.uppercase.font-medium:text-is("BANKNIFTY")')
        if not banknifty_span.is_visible():
            print("BANKNIFTY not found in watchlist. Attempting to click index selector dropdown directly...")
            index_select = page.locator('select.bg-slate-950').first
            index_select.select_option("BANKNIFTY")
            page.wait_for_timeout(2000)
        else:
            # Click the parent row container
            row = banknifty_span.locator('xpath=./ancestor::div[contains(@class, "grid-cols-12")]')
            row.click()
            print("Clicked BANKNIFTY in watchlist.")
            page.wait_for_timeout(3000) # Wait for option chain metadata to sync

        # Wait for option chain table to load with rows
        print("Waiting for option chain table rows to load...")
        try:
            page.wait_for_selector('tbody tr:nth-child(5)', timeout=10000)
        except Exception as e:
            print("Timeout waiting for option chain strikes to load.")

        # selectedUnderlying: Option Chain Index select element value
        index_select = page.locator('select.bg-slate-950').first
        selected_underlying = index_select.input_value() if index_select.count() > 0 else "N/A"
        
        # selectedContract: Option Chain Panel -> Active Target contract symbol
        active_target_hud = page.locator('div:has-text("Active Target:")').last
        if active_target_hud.is_visible():
            selected_contract = active_target_hud.locator('span.font-bold.text-cyan-400.font-mono').inner_text()
        else:
            # Fallback to contract info in order entry pad
            contract_hud = page.locator('div:has-text("CONTRACT:")').last
            if contract_hud.is_visible():
                selected_contract = contract_hud.locator('span.font-bold.text-cyan-400.uppercase').inner_text()
            else:
                selected_contract = "None"

        # activeInstrument: Chart toolbar symbol select value
        chart_symbol_select = page.locator('select.text-cyan-400.font-bold.uppercase').first
        active_instrument = chart_symbol_select.input_value() if chart_symbol_select.count() > 0 else "N/A"

        print(f"selectedUnderlying: {selected_underlying}")
        print(f"selectedContract: {selected_contract}")
        print(f"activeInstrument: {active_instrument}")

        # ----------------------------------------------------
        # 2. Click 53600 CE in the Option Chain table
        # ----------------------------------------------------
        print("\n--- STEP 2: Click 53600 CE ---")
        
        # Locate the table row containing Strike text "53600"
        strike_span = page.locator('span:text-is("53600")')
        if not strike_span.is_visible():
            print("Strike 53600 not found in table.")
            print("Strikes visible in table:")
            # Use standard CSS class for strike cells, which are text-slate-300 under td or the span
            strikes = page.locator('tbody tr td span').all_inner_texts()
            # filter out non-numeric or empty strings to find strikes
            clean_strikes = [s for s in strikes if s.isdigit()]
            print(clean_strikes[:20])
            sys.exit(1)

        row_53600 = strike_span.locator('xpath=./ancestor::tr')
        
        # CE LTP button is the first button inside this tr
        ce_button = row_53600.locator('button').first
        ce_button.click()
        print("Clicked 53600 CE button.")
        page.wait_for_timeout(2000)

        # Dump chart title, order ticket title, active target, watchlist entry added
        
        def dump_values():
            # chart title: Value from chart symbol selector
            c_title = chart_symbol_select.input_value() if chart_symbol_select.count() > 0 else "N/A"
            
            # order ticket title: Heading in order entry card
            order_ticket_hdr = page.locator('h3:has-text("ORDER TICKET")').first
            ot_title = order_ticket_hdr.locator('span').first.inner_text() if order_ticket_hdr.is_visible() else "N/A"
            
            # active target: Active target from Option Chain Panel
            active_target_hud = page.locator('div:has-text("Active Target:")').last
            act_target = active_target_hud.locator('span.font-bold.text-cyan-400.font-mono').inner_text() if active_target_hud.is_visible() else "N/A"
            
            # watchlist entry added: Find the newly added element in watchlist matching the symbol
            watchlist_symbols = page.locator('span.truncate.uppercase.font-medium').all_inner_texts()
            added_entry = next((s for s in watchlist_symbols if "53600 CE" in s or "53600" in s and "CE" in s), "Not Found")
            
            return c_title, ot_title, act_target, added_entry

        c_title, ot_title, act_target, added_entry = dump_values()
        print(f"chart title: {c_title}")
        print(f"order ticket title: {ot_title}")
        print(f"active target: {act_target}")
        print(f"watchlist entry added: {added_entry}")

        # ----------------------------------------------------
        # 3. Wait 30 seconds
        # ----------------------------------------------------
        print("\n--- STEP 3: Wait 30 seconds ---")
        print("Waiting 30 seconds...")
        page.wait_for_timeout(30000)
        
        c_title, ot_title, act_target, added_entry = dump_values()
        print("Dump after 30 seconds:")
        print(f"chart title: {c_title}")
        print(f"order ticket title: {ot_title}")
        print(f"active target: {act_target}")
        print(f"watchlist entry added: {added_entry}")

        # ----------------------------------------------------
        # 4. Click 53600 PE in the Option Chain table
        # ----------------------------------------------------
        print("\n--- STEP 4: Click 53600 PE ---")
        
        # PE LTP button is the second button inside this tr
        pe_button = row_53600.locator('button').nth(1)
        pe_button.click()
        print("Clicked 53600 PE button.")
        page.wait_for_timeout(2000)
        
        c_title, ot_title, act_target, added_entry = dump_values()
        watchlist_symbols = page.locator('span.truncate.uppercase.font-medium').all_inner_texts()
        pe_added_entry = next((s for s in watchlist_symbols if "53600 PE" in s or "53600" in s and "PE" in s), "Not Found")
        
        print("Dump after clicking 53600 PE:")
        print(f"chart title: {c_title}")
        print(f"order ticket title: {ot_title}")
        print(f"active target: {act_target}")
        print(f"watchlist entry added: {pe_added_entry}")

        # ----------------------------------------------------
        # 5. Export localStorage: valkyrie_watchlist
        # ----------------------------------------------------
        print("\n--- STEP 5: Export localStorage: valkyrie_watchlist ---")
        valkyrie_watchlist = page.evaluate("window.localStorage.getItem('valkyrie_watchlist')")
        
        if valkyrie_watchlist:
            try:
                parsed_watchlist = json.loads(valkyrie_watchlist)
                formatted_watchlist = json.dumps(parsed_watchlist, indent=2)
                print(formatted_watchlist)
            except Exception as ex:
                print(f"Error parsing watchlist local storage value: {ex}")
                print(valkyrie_watchlist)
        else:
            print("null (or not found)")

        browser.close()

if __name__ == "__main__":
    main()
