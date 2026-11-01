from __future__ import annotations

from enum import StrEnum


class LayerRole(StrEnum):
    WALL = "wall"
    DOOR = "door"
    WINDOW = "window"
    ROOM = "room"
    ROOM_LABEL = "room_label"
    SHAFT = "shaft"
    ANNOTATION = "annotation"
    OTHER = "other"


ROOM_LAYER_TOKENS = ("room", "space", "area")
DOOR_LAYER_TOKENS = ("door",)
WINDOW_LAYER_TOKENS = ("window", "glaz", "glass")
SHAFT_LAYER_TOKENS = ("shaft", "duct", "riser", "stack")
ANNOTATION_LAYER_TOKENS = (
    "dimension",
    "dim",
    "note",
    "title",
    "border",
    "boundary",
    "defpoints",
    "viewport",
    "annotation",
    "tag",
)

ROOM_NAME_TOKENS = (
    "bath",
    "toilet",
    "wc",
    "shower",
    "wash",
    "kitchen",
    "bedroom",
    "living",
    "dining",
    "master",
    "passage",
    "hall",
    "corridor",
    "foyer",
    "lobby",
    "study",
    "utility",
    "balcony",
    "store",
    "closet",
    "pantry",
    "ensuite",
    "powder",
    "lavatory",
    "family",
    "office",
    "garage",
)

REJECTED_LABEL_TOKENS = (
    "approx",
    "overall",
    "units:",
    "layers:",
    "gross",
    "concept",
    "verify",
    "furniture",
    "electrical",
    "licensed",
    "construction",
    "architectural plan",
    "title block",
    "north",
    "sq m",
    "sq ft",
    " mm",
)


def classify_layer(layer: str) -> LayerRole:
    lowered = layer.lower()
    if any(token in lowered for token in SHAFT_LAYER_TOKENS):
        return LayerRole.SHAFT
    if "wall" in lowered:
        return LayerRole.WALL
    if any(token in lowered for token in WINDOW_LAYER_TOKENS):
        return LayerRole.WINDOW
    if any(token in lowered for token in DOOR_LAYER_TOKENS):
        return LayerRole.DOOR
    if any(token in lowered for token in ROOM_LAYER_TOKENS):
        return LayerRole.ROOM
    if any(token in lowered for token in ANNOTATION_LAYER_TOKENS):
        return LayerRole.ANNOTATION
    return LayerRole.OTHER


def is_room_label_text(text: str, layer: str = "") -> bool:
    cleaned = " ".join(text.split())
    if len(cleaned) < 2:
        return False
    lowered = cleaned.lower()
    if any(token in lowered for token in REJECTED_LABEL_TOKENS):
        return False
    if any(token in layer.lower() for token in ROOM_LAYER_TOKENS):
        return True
    return any(token in lowered for token in ROOM_NAME_TOKENS)
