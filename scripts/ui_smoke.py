from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)


def main() -> int:
    errors: list[str] = []
    console_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 980})
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        page.wait_for_selector("#project-summary:not(.hidden)", timeout=15000)
        assert "Fake" in page.locator("#provider-badge").inner_text()
        assert page.locator(".room-card").count() >= 3
        page.screenshot(path=str(OUT / "ui-plan.png"), full_page=True)

        page.locator("#design-button").click()
        page.wait_for_selector("#approve-button:not([disabled])", timeout=45000)
        page.wait_for_selector("#final-answer:not(.hidden)", timeout=15000)
        counts = page.locator("#counts").inner_text()
        assert "0 error" in counts, counts
        assert page.locator("#candidates .candidate").count() >= 3
        page.screenshot(path=str(OUT / "ui-design.png"), full_page=True)

        page.locator("#tab-plan").click()
        page.wait_for_timeout(300)
        page.locator("#tab-design").click()

        approve = page.locator("#approve-button")
        approve.click()
        page.wait_for_selector("#download-link:not(.hidden)", timeout=20000)
        href = page.locator("#download-link").get_attribute("href")
        assert href and "/download.dxf" in href
        page.screenshot(path=str(OUT / "ui-approved.png"), full_page=True)
        browser.close()

    filtered_console = [item for item in console_errors if "favicon" not in item.lower()]
    if errors:
        print("PAGE ERRORS:", errors)
        return 1
    if filtered_console:
        print("CONSOLE ERRORS:", filtered_console)
        return 1
    print("UI SMOKE PASS")
    print(f"screenshots: {OUT / 'ui-plan.png'}, {OUT / 'ui-design.png'}, {OUT / 'ui-approved.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
