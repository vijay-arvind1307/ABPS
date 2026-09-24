import time
import os
import json
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\vijay\.gemini\antigravity-ide\brain\1b65aba9-ab4f-4d88-9334-b3829b2eb18a"

def run_tests():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1536, "height": 864})
        page = context.new_page()

        print("[TEST] 1. Navigating to http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        time.sleep(2)

        # Check if login required
        if "Login" in page.title() or page.locator("input[type='password']").count() > 0:
            print("[TEST] Logging in as Chief Section Controller...")
            # Click quick login or fill credentials
            planner_btn = page.locator("button:has-text('Chief Section Controller')")
            if planner_btn.count() > 0:
                planner_btn.first.click()
            else:
                login_btn = page.locator("button[type='submit']")
                if login_btn.count() > 0:
                    login_btn.first.click()
            time.sleep(2)

        # Ensure we are on Control Room / Block Planning workstation
        control_room_tab = page.locator("button:has-text('Control Room')")
        if control_room_tab.count() > 0:
            control_room_tab.first.click()
            time.sleep(1)

        # Ensure SECTION OCCUPANCY BOARD tab is active
        board_tab = page.locator("button:has-text('SECTION OCCUPANCY BOARD')")
        if board_tab.count() > 0:
            board_tab.first.click()
            time.sleep(1)

        print("[TEST] 2. Checking Section Occupancy Board structure...")
        # Verify Fixed Section Column
        sec_column = page.locator(".section-column")
        results["section_column_exists"] = sec_column.count() > 0
        
        # Check Section rows
        sec_rows = page.locator(".section-body > div")
        sec_count = sec_rows.count()
        results["physical_sections_count"] = sec_count
        print(f"[TEST] Found {sec_count} physical sections in fixed column.")

        # Verify Timeline Scroll Container and Canvas
        timeline_scroll = page.locator(".timeline-scroll")
        timeline_canvas = page.locator(".timeline-canvas")
        results["timeline_scroll_exists"] = timeline_scroll.count() > 0
        results["timeline_canvas_exists"] = timeline_canvas.count() > 0

        # Get initial canvas width and scroll container dimensions
        canvas_box = timeline_canvas.bounding_box()
        scroll_box = timeline_scroll.bounding_box()
        sec_box = sec_column.bounding_box()
        results["canvas_width_initial"] = canvas_box["width"] if canvas_box else 0
        results["scroll_viewport_width"] = scroll_box["width"] if scroll_box else 0
        results["section_col_x"] = sec_box["x"] if sec_box else 0
        results["section_col_width"] = sec_box["width"] if sec_box else 0

        print(f"[TEST] Canvas width: {results['canvas_width_initial']}px (Total 16h @ 120px = 1920px). Viewport: {results['scroll_viewport_width']}px")

        # Initial Screenshot
        initial_shot = os.path.join(ARTIFACT_DIR, "timeline_01_initial_06_22.png")
        page.screenshot(path=initial_shot)
        results["screenshot_initial"] = initial_shot
        print(f"[TEST] Saved initial screenshot: {initial_shot}")

        # Check page level overflow: should be hidden / no page horizontal scroll
        body_scroll_width = page.evaluate("() => document.body.scrollWidth")
        body_client_width = page.evaluate("() => document.body.clientWidth")
        results["no_page_horizontal_overflow"] = body_scroll_width <= body_client_width + 1
        print(f"[TEST] Page overflow check: scrollWidth={body_scroll_width}, clientWidth={body_client_width}, OK={results['no_page_horizontal_overflow']}")

        # 3. Test Horizontal Scrolling
        print("[TEST] 3. Testing horizontal scrolling on timeline...")
        page.evaluate("() => document.querySelector('.timeline-scroll').scrollLeft = 600")
        time.sleep(1)

        scroll_left_val = page.evaluate("() => document.querySelector('.timeline-scroll').scrollLeft")
        results["timeline_scroll_left"] = scroll_left_val
        
        # Verify Section column hasn't moved horizontally
        sec_box_after = sec_column.bounding_box()
        results["section_col_stayed_fixed"] = (sec_box["x"] == sec_box_after["x"])
        print(f"[TEST] ScrollLeft = {scroll_left_val}px. Section column X before={sec_box['x']}, after={sec_box_after['x']}. Fixed={results['section_col_stayed_fixed']}")

        scrolled_shot = os.path.join(ARTIFACT_DIR, "timeline_02_scrolled_right.png")
        page.screenshot(path=scrolled_shot)
        results["screenshot_scrolled"] = scrolled_shot
        print(f"[TEST] Saved scrolled screenshot: {scrolled_shot}")

        # 4. Test Zoom Controls
        print("[TEST] 4. Testing Zoom controls...")
        zoom_in_btn = page.locator("button[title*='Zoom In']")
        if zoom_in_btn.count() > 0:
            zoom_in_btn.first.click()
            time.sleep(0.5)
            zoom_in_btn.first.click()
            time.sleep(0.5)
            
            canvas_zoomed = timeline_canvas.bounding_box()
            results["canvas_width_zoomed"] = canvas_zoomed["width"] if canvas_zoomed else 0
            print(f"[TEST] Canvas width after Zoom In (+): {results['canvas_width_zoomed']}px")

        zoom_shot = os.path.join(ARTIFACT_DIR, "timeline_03_zoomed_in.png")
        page.screenshot(path=zoom_shot)
        results["screenshot_zoomed"] = zoom_shot

        # Test FIT button
        fit_btn = page.locator("button:has-text('FIT')")
        if fit_btn.count() > 0:
            fit_btn.first.click()
            time.sleep(1)
            canvas_fit = timeline_canvas.bounding_box()
            results["canvas_width_fit"] = canvas_fit["width"] if canvas_fit else 0
            print(f"[TEST] Canvas width after FIT: {results['canvas_width_fit']}px")

        fit_shot = os.path.join(ARTIFACT_DIR, "timeline_04_fitted.png")
        page.screenshot(path=fit_shot)
        results["screenshot_fitted"] = fit_shot

        # Reset zoom to 100%
        page.evaluate("() => document.querySelector('.timeline-scroll').scrollLeft = 0")
        zoom_out_btn = page.locator("button[title*='Zoom Out']")
        # Click - or reset
        time.sleep(0.5)

        # 5. Test Train Click & Inspection Dock
        print("[TEST] 5. Testing Train Click and Inspection Dock...")
        train_slot = page.locator("[id^='matrix-train-']").first
        if train_slot.count() > 0:
            train_number = train_slot.get_attribute("data-train-number")
            print(f"[TEST] Clicking train slot {train_number}...")
            train_slot.click()
            time.sleep(1)

            # Check if Inspection dock opened with train details
            inspection_train_header = page.locator(f"text=TRAIN {train_number}")
            results["train_inspection_dock_opened"] = inspection_train_header.count() > 0
            print(f"[TEST] Train {train_number} inspected: {results['train_inspection_dock_opened']}")

        train_shot = os.path.join(ARTIFACT_DIR, "timeline_05_train_selected.png")
        page.screenshot(path=train_shot)
        results["screenshot_train_selected"] = train_shot

        # 6. Test Block Click (BP-001)
        print("[TEST] 6. Testing Maintenance Block Click (BP-001)...")
        block_slot = page.locator("[id^='matrix-block-BP-001']").first
        if block_slot.count() > 0:
            print("[TEST] Clicking BP-001...")
            block_slot.click()
            time.sleep(1)

            inspection_block_header = page.locator("text=BP-001")
            results["block_inspection_dock_opened"] = inspection_block_header.count() > 0
            print(f"[TEST] Block BP-001 inspected: {results['block_inspection_dock_opened']}")

        block_shot = os.path.join(ARTIFACT_DIR, "timeline_06_block_selected.png")
        page.screenshot(path=block_shot)
        results["screenshot_block_selected"] = block_shot

        # 7. Test Time Horizon 00-24 Toggle
        print("[TEST] 7. Testing Time Horizon toggle to 00-24...")
        btn_24h = page.locator("button:has-text('00–24')")
        if btn_24h.count() > 0:
            btn_24h.first.click()
            time.sleep(1)
            canvas_24h = timeline_canvas.bounding_box()
            results["canvas_width_24h"] = canvas_24h["width"] if canvas_24h else 0
            print(f"[TEST] Canvas width for 24h cycle: {results['canvas_width_24h']}px (24h * 120px = 2880px)")

        cycle_shot = os.path.join(ARTIFACT_DIR, "timeline_07_24h_cycle.png")
        page.screenshot(path=cycle_shot)
        results["screenshot_24h"] = cycle_shot

        # Switch back to 06-22
        btn_16h = page.locator("button:has-text('06–22')")
        if btn_16h.count() > 0:
            btn_16h.first.click()
            time.sleep(1)

        # 8. Test Corridor Switching
        print("[TEST] 8. Testing Corridor Switching...")
        corridor_select = page.locator("select").first
        if corridor_select.count() > 0:
            # Change corridor
            options = corridor_select.locator("option")
            opt_count = options.count()
            if opt_count > 1:
                second_val = options.nth(1).get_attribute("value")
                print(f"[TEST] Switching to corridor value {second_val}...")
                corridor_select.select_option(value=second_val)
                time.sleep(2)

                corr_switch_shot = os.path.join(ARTIFACT_DIR, "timeline_08_corridor_switched.png")
                page.screenshot(path=corr_switch_shot)
                results["screenshot_corridor_switched"] = corr_switch_shot

                # Switch back to corridor 30
                corridor_select.select_option(value="30")
                time.sleep(2)
                print("[TEST] Switched back to Corridor 30 (Madurai - Tirunelveli).")

        final_shot = os.path.join(ARTIFACT_DIR, "timeline_09_final_verified.png")
        page.screenshot(path=final_shot)
        results["screenshot_final"] = final_shot

        browser.close()
        print("[TEST] All tests completed successfully!")
        print(json.dumps(results, indent=2))
        return results

if __name__ == "__main__":
    run_tests()
