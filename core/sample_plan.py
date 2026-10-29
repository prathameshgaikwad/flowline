from __future__ import annotations

from pathlib import Path

import ezdxf


def build_apartment(path: str | Path) -> str:
    doc = _new_doc()
    msp = doc.modelspace()

    msp.add_lwpolyline(
        [(0, 0), (5400, 0), (5400, 3600), (0, 3600)],
        close=True,
        dxfattribs={"layer": "A-WALL"},
    )
    msp.add_lwpolyline(
        [(0, 0), (2400, 0), (2400, 1800), (0, 1800)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    msp.add_lwpolyline(
        [(2400, 0), (5400, 0), (5400, 3000), (2400, 3000)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    msp.add_lwpolyline(
        [(0, 1800), (2400, 1800), (2400, 3600), (0, 3600)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )

    for start, end in (
        ((2400, 0), (2400, 3000)),
        ((0, 1800), (2400, 1800)),
        ((2400, 3000), (5400, 3000)),
    ):
        msp.add_line(start, end, dxfattribs={"layer": "A-WALL"})

    _add_label(msp, "BATHROOM", (1200, 900))
    _add_label(msp, "BEDROOM", (3900, 1500))
    _add_label(msp, "KITCHEN", (1200, 2700))

    block = doc.blocks.new("DOOR_900")
    block.add_line((0, 0), (900, 0), dxfattribs={"layer": "A-DOOR"})
    block.add_arc((0, 0), 900, 0, 90, dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("DOOR_900", (1200, 0), dxfattribs={"layer": "A-DOOR"})

    msp.add_lwpolyline(
        [(2050, 0), (2350, 0), (2350, 300), (2050, 300)],
        close=True,
        dxfattribs={"layer": "A-SHAFT"},
    )
    _add_label(msp, "SHAFT", (2200, 150), height=100)

    return _save(doc, path)


def build_tight_bathroom(path: str | Path) -> str:
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (1500, 0), (1500, 1200), (0, 1200)],
        close=True,
        dxfattribs={"layer": "A-ROOM"},
    )
    _add_label(msp, "TOILET", (750, 600))

    block = doc.blocks.new("DOOR_750")
    block.add_line((0, 0), (750, 0), dxfattribs={"layer": "A-DOOR"})
    block.add_arc((0, 0), 750, 0, 90, dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("DOOR_750", (750, 0), dxfattribs={"layer": "A-DOOR"})

    msp.add_lwpolyline(
        [(1200, 900), (1500, 900), (1500, 1200), (1200, 1200)],
        close=True,
        dxfattribs={"layer": "A-SHAFT"},
    )
    _add_label(msp, "SHAFT", (1350, 1050), height=80)
    return _save(doc, path)


def _new_doc():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    for name, color in (
        ("A-WALL", 8),
        ("A-ROOM", 151),
        ("A-DOOR", 30),
        ("A-SHAFT", 5),
        ("A-TEXT", 7),
    ):
        doc.layers.add(name, color=color)
    return doc


def _add_label(msp, text: str, position: tuple[float, float], height: float = 150) -> None:
    msp.add_text(text, dxfattribs={"layer": "A-TEXT", "height": height}).set_placement(position)


def _save(doc, path: str | Path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(target)
    return str(target)
