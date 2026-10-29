from __future__ import annotations

import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)


def main() -> int:
    print("Recording Flowline demo. Start uvicorn on http://127.0.0.1:8000 first.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1500, "height": 980},
            record_video_dir=str(OUT / "video"),
            record_video_size={"width": 1500, "height": 980},
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        page.wait_for_selector("#project-summary:not(.hidden)", timeout=20000)
        page.wait_for_timeout(2200)
        page.locator(".room-card").first.click()
        page.wait_for_timeout(1400)
        page.locator("#profile-select").select_option("us_ipc_2021")
        page.wait_for_timeout(1000)
        page.locator("#profile-select").select_option("india_nbc_2016")
        page.wait_for_timeout(1200)

        page.locator("#design-button").click()
        page.wait_for_selector("#approve-button:not([disabled])", timeout=180000)
        page.wait_for_timeout(1600)
        page.locator("#validation").scroll_into_view_if_needed()
        page.wait_for_timeout(1800)
        page.locator("#approve-button").click()
        page.wait_for_selector("#download-link:not(.hidden)", timeout=30000)
        page.wait_for_timeout(2200)

        video = page.video
        context.close()
        browser.close()
        if video:
            source = Path(video.path())
            target = OUT / "demo.webm"
            shutil.move(str(source), str(target))
            print(f"video: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
