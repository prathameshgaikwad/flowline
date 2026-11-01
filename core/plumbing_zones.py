from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum


class PlumbingRole(StrEnum):
    BATHROOM = "bathroom"
    POWDER = "powder"
    KITCHEN = "kitchen"
    BALCONY = "balcony"
    UTILITY = "utility"
    WASH_AREA = "wash_area"
    NONE = "none"


_LABEL_TOKENS: tuple[tuple[PlumbingRole, tuple[str, ...]], ...] = (
    (
        PlumbingRole.BATHROOM,
        (
            "bathroom",
            "bath room",
            "master bath",
            "common bath",
            "washroom",
            "wash room",
            "shower room",
            "ensuite",
            "en suite",
            "restroom",
            "rest room",
        ),
    ),
    (
        PlumbingRole.POWDER,
        (
            "powder",
            "toilet",
            "wc",
            "half bath",
        ),
    ),
    (
        PlumbingRole.KITCHEN,
        (
            "kitchen",
            "kitchenette",
            "pantry",
        ),
    ),
    (
        PlumbingRole.BALCONY,
        (
            "balcony",
            "terrace",
            "deck",
            "veranda",
            "verandah",
        ),
    ),
    (
        PlumbingRole.UTILITY,
        (
            "utility",
            "laundry",
            "washing",
            "maid",
        ),
    ),
    (
        PlumbingRole.WASH_AREA,
        (
            "wash basin",
            "washbasin",
            "wash area",
            "vanity",
            "basin",
        ),
    ),
)


def classify_room(name: str | None, hints: Iterable[object]) -> PlumbingRole:
    label_role = _role_from_label(name)
    if label_role != PlumbingRole.NONE:
        return label_role

    hint_values = {_hint_value(hint) for hint in hints}
    if "KITCHEN_SINK" in hint_values:
        return PlumbingRole.KITCHEN
    if "SHOWER" in hint_values or "WC" in hint_values:
        return PlumbingRole.BATHROOM
    if "BASIN" in hint_values:
        return PlumbingRole.WASH_AREA
    if "FLOOR_DRAIN" in hint_values:
        return PlumbingRole.BALCONY
    return PlumbingRole.NONE


def default_fixtures(role: PlumbingRole) -> list[object]:
    from core.models import FixtureType

    return {
        PlumbingRole.BATHROOM: [
            FixtureType.WC,
            FixtureType.BASIN,
            FixtureType.SHOWER,
        ],
        PlumbingRole.POWDER: [FixtureType.WC, FixtureType.BASIN],
        PlumbingRole.KITCHEN: [FixtureType.KITCHEN_SINK],
        PlumbingRole.BALCONY: [FixtureType.FLOOR_DRAIN],
        PlumbingRole.UTILITY: [FixtureType.FLOOR_DRAIN, FixtureType.BASIN],
        PlumbingRole.WASH_AREA: [FixtureType.BASIN],
        PlumbingRole.NONE: [],
    }[role]


def fixture_hint_from_name(name: str | None, layer: str = "") -> object | None:
    from core.models import FixtureType

    value = _normalise(f"{name or ''} {layer}")
    if "kitchen sink" in value or "kitchen_sink" in value or "ksink" in value:
        return FixtureType.KITCHEN_SINK
    if "floor drain" in value or "floor_drain" in value or "floordrain" in value:
        return FixtureType.FLOOR_DRAIN
    if "water closet" in value or "wc" in value or "toilet" in value or "urinal" in value:
        return FixtureType.WC
    if (
        "wash basin" in value
        or "washbasin" in value
        or "lavatory" in value
        or "basin" in value
        or re.search(r"\blav\b", value)
    ):
        return FixtureType.BASIN
    if "shower" in value or "bathtub" in value or re.search(r"\btub\b", value):
        return FixtureType.SHOWER
    if "sink" in value:
        return FixtureType.KITCHEN_SINK
    return None


def _role_from_label(name: str | None) -> PlumbingRole:
    if not name:
        return PlumbingRole.NONE
    lowered = _normalise(name)
    for role, tokens in _LABEL_TOKENS:
        if any(token in lowered for token in tokens):
            return role
    return PlumbingRole.NONE


def _hint_value(hint: object) -> str:
    value = getattr(hint, "value", hint)
    return str(value).upper()


def _normalise(value: str) -> str:
    return re.sub(r"[_-]+", " ", value).lower()
