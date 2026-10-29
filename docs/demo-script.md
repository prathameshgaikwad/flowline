# Flowline 3-minute demo script

**Primary judging artifact.** One journey: a real floor plan to a reviewed, validated DXF. Show the product working, not slides. The live run must use Meta Model API (`muse-spark-1.3`); the fake provider is only the offline fallback.

## Pre-flight

1. `.env` contains `META_API_KEY=...` (preferred) or `OPENROUTER_API_KEY=...` with `OPENROUTER_MODEL=meta/muse-spark-1.3`; `python scripts/check_provider.py` prints `provider=meta` or `provider=openrouter`, `model=muse-spark-1.3`/`meta/muse-spark-1.3`, and `PASS`.
2. `python scripts/make_sample_plan.py` has generated both samples.
3. `uvicorn app.main:app --reload` is running; the browser is at `http://127.0.0.1:8000`.
4. The provider badge shows the Meta model: **Meta · muse-spark-1.3** or **OpenRouter · meta/muse-spark-1.3**. The profile is **India - NBC 2016 / IS 1742 (POC)**.
5. Close other tabs. Zoom the browser to a readable size. Hide the bookmarks bar.
6. Have `out/ui-design.png` and `out/DESIGN-01.dxf` ready as backup artifacts.

## Beats

| Time | On screen | Narration |
|---|---|---|
| 0:00–0:20 | Flowline landing with the sample apartment; the plan is visible; the agent panel is idle. | "Small MEP teams still redraw the same bathroom drainage by hand. One missed clearance or slope becomes a coordination problem on site. Flowline is an agentic MEP designer for the tools they already use: AutoCAD." |
| 0:20–0:40 | Click the BATHROOM room; the bathroom highlights; show the shaft and fixtures; switch to the US profile and back to India to show the rule-pack control. | "Upload a DXF, pick the wet area, pick the stack, and choose the rule pack. This is a 4.3-square-metre bathroom with a shaft on the right." |
| 0:40–1:15 | Click **Design bathroom**. Show the live agent trace: inspect_plan, list_layout_options, select_layout. Point at the candidate scores and the agent's rationale. | "The agent inspects the plan, asks the deterministic engine for candidate layouts, and selects one with a reason. The model never invents a dimension. It chooses among engineered options." |
| 1:15–1:45 | Routing and validation scroll into view. Show 54 pass, 1 warning, 0 errors; show the POC warning and its source. | "The engine routes each fixture to the stack, assigns the profile's pipe sizes and slopes, and checks every rule. Each result carries its source. This is a POC rule pack, not a compliance certificate, and the UI says so." |
| 1:45–2:10 | Scroll to the agent trace; show the apply_fix events; point at the final layout changing from C-01 to C-02. | "The agent found a better layout after routing: it switched candidates, revalidated, and reduced the warnings. That is the agentic loop: inspect, choose, route, validate, correct." |
| 2:10–2:35 | Click **Approve & export**; open the downloaded DXF in AutoCAD 2024 (or show the exported layers in the viewer); show `P-SOIL`, `P-WASTE`, `P-FIXTURE`. | "The engineer reviews and approves. Flowline writes the pipes, fixtures, labels, and stack onto the source DXF. It opens in ordinary AutoCAD, not AutoCAD MEP." |
| 2:35–2:55 | Show the architecture slide or the README diagram: browser → agent → deterministic tools → DXF; provider badge. | "Muse Spark coordinates. The planner, router, rule packs, and fix engine are deterministic Python. Meta's model is doing what it is good at, while the engineering stays auditable." |
| 2:55–3:00 | End card: Flowline, the wedge, the roadmap. | "Flowline: from floor plan to reviewed plumbing, in minutes. Bathroom drainage first, then water supply, venting, and Revit." |

## What to emphasize

- **Impact:** repetitive bathroom drainage work, AutoCAD-native, small-firm economics.
- **Meta tooling:** multi-step tool use, structured tool results, provider strategy, live trace.
- **Demo:** working end-to-end, not a mock; real DXF; real AutoCAD.
- **Depth:** deterministic boundary, cited rules, fixes, audit log, tests.

## Backup plan

If the Meta API is unavailable during recording:

1. Keep the Meta provider configured; show the health check failure honestly.
2. Record the same flow with the fake provider and label it "offline scripted agent" in the video description; do not claim it is Meta.
3. Submit the repo and the architecture; the live final round will test the real integration.

Do not fake a Meta run. The hackathon requires genuine Meta model use.

## Filming checklist

- [ ] 1920×1080 browser, 100% zoom
- [ ] No console errors; no stale servers
- [ ] Meta badge visible
- [ ] Sample plan loaded
- [ ] Agent run under 60 seconds
- [ ] Export completed; DXF opens in AutoCAD
- [ ] Captions or clear narration
- [ ] Video under 3:00
- [ ] Repo public; `.env` not committed; `out/` not committed
