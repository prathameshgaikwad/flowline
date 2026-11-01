from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
BASE_URL = os.getenv("FLOWLINE_UI_URL", "http://127.0.0.1:8000")


def main() -> int:
    page_errors: list[str] = []
    console_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid=start-design]", timeout=30000)
        assert page.locator("[data-testid=start-design]").is_enabled()
        page.screenshot(path=str(OUT / "v3-setup.png"), full_page=True)

        before = page.locator("[data-testid=plan-canvas]").bounding_box()
        handle = page.locator("[data-testid=splitter]").bounding_box()
        assert before and handle
        page.mouse.move(
            handle["x"] + handle["width"] / 2,
            handle["y"] + handle["height"] / 2,
        )
        page.mouse.down()
        page.mouse.move(
            handle["x"] + handle["width"] / 2 + 120,
            handle["y"] + handle["height"] / 2,
            steps=6,
        )
        page.mouse.up()
        after = page.locator("[data-testid=plan-canvas]").bounding_box()
        assert after and after["width"] > before["width"] + 40
        page.locator("[data-testid=splitter]").dblclick()
        page.wait_for_timeout(250)
        plan_before_work = page.locator("[data-testid=plan-canvas]").bounding_box()
        assert plan_before_work

        page.locator("[data-testid=start-design]").click()
        page.wait_for_selector("[data-testid=agent-turn]", timeout=30000)
        plan_during_work = page.locator("[data-testid=plan-canvas]").bounding_box()
        assert plan_during_work
        assert abs(plan_during_work["width"] - plan_before_work["width"]) <= 2
        page.wait_for_selector("[data-testid=approve-button]:not([disabled])", timeout=90000)
        page.wait_for_timeout(1000)
        plan_after_work = page.locator("[data-testid=plan-canvas]").bounding_box()
        assert plan_after_work
        assert abs(plan_after_work["width"] - plan_before_work["width"]) <= 2
        page.screenshot(path=str(OUT / "v3-design.png"), full_page=True)
        assert page.locator("[data-testid=summary-card]").first.is_visible()
        summary_text = page.locator("[data-testid=summary-card]").first.inner_text().lower()
        assert "bathroom" in summary_text or "plan" in summary_text
        page.wait_for_selector("[data-testid=view-sheet]", timeout=30000)
        pdf_href = page.locator("[data-testid=summary-sheet-pdf]").first.get_attribute("href")
        assert pdf_href and "/sheet.pdf" in pdf_href

        page.locator("[data-testid=view-sheet]").click()
        page.wait_for_selector("[data-testid=sheet-canvas]", timeout=10000)
        page.wait_for_selector("[data-testid=sheet-canvas] svg", timeout=30000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "v3-sheet.png"), full_page=True)

        page.locator("[data-testid=sheet-settings-button]").click()
        page.locator("[data-testid=sheet-preset]").select_option("A4")
        page.locator("[data-testid=sheet-apply]").click()
        page.wait_for_function(
            "() => document.querySelector('[data-testid=summary-card]')?.innerText.includes('A4')",
            timeout=60000,
        )
        page.wait_for_timeout(1500)
        page.locator("[data-testid=sheet-settings-button]").click()
        page.screenshot(path=str(OUT / "v3-sheet-a4.png"), full_page=True)
        page.locator("[data-testid=sheet-back]").click()
        page.wait_for_selector("[data-testid=plan-canvas]", timeout=10000)

        page.locator("button[aria-label='Zoom in']").click()
        page.wait_for_timeout(200)
        assert "125%" in page.locator("[data-testid=plan-canvas]").inner_text()
        page.locator("[data-testid=fit-plan]").click()

        page.locator("[data-testid=details-button]").click()
        page.wait_for_selector("[data-testid=details-drawer]", timeout=10000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "v3-details-design.png"), full_page=True)
        page.locator("[data-testid=details-tab-checks]").click()
        page.wait_for_timeout(300)
        assert "passed" in page.locator("[data-testid=validation-panel]").inner_text().lower()
        page.screenshot(path=str(OUT / "v3-details-checks.png"), full_page=True)
        page.locator("[data-testid=details-tab-activity]").click()
        page.wait_for_timeout(300)
        assert "read the drawing" in page.locator("[data-testid=details-drawer]").inner_text().lower()
        page.screenshot(path=str(OUT / "v3-details-activity.png"), full_page=True)
        page.keyboard.press("Escape")
        page.wait_for_selector("[data-testid=details-drawer]", state="detached", timeout=5000)

        page.locator("[data-testid=fullscreen-button]").click()
        page.wait_for_selector("[data-testid=fullscreen-plan]", timeout=10000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "v3-fullscreen.png"), full_page=True)
        page.keyboard.press("Escape")
        page.wait_for_selector("[data-testid=fullscreen-plan]", state="detached", timeout=5000)

        page.fill("[data-testid=composer]", "Why did you reject the other layouts?")
        page.locator("[data-testid=send-message]").click()
        page.wait_for_selector("[data-testid=approve-button]:not([disabled])", timeout=90000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "v3-followup.png"), full_page=True)

        page.fill("[data-testid=composer]", "How do I reverse a palindrome?")
        page.locator("[data-testid=send-message]").click()
        page.wait_for_function(
            "() => !document.querySelector('[data-testid=composer]').disabled",
            timeout=30000,
        )
        page.wait_for_timeout(400)
        last_turn = page.locator("[data-testid=agent-turn]").last.inner_text().lower()
        assert "i can only help with this mep design" in last_turn
        page.screenshot(path=str(OUT / "v3-scope-refusal.png"), full_page=True)

        page.locator("[data-testid=approve-button]").click()
        page.wait_for_selector("[data-testid=approval-dialog]", timeout=10000)
        problems = page.get_by_test_id("approval-problems")
        assert problems.is_visible()
        assert "Issues to review" in problems.inner_text()
        page.locator("[data-testid=dialog-approve]").click()
        page.wait_for_selector("[data-testid=dialog-download]", timeout=30000)
        href = page.locator("[data-testid=dialog-download]").get_attribute("href")
        assert href and "/download.dxf" in href
        pdf = page.locator("[data-testid=dialog-pdf]").get_attribute("href")
        assert pdf and "/sheet.pdf" in pdf
        page.screenshot(path=str(OUT / "v3-approved.png"), full_page=True)

        page.keyboard.press("Escape")
        page.wait_for_selector("[data-testid=approval-dialog]", state="detached", timeout=5000)
        page.locator("[data-testid=workspace-trigger]").click()
        page.wait_for_selector("[data-testid=workspace-menu]", timeout=10000)
        page.locator("[data-testid=new-design]").click()
        page.wait_for_selector("[data-testid=new-design-workspace]", timeout=10000)
        page.wait_for_timeout(350)
        page.screenshot(path=str(OUT / "v3-new-design-workspace.png"), full_page=True)
        page.locator("[data-testid=blank-use-current]").click()
        page.wait_for_selector("[data-testid=start-design]", timeout=10000)

        page.locator("[data-testid=workspace-trigger]").click()
        page.wait_for_selector("[data-testid=workspace-menu]", timeout=10000)
        page.locator("[data-testid=new-design]").click()
        page.wait_for_selector("[data-testid=new-design-workspace]", timeout=10000)
        page.set_input_files(
            "[data-testid=start-upload]",
            str(ROOT / "samples" / "tight_bathroom.dxf"),
        )
        page.wait_for_selector("[data-testid=start-design]", timeout=30000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "v3-new-design-upload.png"), full_page=True)
        browser.close()

    filtered_console = [
        item for item in console_errors if "favicon" not in item.lower()
    ]
    if page_errors:
        print("PAGE ERRORS:", page_errors)
        return 1
    if filtered_console:
        print("CONSOLE ERRORS:", filtered_console)
        return 1
    print("UI V3 SMOKE PASS")
    for name in (
        "v3-setup.png",
        "v3-design.png",
        "v3-details-design.png",
        "v3-details-checks.png",
        "v3-details-activity.png",
        "v3-fullscreen.png",
        "v3-followup.png",
        "v3-scope-refusal.png",
        "v3-approved.png",
        "v3-sheet.png",
        "v3-sheet-a4.png",
        "v3-new-design-workspace.png",
        "v3-new-design-upload.png",
    ):
        print(f"screenshot: {OUT / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
