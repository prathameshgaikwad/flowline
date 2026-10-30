from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)


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
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        page.wait_for_selector("[data-testid=start-design]", timeout=30000)
        page.screenshot(path=str(OUT / "v2-setup.png"), full_page=True)

        page.locator("[data-testid=start-design]").click()
        page.wait_for_selector("[data-testid=agent-turn]", timeout=30000)
        page.wait_for_selector("[data-testid=approve-button]:not([disabled])", timeout=90000)
        page.wait_for_timeout(1000)
        assert (
            "0 error"
            in page.locator("[data-testid=validation-panel]").first.inner_text()
        )
        agent_text = page.locator("[data-testid=agent-turn]").first.inner_text().lower()
        assert "model reasoning" in agent_text or "agent note" in agent_text
        page.screenshot(path=str(OUT / "v2-design.png"), full_page=True)

        page.locator("[data-testid=mission-tab-thinking]").click()
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "v2-thinking.png"), full_page=True)
        page.locator("[data-testid=mission-tab-decisions]").click()
        page.wait_for_timeout(300)
        assert (
            "layout selected"
            in page.locator("[data-testid=mission-control]").inner_text().lower()
        )
        page.screenshot(path=str(OUT / "v2-decisions.png"), full_page=True)
        page.locator("[data-testid=mission-tab-validation]").click()
        page.wait_for_timeout(300)
        assert (
            "pass"
            in page.locator(
                "[data-testid=mission-control] [data-testid=validation-panel]"
            ).inner_text()
        )
        page.screenshot(path=str(OUT / "v2-validation.png"), full_page=True)
        page.locator("[data-testid=mission-tab-activity]").click()
        page.wait_for_timeout(300)
        assert "list_layout_options" in page.locator("[data-testid=mission-control]").inner_text()

        page.fill("[data-testid=composer]", "Why did you reject the other layouts?")
        page.locator("[data-testid=send-message]").click()
        page.wait_for_selector("[data-testid=approve-button]:not([disabled])", timeout=90000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "v2-followup.png"), full_page=True)

        page.locator("[data-testid=approve-button]").click()
        page.wait_for_selector("[data-testid=approval-dialog]", timeout=10000)
        page.locator("[data-testid=dialog-approve]").click()
        page.wait_for_selector("[data-testid=dialog-download]", timeout=30000)
        href = page.locator("[data-testid=dialog-download]").get_attribute("href")
        assert href and "/download.dxf" in href
        page.screenshot(path=str(OUT / "v2-approved.png"), full_page=True)
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
    print("UI V2 SMOKE PASS")
    for name in (
        "v2-setup.png",
        "v2-design.png",
        "v2-thinking.png",
        "v2-decisions.png",
        "v2-validation.png",
        "v2-followup.png",
        "v2-approved.png",
    ):
        print(f"screenshot: {OUT / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
