from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402,F401  (loads .env)
from agent.logging import ActionLogger  # noqa: E402
from agent.loop import AgentRunner  # noqa: E402
from agent.providers.base import ConfigError  # noqa: E402
from agent.providers.factory import create_provider  # noqa: E402
from agent.tools import TOOLS, AgentSession  # noqa: E402
from core.dxf_import import import_dxf  # noqa: E402
from core.geometry import Point  # noqa: E402
from core.models import FixtureType, Stack  # noqa: E402
from core.rules.engine import load_profile, summarize, validate_design  # noqa: E402
from core.svg import render_svg  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Flowline agent end to end.")
    parser.add_argument("--sample", default=str(ROOT / "samples" / "apartment.dxf"))
    parser.add_argument("--room", default=None)
    parser.add_argument("--stack-x", type=float, default=None)
    parser.add_argument("--stack-y", type=float, default=None)
    parser.add_argument(
        "--fixtures",
        nargs="+",
        default=["WC", "BASIN", "SHOWER"],
        choices=[item.value for item in FixtureType],
    )
    parser.add_argument("--profile", default="india_nbc_2016")
    parser.add_argument("--provider", default="auto", choices=["auto", "meta", "openrouter", "fake"])
    parser.add_argument("--request", default="Design the bathroom drainage and explain any warnings.")
    parser.add_argument("--out", default=str(ROOT / "out"))
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()

    import os

    os.environ["LLM_PROVIDER"] = args.provider
    try:
        provider = create_provider()
    except ConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2

    building = import_dxf(args.sample)
    room = None
    if args.room:
        room = building.room(args.room)
    elif building.wet_area_candidates():
        room = building.wet_area_candidates()[0]
    elif building.rooms:
        room = building.rooms[0]
    if room is None:
        print("No rooms found in the drawing.")
        return 1

    if args.stack_x is not None and args.stack_y is not None:
        stack = Stack(id="S1", position=Point(x=args.stack_x, y=args.stack_y))
    elif building.shafts:
        stack = Stack(id="S1", position=building.shafts[0].position)
    else:
        print("No shaft found; pass --stack-x and --stack-y.")
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    session = AgentSession(
        building=building,
        source_path=Path(args.sample),
        out_dir=out_dir,
        room_id=room.id,
        fixture_types=[FixtureType(value) for value in args.fixtures],
        stack=stack,
        profile_id=args.profile,
    )
    logger = ActionLogger(out_dir / "audit.jsonl")

    def on_event(event: dict) -> None:
        kind = event.get("type")
        if kind == "tool_call":
            print(f"[tool] {event['tool']} {event.get('arguments')}")
        elif kind == "tool_result":
            status = "OK" if event.get("success") else "FAIL"
            print(f"[tool] {event['tool']} -> {status}")
        elif kind == "final":
            print(f"[agent] {event['content']}")

    runner = AgentRunner(
        provider,
        max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "12")),
        logger=logger,
        on_event=on_event,
    )
    print(f"provider={provider.name} model={provider.model}")
    result = runner.run(args.request, session)

    profile = load_profile(session.profile_id)
    if session.design is not None:
        results = session.validation or validate_design(building, session.design, profile)
        counts = summarize(results)
        payload = {
            "provider": provider.name,
            "model": provider.model,
            "profile": profile.id,
            "profile_name": profile.name,
            "disclaimer": profile.disclaimer,
            "design": session.design.model_dump(mode="json"),
            "validation": [item.model_dump(mode="json") for item in results],
            "counts": counts,
            "applied_fixes": session.applied_fixes,
        }
        (out_dir / "design.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        (out_dir / "preview.svg").write_text(
            render_svg(building, session.design), encoding="utf-8"
        )
        print(f"[out] {out_dir / 'design.json'}")
        print(f"[out] {out_dir / 'preview.svg'}")
        print(f"[validation] {counts}")

        if args.approve and counts["ERROR"] == 0:
            session.approved = True
            exported = TOOLS["export_dxf"].run({}, session)
            print(f"[out] {exported['path']}")
        elif args.approve:
            print("[export] blocked: fix validation errors before export.")
        else:
            print("[export] draft only; rerun with --approve to write the DXF.")

    return 0 if result.stopped_reason == "final" else 1


if __name__ == "__main__":
    raise SystemExit(main())
