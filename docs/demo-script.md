# Flowline demo script

**Primary judging artifact.** One journey: a DXF floor plan to a reviewed, validated DXF. Show the product working, not slides. The live run must use a Meta model (`muse-spark-1.3` or `muse-spark-1.3-contributor`).

## Pre-flight

1. `frontend` is built (`npm run build`); `python -m uvicorn app.main:app --reload` is running.
2. `.env` has a working provider. Current demo: `OPENCODE_PLAN=go`, `OPENCODE_CLI_AUTH=true`, `OPENCODE_MODEL=muse-spark-1.3-contributor`.
3. `python scripts/check_provider.py` prints the provider, a Muse Spark model, and `PASS`.
4. Fresh workspace data is fine; the app auto-loads the sample if none exists.
5. Browser at `http://127.0.0.1:8000`, 1600×1000, 100% zoom.
6. Have the exported DXF ready to open in AutoCAD 2024.

## Beats

| Time | On screen | Narration |
|---|---|---|
| 0:00–0:20 | Workspace setup with the sample plan, room, stack, fixtures and India standard. | "Small MEP teams still draft the same bathroom drainage by hand. Flowline starts with the DXF they already have — and a Meta Muse Spark agent." |
| 0:20–0:40 | Click **Start design**. The chat shows the user message and the agent plan. | "Pick the wet area, stack, fixtures and standard. The agent inspects the drawing, generates layouts, and starts the design workflow." |
| 0:40–1:15 | Scroll the chat; show agent notes, tool calls and candidate comparison. Open the **Thinking** tab. | "Every step is visible: the plan, the model's notes or reasoning, every tool call and result, and the candidate scores. The model coordinates; Python owns the geometry." |
| 1:15–1:45 | Open the **Decisions** tab; show selected/rejected layouts, reasons, and the current design. | "The agent does not just pick a layout. It records what it rejected, why, and the rationale for the selected one. The candidate table is deterministic." |
| 1:45–2:10 | Open **Checks**; show counts, citations, warnings and recommended fixes. | "Every validation result carries a source. This is a POC rule pack, not a compliance certificate. A fix is one click or one chat message away." |
| 2:10–2:30 | Send a follow-up: "Why did you reject the other layouts?" The agent calls compare_layouts and answers. | "The conversation is stateful. The agent can explain its own decisions, revalidate with another standard, apply a fix, or change the fixture set." |
| 2:30–2:50 | Approve & export; show the download link. Open the DXF in AutoCAD; show `P-SOIL`, `P-WASTE`, `P-FIXTURE`. | "The engineer approves. Flowline overlays the pipes, fixtures, labels and stack on the source DXF. It opens in ordinary AutoCAD, not AutoCAD MEP." |
| 2:50–3:00 | Architecture/README diagram; end card. | "Chat-first, fully visible, deterministic engineering. Bathroom drainage first; projects, water supply, venting and Revit next." |

## What to emphasize

- **Impact:** repetitive bathroom drainage work for AutoCAD-native small firms.
- **Meta tooling:** multi-step Muse Spark tool use, provider reasoning/notes, live trace.
- **Demo:** working end-to-end; real DXF; real AutoCAD.
- **Depth:** deterministic boundary, cited rule packs, decisions/rejections, fixes, JSON audit trail, tests.

## Recording

`scripts/record_demo.py` captures a silent screen walkthrough. Update it to the current UI, record with the Meta model, then add narration in editing. The video can be shorter than three minutes; completeness and clarity matter more than length.

## Backup plan

If the provider is unavailable, run with `LLM_PROVIDER=fake` and label it "offline scripted agent" in the description. Do not claim a fake run is a Meta run. The repo, architecture, and screenshots remain valid.

## Checklist

- [ ] Provider badge shows a Meta model
- [ ] Setup starts with the sample plan
- [ ] Chat shows plan, agent notes/reasoning, tools, decisions, validation
- [ ] Follow-up question works
- [ ] Approval produces a downloadable DXF
- [ ] DXF opens in AutoCAD
- [ ] Video under 3:00
- [ ] Repo public; `.env` not committed; `data/`, `out/`, `frontend/node_modules` not committed
