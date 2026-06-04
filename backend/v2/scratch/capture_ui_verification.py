import asyncio
import os
import sqlite3
from playwright.async_api import async_playwright

def get_latest_session_id():
    conn = sqlite3.connect("backend/valkyrie_trades.db")
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM trade_sessions WHERE status='COMPLETED'")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

async def main():
    session_id = get_latest_session_id()
    print(f"[+] Latest completed Session ID in DB: {session_id}")
    
    print("[+] Launching headless browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        
        print("[+] Navigating to http://localhost:3000/ ...")
        await page.goto("http://localhost:3000/")
        await page.wait_for_timeout(3000)
        
        print("[+] Clicking on 'Paper Trading' navigation sidebar...")
        await page.click("text=Paper Trading")
        await page.wait_for_timeout(3000)
        
        print("[+] Clicking on 'Paper Trading Journal' tab...")
        await page.click("text=Paper Trading Journal")
        await page.wait_for_timeout(3000)
        
        screenshot_dir = "/Users/rajumaharjan/.gemini/antigravity/brain/32969241-ec89-449b-9320-9d0ee4de9633"
        journal_path = os.path.join(screenshot_dir, "ui_journal.png")
        await page.screenshot(path=journal_path)
        print(f"[+] Saved Journal screenshot to: {journal_path}")
        
        if session_id:
            try:
                target_selector = f"text=#{session_id}"
                print(f"[+] Clicking latest session row selector: {target_selector}")
                await page.click(target_selector, timeout=5000)
                await page.wait_for_timeout(3000)
                
                inspector_path = os.path.join(screenshot_dir, "ui_inspector.png")
                await page.screenshot(path=inspector_path)
                print(f"[+] Saved Inspector screenshot to: {inspector_path}")
            except Exception as e:
                print(f"[!] Warning: Failed to click session row: {e}")
        else:
            print("[!] Warning: No completed session found to inspect.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
