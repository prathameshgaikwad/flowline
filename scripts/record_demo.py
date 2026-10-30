from __future__ import annotations

import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)


def main() -> int:
    print("Recording Flowline. Start uvicorn on http://127.0.0.1:8000 first.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            record_video_dir=str(OUT / "video"),
            record_video_size={"width": 1600, "height": 1000},
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        page.wait_for_selector("[data-testid=start-design]", timeout=30000)
        page.wait_for_timeout(2600)

        page.locator("[data-testid=start-design]").click()
        page.wait_for_selector("[data-testid=agent-turn]", timeout=30000)
        page.wait_for_selector("[data-testid=approve-button]:not([disabled])", timeout=180000)
        page.wait_for_timeout(2200)

        page.locator("[data-testid=chat-messages]").evaluate("el => el.scrollTop = 0")
        page.wait_for_timeout(2400)
        page.locator("[data-testid=chat-messages]").evaluate(
            "el => el.scrollTop = el.scrollHeight"
        )
        page.wait_for_timeout(1800)

        page.locator("[data-testid=mission-tab-thinking]").click()
        page.wait_for_timeout(2400)
        page.locator("[data-testid=mission-tab-decisions]").click()
        page.wait_for_timeout(2400)
        page.locator("[data-testid=mission-tab-validation]").click()
        page.wait_for_timeout(2400)
        page.locator("[data-testid=mission-tab-activity]").click()
        page.wait_for_timeout(1800)

        page.fill(
            "[data-testid=composer]",
            "Why did you reject the other layouts?",
        )
        page.locator("[data-testid=send-message]").click()
        page.wait_for_selector("[data-testid=approve-button]:not([disabled])", timeout=180000)
        page.wait_for_timeout(2800)

        page.locator("[data-testid=approve-button]").click()
        page.wait_for_selector("[data-testid=approval-dialog]", timeout=15000)
        page.wait_for_timeout(1600)
        page.locator("[data-testid=dialog-approve]").click()
        page.wait_for_selector("[data-testid=dialog-download]", timeout=30000)
        page.wait_for_timeout(2400)

        video = page.video
        context.close()
        browser.close()
        if video:
            source = Path(video.path())
            target = OUT / "demo-v2.webm"
            shutil.move(str(source), str(target))
            print(f"video: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
