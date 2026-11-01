from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ezdxf  # noqa: E402

from core.dxf_import import _iter_entities, import_dxf  # noqa: E402
from core.geometry import Point, bbox  # noqa: E402
from core.svg import render_svg  # noqa: E402

SANITARY_TOKENS = ("sanitary", "m03", "m04")


def _walk_inserts(entities, inherited_layer="", depth=0):
    if depth > 6:
        return
    for entity in entities:
        if entity.dxftype() != "INSERT":
            continue
        layer = str(entity.dxf.get("layer", "")) or inherited_layer
        yield str(entity.dxf.get("name", "")), layer
        try:
            block = entity.block()
        except Exception:
            continue
        yield from _walk_inserts(block, layer, depth + 1)


def _is_sanitary_layer(layer: str) -> bool:
    lowered = layer.lower()
    return any(token in lowered for token in SANITARY_TOKENS)


def _entity_extent(building):
    points = []
    for entity in building.entities:
        points.extend(entity.points)
        if entity.center is not None:
            points.append(entity.center)
            if entity.radius:
                points.extend(
                    [
                        Point(
                            x=entity.center.x - entity.radius,
                            y=entity.center.y - entity.radius,
                        ),
                        Point(
                            x=entity.center.x + entity.radius,
                            y=entity.center.y + entity.radius,
                        ),
                    ]
                )
        if entity.position is not None:
            points.append(entity.position)
    return bbox(points) if points else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a DXF before or after Flowline import.")
    parser.add_argument("path", help="DXF file to inspect")
    args = parser.parse_args()

    source = Path(args.path)
    if not source.exists():
        print(f"File not found: {source}")
        return 2

    doc = ezdxf.readfile(source)
    msp = doc.modelspace()
    expanded = list(_iter_entities(msp))
    mirrored = sum(
        1
        for entity, _ in expanded
        if entity.dxf.get("extrusion", (0, 0, 1))[2] < 0
    )

    print("FLOWLINE DXF INSPECTION")
    print(f"file: {source} ({source.stat().st_size:,} bytes)")
    print(f"dxf_version: {doc.dxfversion}")
    print(f"insunits: {doc.header.get('$INSUNITS')}")
    print(f"modelspace_entities: {len(msp)}")
    print(f"expanded_entities: {len(expanded)}")
    print(f"mirrored_ocs_geometry: {mirrored}")

    top_types = Counter(entity.dxftype() for entity in msp)
    expanded_types = Counter(entity.dxftype() for entity, _ in expanded)
    print(f"top_level_types: {dict(top_types)}")
    print(f"expanded_types: {dict(expanded_types)}")

    layer_counts = Counter(
        str(entity.dxf.get("layer", "0")) for entity, _ in expanded
    )
    print("layers:")
    for layer, count in layer_counts.most_common():
        print(f"  {count:5}  {layer}")

    building = import_dxf(source)
    extent = _entity_extent(building)
    print("imported:")
    print(f"  units: {building.units} (scale {building.source_scale:g})")
    print(f"  rooms: {len(building.rooms)}")
    print(f"  doors: {len(building.doors)}")
    print(f"  shafts: {len(building.shafts)}")
    print(f"  entities: {len(building.entities)}")
    if extent is not None:
        print(
            "  extent_mm: "
            f"x {extent.minx:.0f}..{extent.maxx:.0f} "
            f"y {extent.miny:.0f}..{extent.maxy:.0f} "
            f"({extent.width:.0f} x {extent.height:.0f})"
        )
    view_box = re.search(r'viewBox="([^"]+)"', render_svg(building))
    if view_box is not None:
        values = view_box.group(1).split()
        print(f"  svg_viewbox: {view_box.group(1)}")
        if len(values) == 4:
            print(f"  svg_width_mm: {float(values[2]):.0f}")
    for warning in building.warnings:
        print(f"  warning: {warning}")

    print("rooms:")
    for room in building.rooms:
        hints = ",".join(hint.value for hint in room.fixture_hints) or "-"
        print(
            f"  {room.id}  {room.area_m2:6.2f} m2  "
            f"{room.plumbing_role.value:9}  hints={hints}  "
            f"sanitaryware={room.has_sanitaryware}"
        )

    print("shafts:")
    for shaft in building.shafts:
        services = ",".join(service.value for service in shaft.services)
        print(
            f"  {shaft.id}  {shaft.width_mm:.0f}x{shaft.depth_mm:.0f} mm  "
            f"services={services}  source={shaft.source}  "
            f"confidence={shaft.confidence:.2f}  name={shaft.name or '-'}"
        )

    print("detected_fixtures:")
    for fixture in building.detected_fixtures:
        print(
            f"  {fixture.id:16} {fixture.type.value:12} "
            f"room={fixture.room_id or '-':6} "
            f"at=({fixture.position.x:.0f},{fixture.position.y:.0f}) "
            f"{fixture.width_mm:.0f}x{fixture.depth_mm:.0f} mm "
            f"source={fixture.source} confidence={fixture.confidence:.2f}"
        )

    print("sanitaryware_layers:")
    for layer, count in layer_counts.items():
        if _is_sanitary_layer(layer):
            print(f"  {count:5}  {layer}")

    print("fixture_like_inserts:")
    fixture_inserts = Counter(
        (name, layer)
        for name, layer in _walk_inserts(msp)
        if _is_sanitary_layer(layer)
    )
    if not fixture_inserts:
        print("  none")
    for (name, layer), count in fixture_inserts.most_common():
        print(f"  {count:5}  {name}  [{layer}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
