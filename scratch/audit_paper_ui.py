import os
import sys
import json
from playwright.sync_api import sync_playwright

def run_audit():
    print("Initializing Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Large viewport to see everything clearly
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        url = "http://localhost:3000"
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        print("Clicking 'Paper Trading' in the sidebar...")
        paper_btn = page.locator('button:has-text("Paper Trading")').first
        if paper_btn.is_visible():
            paper_btn.click()
            print("Clicked 'Paper Trading' tab.")
        else:
            print("Error: Paper Trading button not visible in sidebar.")
            # Try by clicking selector
            print("Locators found for button:")
            buttons = page.locator('button').all_inner_texts()
            print("Buttons found:", buttons)
            sys.exit(1)
            
        page.wait_for_timeout(4000) # Wait for page and any data to render
        
        # Take Screenshot
        screenshot_path = "/Users/rajumaharjan/.gemini/antigravity/brain/32969241-ec89-449b-9320-9d0ee4de9633/paper_trading_audit.png"
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot successfully saved to {screenshot_path}")
        
        # Verify components visually and gather HTML/inner-texts to output
        print("\n=== STARTING VISUAL AUDIT CONTROLS DUMP ===")
        
        # 1. PAPER/LIVE Safety Banner
        banner = page.locator('div:has-text("PAPER TRADING SESSION ACTIVE")').first
        if not banner.is_visible():
            banner = page.locator('div:has-text("LIVE TRADING ACTIVE")').first
            
        banner_present = banner.is_visible()
        banner_text = banner.inner_text().strip() if banner_present else "N/A"
        print(f"Safety Banner Present: {banner_present}")
        print(f"Safety Banner Text: {banner_text}")
        
        # 2. Active Preset Card
        preset_card = page.locator('div:has-text("ACTIVE STRATEGY CONFIGURATION")').last
        preset_present = preset_card.is_visible()
        preset_text = preset_card.inner_text().strip() if preset_present else "N/A"
        print(f"Preset Card Present: {preset_present}")
        print(f"Preset Card Content:\n{preset_text}\n---")
        
        # 3. Session Runtime Clock
        clock_card = page.locator('div:has-text("SESSION EXECUTION CLOCK")').last
        clock_present = clock_card.is_visible()
        clock_text = clock_card.inner_text().strip() if clock_present else "N/A"
        print(f"Clock Card Present: {clock_present}")
        print(f"Clock Card Content:\n{clock_text}\n---")
        
        # 4. Session Summary Panel
        summary_card = page.locator('div:has-text("SESSION METRICS SUMMARY")').last
        summary_present = summary_card.is_visible()
        summary_text = summary_card.inner_text().strip() if summary_present else "N/A"
        print(f"Summary Card Present: {summary_present}")
        print(f"Summary Card Content:\n{summary_text}\n---")
        
        # 5. Last Signal Widget
        signal_card = page.locator('div:has-text("LAST SIGNAL GENERATED")').last
        signal_present = signal_card.is_visible()
        signal_text = signal_card.inner_text().strip() if signal_present else "N/A"
        print(f"Signal Card Present: {signal_present}")
        print(f"Signal Card Content:\n{signal_text}\n---")
        
        # Also print general layout hierarchy inside PaperMain
        print("\nAudit complete.")
        browser.close()

if __name__ == "__main__":
    run_audit()
