# AutoCAD integration notes

**Date:** 2026-10-29. **Machine:** Windows, Python 3.13, full AutoCAD 2024 installed.

## What is verified

- `C:\Program Files\Autodesk\AutoCAD 2024\acad.exe` exists.
- The `AutoCAD.Application` COM ProgID is registered (`{8B4929F8-076F-4AEC-AFEE-8928747B7AE3}`).
- The hackathon demo therefore does **not** need AutoCAD: Flowline writes DXF with `ezdxf`, and AutoCAD opens DXF directly.
- A live handoff is available as a separate script:

```powershell
python scripts/send_to_autocad.py --dxf out\DESIGN-01.dxf
```

It attaches to a running full AutoCAD (or starts it), opens the exported drawing, and zooms extents. It never edits or saves the active user drawing.

## Options considered

| Option | Needs AutoCAD | Read | Write | Demo reliability | Verdict |
|---|---|---|---|---|---|
| `ezdxf` headless DXF | No | yes | yes | high | **Primary path** |
| COM / ActiveX (`pywin32`) | Full AutoCAD on Windows | yes | yes | medium | **Live handoff script** |
| AutoCAD LT AutoLISP file IPC | LT 2024+ | yes | yes | medium | Not needed; full AutoCAD is present |
| AutoCAD MCP server | Full AutoCAD or LT | yes | yes | medium | It is a wrapper over COM/ezdxf; direct is simpler |
| Autodesk Platform Services | Cloud, credentials | yes | yes | low for a hackathon | Later product path |
| Revit API | Revit | yes | yes | not installed | Later product path |

## Caveats

- AutoCAD LT does not expose ActiveX automation. LT 2024+ can be driven via AutoLISP file IPC, but that is a different bridge.
- COM is single-threaded and version-sensitive. Do not call it from a FastAPI worker thread; use the separate `scripts/send_to_autocad.py` process.
- `ezdxf` writes DXF, not DWG. AutoCAD can save the opened DXF as DWG if needed.
- The exporter preserves the source drawing and adds `P-SOIL`, `P-WASTE`, `P-VENT`, `P-FIXTURE`, `P-STACK`, `P-TEXT`, and `P-ROOM` layers.
- The live script is a demo convenience, not part of the tested core. The tested artifact is the DXF.

## Product path

- **Now:** DXF overlay for AutoCAD-native small firms; a plugin/COM bridge can live inside AutoCAD later.
- **Next:** AutoCAD LT AutoLISP bridge for the large LT installed base, or a .NET plugin for full AutoCAD.
- **Later:** Revit/IFC and APS for BIM-first firms. Do not make Revit the first integration; the first customer's workflow is 2D AutoCAD.
