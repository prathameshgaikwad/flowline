# Hackathon submission

**Event:** Meta Global AI Developer Hackathon (Cerebral Valley), Oct 26 – Nov 4, 2026.
**Track:** Indie developer.
**Theme:** Build for Your World.
**Project:** Flowline — agentic bathroom plumbing design for AutoCAD-native workflows.
**Repo:** https://github.com/prathameshgaikwad/flowline
**Video:** _add the 3-minute video link before submitting._

## One-liner

Flowline turns a DXF floor plan into ranked bathroom drainage layouts, routes them to a stack, validates every rule with a source, self-corrects with deterministic fixes, and exports an AutoCAD-ready DXF — with Meta Muse Spark coordinating the workflow and deterministic Python doing the engineering math.

## Problem

Small MEP consultancies and design-build contractors redraw the same bathroom drainage layouts by hand in AutoCAD. The work is repetitive, clearance/slope mistakes surface late in coordination, and full BIM/calculation suites are too heavy or expensive for the job. The engineer's judgment is valuable; the drafting and checking loop is not.

## Solution

- Upload a DXF, select the wet area and stack, choose an India or US rule pack.
- The deterministic engine generates ranked layout candidates.
- The agent inspects the plan, selects a candidate with a rationale, routes each fixture to the stack, and validates the result.
- Every validation result names a rule, measured value, required value, and source.
- When the first layout produces warnings/errors, the agent applies a deterministic fix, revalidates, and explains the final design.
- The engineer reviews and approves; Flowline writes the pipes, fixtures, labels, and stack onto the source DXF.

## How Meta is used

- **Muse Spark 1.3** through Meta Model API, OpenAI-compatible Chat Completions with function tools.
- The model runs a multi-step loop: inspect → list layouts → select → route → validate → fix → validate → explain.
- The model is restricted to the tool surface. It does not invent dimensions, sizes, slopes, or rule values.
- Provider strategy: first-party Meta Model API if `META_API_KEY`/`MODEL_API_KEY` is set; otherwise OpenRouter with `OPENROUTER_MODEL=meta/muse-spark-1.3`, which is the same Meta model; a deterministic fake provider for offline tests and demos.
- The live trace and audit log show the provider, model, tool, input, result, and duration.

## Why it works

- **Deterministic boundary:** geometry, pipe sizes, slopes, routing, and rule outcomes are Python; the model only coordinates.
- **Cited rule packs:** India (`NBC 2016` / `IS 1742` with IPC clearances) and US (`IPC 2021`) YAML profiles. Every result carries its source.
- **Human gate:** export requires explicit approval; the report includes the approver, counts, warnings, assumptions, and disclaimer.
- **CAD-native:** DXF in/out; the exported file opens in ordinary AutoCAD. Live AutoCAD handoff is a separate script.
- **Tested:** unit, integration, API, UI smoke, and an end-to-end DXF round-trip; CI runs lint and tests.

## Rubric mapping

| Criterion | Evidence |
|---|---|
| Impact 30% | A real, repetitive workflow for small AutoCAD-native firms; minutes instead of hand drafting; reviewable rule trail. |
| Meta AI tooling 25% | Multi-step Muse Spark tool loop, structured tool results, live trace, provider strategy, offline fallback. |
| Demo 25% | Working upload → agent → validation → fix → approved DXF → AutoCAD; sample plan included. |
| Technical depth 20% | DXF parsing, unit conversion, candidate generation, A* routing, two cited rule packs, deterministic fixes, audit log, tests, CI. |

## New-work statement

The repository was created and first committed on 2026-10-29, during the hackathon. The older private `plumbing-agent` POC is not a dependency and none of its source was copied into this repo. The code in this repo was written for this submission.

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# add META_API_KEY
python scripts/check_provider.py
python scripts/make_sample_plan.py
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. The sample apartment loads automatically.

## Limitations

- Drainage-only; no water supply or vent geometry.
- Simple rectangular rooms; the layout uses the bounding box and warns otherwise.
- Clean DXF plans; legacy polylines/xrefs need hardening.
- POC rule packs, not compliance certificates.
- No DWG write; use AutoCAD to save the exported DXF as DWG.

## Next

Water supply and venting, kitchen/multi-room, PDF/image intake with Muse vision, DWG/ODA, AutoCAD LT/.NET plugin, Revit/IFC, rule-pack authoring, and engineer sign-off workflows. The commercial wedge is small MEP firms in India/MENA first, then the UK/US.
