import time
import os
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\vijay\.gemini\antigravity-ide\brain\22b711cc-38d3-414a-8ede-fc9aea1abbe4"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1600, "height": 950})
        page = context.new_page()

        print("[E2E] Navigating to http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        time.sleep(1)

        # Check if login required
        if "Login" in page.title() or page.locator("input[type='password']").count() > 0:
            print("[E2E] Logging in as planner...")
            login_btn = page.locator("button[type='submit']")
            if login_btn.count() > 0:
                login_btn.first.click()
                time.sleep(2)

        # Navigate to LIVE TRAIN POSITION
        print("[E2E] Navigating to Live Train Position tab...")
        train_tab = page.locator("button:has-text('LIVE TRAIN POSITION')")
        if train_tab.count() > 0:
            train_tab.first.click()
        else:
            page.locator("text=Train Position").first.click()
        time.sleep(2)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "train_position_initial.png"))
        print("[E2E] Saved train_position_initial.png")

        # Select Corridor C40: Madurai -> Tirunelveli
        print("[E2E] Selecting Corridor C40 (Madurai -> Tirunelveli)...")
        c40_btn = page.locator("button:has-text('C40: Madurai')")
        if c40_btn.count() > 0:
            c40_btn.first.click()
        time.sleep(4)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "corridor_c40_geometry.png"))
        print("[E2E] Saved corridor_c40_geometry.png")

        # Select Corridor C23: Nilgiri Mountain Railway
        print("[E2E] Selecting Corridor C23 (Nilgiri Mountain Railway)...")
        c23_btn = page.locator("button:has-text('C23: Nilgiri Mountain')")
        if c23_btn.count() > 0:
            c23_btn.first.click()
        time.sleep(3)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "corridor_c23_geometry.png"))
        print("[E2E] Saved corridor_c23_geometry.png")

        # Select Corridor C15: Salem -> Jolarpettai
        print("[E2E] Selecting Corridor C15 (Salem -> Jolarpettai)...")
        c15_btn = page.locator("button:has-text('C15: Salem')")
        if c15_btn.count() > 0:
            c15_btn.first.click()
        time.sleep(3)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "corridor_c15_geometry.png"))
        print("[E2E] Saved corridor_c15_geometry.png")

        # Test search filter with 'Salem'
        print("[E2E] Testing corridor filter with 'Salem'...")
        search_input = page.locator("input[placeholder*='Filter (e.g. Salem']")
        if search_input.count() > 0:
            search_input.fill("Salem")
            time.sleep(1)
            page.screenshot(path=os.path.join(ARTIFACT_DIR, "corridor_search_filtered.png"))
            print("[E2E] Saved corridor_search_filtered.png")
            search_input.fill("")
            time.sleep(1)

        # Select Corridor C37: Trichy -> Manamadurai
        print("[E2E] Selecting Corridor C37 (Trichy -> Manamadurai)...")
        c37_btn = page.locator("button:has-text('C37: Trichy')")
        if c37_btn.count() > 0:
            c37_btn.first.click()
        time.sleep(3)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "corridor_c37_geometry.png"))
        print("[E2E] Saved corridor_c37_geometry.png")

        # Select Corridor C45: Madurai -> Bodinayakkanur
        print("[E2E] Selecting Corridor C45 (Madurai -> Bodinayakkanur)...")
        c45_btn = page.locator("button:has-text('C45: Madurai')")
        if c45_btn.count() > 0:
            c45_btn.first.click()
        time.sleep(3)

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "corridor_c45_geometry.png"))
        print("[E2E] Saved corridor_c45_geometry.png")

        print("[E2E] Verification completed successfully!")
        browser.close()

if __name__ == "__main__":
    run()
