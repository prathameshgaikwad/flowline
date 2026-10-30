from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from core.models import Building


@dataclass
class Project:
    id: str
    name: str
    source_path: Path
    building: Building
    designs: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
