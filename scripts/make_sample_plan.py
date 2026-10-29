from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.sample_plan import build_apartment, build_tight_bathroom  # noqa: E402


def main() -> int:
    samples = ROOT / "samples"
    print(build_apartment(samples / "apartment.dxf"))
    print(build_tight_bathroom(samples / "tight_bathroom.dxf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
