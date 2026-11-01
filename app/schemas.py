from __future__ import annotations

from pydantic import BaseModel, Field

from core.geometry import Point
from core.models import FixtureType


class RoomSelection(BaseModel):
    room_id: str
    fixtures: list[FixtureType] | None = None
    stack_id: str | None = None


class DesignRequest(BaseModel):
    room_id: str | None = None
    fixtures: list[FixtureType] = Field(
        default_factory=lambda: [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER]
    )
    rooms: list[RoomSelection] = Field(default_factory=list)
    stack: Point | None = None
    shaft_id: str | None = None
    profile_id: str = "india_nbc_2016"
    provider: str | None = None
    request: str | None = None


class FixRequest(BaseModel):
    fix_id: str


class MessageRequest(BaseModel):
    content: str


class ProfileRequest(BaseModel):
    profile_id: str


class ApproveRequest(BaseModel):
    approver_name: str = "Engineer"


class SheetRequest(BaseModel):
    preset: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    orientation: str | None = None
    scale: float | None = None
    include_riser: bool | None = None
    include_schedules: bool | None = None
    notes: list[str] | None = None
