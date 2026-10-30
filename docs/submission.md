# Hackathon submission

**Event:** Meta Global AI Developer Hackathon (Cerebral Valley), Oct 26 – Nov 4, 2026.
**Track:** Indie developer.
**Theme:** Build for Your World.
**Project:** Flowline — a chat-first agentic MEP workspace for bathroom plumbing.
**Repo:** https://github.com/prathameshgaikwad/flowline
**Video:** _add the public demo video link before submitting. See `docs/demo-script.md`._

## One-liner

Flowline turns a DXF floor plan into a reviewed bathroom drainage design: a Meta Muse Spark agent inspects the plan, compares layouts, routes pipes, validates cited rules, applies deterministic fixes, and exports an AutoCAD-ready DXF — with every step, note, tool call, decision and rejected alternative visible in the workspace.

## Problem

Small MEP consultancies and design-build contractors redraw repetitive bathroom drainage by hand in AutoCAD. Clearance and slope mistakes surface late in coordination, and full BIM/calculation suites are too heavy or expensive for the job. The engineer's judgment matters; the drafting and checking loop should not be manual.

## Solution

- Upload a DXF, choose the wet area, stack, fixtures and standard.
- The deterministic engine generates ranked layouts; the agent selects one with a rationale.
- The chat shows the plan, provider reasoning or interim agent notes, tool calls/results, candidate scores, selected/rejected layouts, fix history, validation counts and citations.
- Follow-ups are stateful: "why did you reject C-2?", "validate with the US standard", "apply the best fix", "remove the shower".
- The engineer approves; Flowline overlays `P-SOIL`, `P-WASTE`, `P-FIXTURE`, `P-STACK`, `P-TEXT` and `P-ROOM` on the source DXF.

## How Meta is used

- **Muse Spark 1.3 Contributor** through OpenCode Go (`muse-spark-1.3-contributor`), with first-party Meta Model API support when `META_API_KEY` is available.
- Multi-turn function calling: inspect → layouts → select → route → validate → fix → explain → answer questions.
- The model coordinates; it never invents dimensions, pipe sizes, slopes or rule outcomes.
- Provider reasoning is captured when available; otherwise the model's interim notes are shown. The deterministic tool results remain authoritative.
- Provider strategy: Meta > OpenCode > OpenRouter > fake offline provider.

## Why it stands out

- **Chat-first, not a form.** The conversation is the main surface, with quick actions and a persistent mission-control panel.
- **Full visibility.** Plan checklist, reasoning/notes, tool timeline with arguments/results, candidate comparison, decision log, validation citations.
- **Deterministic boundary.** Geometry, pipe sizes, slopes, routing and rule checks are Python.
- **Cited rule packs.** India (`NBC 2016` / `IS 1742` with IPC clearances) and US (`IPC 2021`) profiles, switchable per design; changing the standard marks the design stale until revalidated.
- **Human gate.** Export requires explicit approval; errors block export.
- **CAD-native.** DXF in/out; the exported file opens in ordinary AutoCAD.
- **Persistent.** JSON workspaces, designs, messages, events and audit logs survive restarts.
- **Tested.** Unit, integration, API, multi-turn chat, persistence, reasoning parsing, UI smoke and an end-to-end DXF round-trip; CI runs lint and tests.

## Rubric mapping

| Criterion | Evidence |
|---|---|
| Impact 30% | Real repetitive workflow for small AutoCAD-native firms; reviewable rule trail. |
| Meta AI tooling 25% | Multi-step Muse Spark tool loop, provider reasoning/notes, stateful follow-ups, provider strategy. |
| Demo 25% | Working setup → chat → plan/reasoning → decisions/rejections → validation/fix → approve/DXF → AutoCAD. |
| Technical depth 20% | DXF parsing, unit conversion, candidate generation, A* routing, two cited rule packs, fixes, JSON persistence, audit log, tests, CI. |

## New-work statement

The repository was created and first committed on 2026-10-29, during the hackathon. The older private `plumbing-agent` POC is not a dependency and none of its source was copied into this repo. The code in this repo was written for this submission.

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# add META_API_KEY, or OpenCode Go / OpenRouter
cd frontend
npm install
npm run build
cd ..
python scripts/check_provider.py
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. The sample workspace loads automatically.

## Limitations

- No home/project grouping or project-level standards in this pass; the left rail has a per-workspace **Designs** list.
- Standards are per design; changing one requires revalidation.
- Drainage-only; water supply and vent geometry are not modeled.
- Simple rectangular rooms; clean DXF plans.
- POC rule packs, not compliance certificates.
- JSON persistence is local and single-user.
- No manual fixture dragging; the agent can change the fixture set and re-plan.
- No DWG write; use AutoCAD to save the exported DXF as DWG.

## Next

1. Home tab and projects with multiple drawings + project-level standards.
2. Manual fixture editing; water supply and venting.
3. PDF/image intake with Muse vision; DWG/ODA; AutoCAD LT/.NET plugin.
4. Revit/IFC, rule-pack authoring, project versions, engineer sign-off, BOQ.
