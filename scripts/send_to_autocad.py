from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open a Flowline DXF in a running AutoCAD 2024 instance."
    )
    parser.add_argument("--dxf", required=True, help="Path to the exported DXF.")
    args = parser.parse_args()

    target = Path(args.dxf).resolve()
    if not target.exists():
        print(f"DXF not found: {target}")
        return 2

    try:
        import pythoncom
        import win32com.client
    except ImportError:
        print("pywin32 is not installed. Run: pip install pywin32")
        return 2

    pythoncom.CoInitialize()
    try:
        try:
            app = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception:
            app = win32com.client.Dispatch("AutoCAD.Application")
        try:
            app.Visible = True
        except Exception:
            pass
        app.Documents.Open(str(target))
        try:
            app.ZoomExtents()
        except Exception:
            pass
        print(f"Opened {target} in AutoCAD.")
        return 0
    except Exception as exc:
        print(f"AutoCAD automation failed: {exc}")
        return 1
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
