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
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid=select-all-plumbing]", timeout=30000)

        projects = page.request.get(f"{BASE_URL}/api/projects").json()["projects"]
        project = page.request.get(
            f"{BASE_URL}/api/projects/{projects[0]['project_id']}"
        ).json()
        bathroom = next(room for room in project["rooms"] if room["name"] == "BATHROOM")
        kitchen = next(room for room in project["rooms"] if room["name"] == "KITCHEN")
        bedroom = next(room for room in project["rooms"] if room["name"] == "BEDROOM")

        def selected(room_id: str) -> str:
            return page.get_by_test_id(f"setup-room-toggle-{room_id}").get_attribute(
                "aria-pressed"
            ) or "false"

        assert selected(bathroom["id"]) == "true"
        assert selected(kitchen["id"]) == "true"
        assert selected(bedroom["id"]) == "false"
        assert page.get_by_test_id(
            f"fixture-{kitchen['id']}-kitchen_sink"
        ).is_visible()
        page.screenshot(path=str(OUT / "qa-consolidated-setup.png"), full_page=True)

        page.locator(f'[data-room-id="{kitchen["id"]}"]').click()
        page.wait_for_timeout(200)
        assert selected(kitchen["id"]) == "false"
        page.get_by_test_id("select-all-plumbing").click()
        page.wait_for_timeout(200)
        assert selected(kitchen["id"]) == "true"
        assert "Design 2 areas" in page.get_by_test_id("start-design").inner_text()

        bathroom_shower = page.get_by_test_id(
            f"fixture-{bathroom['id']}-shower"
        )
        bathroom_floor_drain = page.get_by_test_id(
            f"fixture-{bathroom['id']}-floor_drain"
        )
        assert bathroom_shower.get_attribute("aria-pressed") == "true"
        bathroom_shower.click()
        bathroom_floor_drain.click()
        page.wait_for_timeout(200)
        assert bathroom_shower.get_attribute("aria-pressed") == "false"
        assert bathroom_floor_drain.get_attribute("aria-pressed") == "true"
        page.screenshot(
            path=str(OUT / "qa-consolidated-fixtures.png"), full_page=True
        )

        page.get_by_test_id("start-design").click()
        page.wait_for_selector("[data-testid=agent-turn]", timeout=30000)
        page.wait_for_selector(
            "[data-testid=approve-button]:not([disabled])", timeout=120000
        )
        page.wait_for_timeout(700)
        topbar = page.get_by_test_id("topbar").inner_text()
        assert "BATHROOM + KITCHEN" in topbar
        summary = page.get_by_test_id("summary-card").first.inner_text()
        assert "Plumbing design" in summary
        assert "2 areas" in summary
        page.screenshot(path=str(OUT / "qa-consolidated-design.png"), full_page=True)

        page.get_by_test_id("details-button").click()
        page.wait_for_selector("[data-testid=details-drawer]", timeout=10000)
        details = page.get_by_test_id("details-drawer").inner_text()
        assert "BATHROOM" in details
        assert "KITCHEN" in details
        page.keyboard.press("Escape")
        page.wait_for_selector(
            "[data-testid=details-drawer]", state="detached", timeout=5000
        )

        page.get_by_test_id("workspace-trigger").click()
        page.wait_for_selector("[data-testid=workspace-menu]", timeout=5000)
        menu_text = page.get_by_test_id("workspace-menu").inner_text()
        assert "BATHROOM + KITCHEN" in menu_text
        page.keyboard.press("Escape")

        refreshed = page.request.get(
            f"{BASE_URL}/api/projects/{project['project_id']}"
        ).json()
        design_id = refreshed["designs"][-1]["design_id"]
        design = page.request.get(f"{BASE_URL}/api/designs/{design_id}").json()
        assert set(design["room_ids"]) == {bathroom["id"], kitchen["id"]}
        assert design["sheet_ready"] is True
        assert len(design["design"]["room_plans"]) == 2
        fixtures_by_room = {
            plan["room_id"]: plan["fixture_types"]
            for plan in design["design"]["room_plans"]
        }
        assert "SHOWER" not in fixtures_by_room[bathroom["id"]]
        assert "FLOOR_DRAIN" in fixtures_by_room[bathroom["id"]]
        assert fixtures_by_room[kitchen["id"]] == ["KITCHEN_SINK"]
        assert any(pipe.get("room_id") == kitchen["id"] for pipe in design["design"]["pipes"])
        print("CONSOLIDATED SETUP PASS")
        print("CONSOLIDATED DESIGN PASS")
        browser.close()

    filtered = [item for item in console_errors if "favicon" not in item.lower()]
    print("PAGE ERRORS", page_errors)
    print("CONSOLE ERRORS", filtered)
    if page_errors or filtered:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
