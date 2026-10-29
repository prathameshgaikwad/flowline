import json
import subprocess
import sys
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parent.parent


def test_cli_end_to_end_with_fake_provider(tmp_path):
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/demo_cli.py",
            "--provider",
            "fake",
            "--approve",
            "--out",
            str(out_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads((out_dir / "design.json").read_text(encoding="utf-8"))
    assert payload["counts"]["ERROR"] == 0
    assert len(payload["design"]["fixtures"]) == 3
    assert len(payload["design"]["pipes"]) == 3
    assert (out_dir / "preview.svg").exists()
    assert (out_dir / "audit.jsonl").exists()

    dxf_path = next(out_dir.glob("*.dxf"))
    doc = ezdxf.readfile(dxf_path)
    layers = {layer.dxf.name for layer in doc.layers}
    assert {"P-SOIL", "P-WASTE", "P-FIXTURE", "P-STACK"} <= layers
