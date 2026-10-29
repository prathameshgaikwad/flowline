# Flowline

Agentic bathroom plumbing design for AutoCAD-native workflows.

Flowline reads a DXF floor plan, generates ranked bathroom drainage layouts, lets a Meta Muse Spark agent choose and explain one, routes the drainage to a stack, validates the result against cited India and US rule packs, applies deterministic fixes, and exports an AutoCAD-ready DXF.

The language model coordinates. The geometry, sizing, routing, and rule checks are deterministic.

**Status:** Hackathon MVP in progress (Meta Global AI Developer Hackathon, Indie track). Not a compliance tool.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Add your Meta key to `.env` (`META_API_KEY=...`) or use OpenRouter (`OPENROUTER_API_KEY=...`). Without either, the fake provider runs the scripted demo.

```powershell
python scripts/check_provider.py
python scripts/make_sample_plan.py
python scripts/demo_cli.py --provider fake --sample samples/apartment.dxf
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Provider strategy

```text
LLM_PROVIDER=auto
  META_API_KEY or MODEL_API_KEY -> Meta Model API (muse-spark-1.3)
  OPENROUTER_API_KEY            -> OpenRouter
  otherwise                     -> fake/scripted
```

Set `LLM_PROVIDER=meta`, `openrouter`, or `fake` to override. Missing keys for an explicit provider fail fast.

## Layout

```text
app/              FastAPI app, static UI, jobs, SSE
core/             units, geometry, models, DXF import/export, layout, router, rules, fixes, SVG
agent/            tools, prompt, loop, audit log, provider strategy
scripts/          samples, CLI demo, provider check, AutoCAD handoff
tests/            unit, integration, API, and end-to-end tests
docs/             design, standards, plan, demo script
```

## Standards

v1 ships two small cited packs: `india_nbc_2016` and `us_ipc_2021`. Every rule result includes a source. See [docs/standards.md](docs/standards.md).

> Flowline is a design assistant. It checks a small, cited rule pack, not the full code. A licensed engineer and the local authority govern the issued design.

## Tests

```powershell
pytest -q
python -m compileall app core agent scripts
```

## License

MIT
