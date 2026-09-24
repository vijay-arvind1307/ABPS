import time
import os
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\vijay\.gemini\antigravity-ide\brain\1b65aba9-ab4f-4d88-9334-b3829b2eb18a"

def capture_final_views():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1536, "height": 864})
        page = context.new_page()

        print("[TEST] Loading http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        time.sleep(1)

        # Login
        if page.locator("button:has-text('LOGIN TO PLANNING SYSTEM')").count() > 0:
            page.locator("button:has-text('LOGIN TO PLANNING SYSTEM')").first.click()

        # Wait for train elements to be rendered
        print("[TEST] Waiting for train elements to render on corridor 30...")
        page.wait_for_selector("[id^='matrix-train-']", state="visible", timeout=20000)
        time.sleep(1)

        # 1. 06-22 view at 100% zoom - Morning / Afternoon view (scrollLeft = 0)
        page.evaluate("() => document.querySelector('.timeline-scroll').scrollLeft = 0")
        time.sleep(1)
        shot1 = os.path.join(ARTIFACT_DIR, "final_06_22_morning_afternoon.png")
        page.screenshot(path=shot1)
        print(f"[TEST] Captured {shot1}")

        # 2. Scroll horizontally to 750px to view evening / night 15:00 - 22:00
        page.evaluate("() => document.querySelector('.timeline-scroll').scrollLeft = 750")
        time.sleep(1)
        shot2 = os.path.join(ARTIFACT_DIR, "final_06_22_evening_night.png")
        page.screenshot(path=shot2)
        print(f"[TEST] Captured {shot2}")

        # 3. Click 00-24 button
        btn_24h = page.locator("button:has-text('00–24')")
        if btn_24h.count() > 0:
            btn_24h.first.click()
            time.sleep(1)
            page.evaluate("() => document.querySelector('.timeline-scroll').scrollLeft = 0")
            time.sleep(1)
            shot3 = os.path.join(ARTIFACT_DIR, "final_00_24_full_cycle.png")
            page.screenshot(path=shot3)
            print(f"[TEST] Captured {shot3}")

        browser.close()
        print("[TEST] All final views captured successfully!")

if __name__ == "__main__":
    capture_final_views()
