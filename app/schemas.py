from __future__ import annotations

from pydantic import BaseModel, Field

from core.geometry import Point
from core.models import FixtureType


class DesignRequest(BaseModel):
    room_id: str
    fixtures: list[FixtureType] = Field(
        default_factory=lambda: [FixtureType.WC, FixtureType.BASIN, FixtureType.SHOWER]
    )
    stack: Point | None = None
    shaft_id: str | None = None
    profile_id: str = "india_nbc_2016"
    provider: str | None = None
    request: str | None = None


class FixRequest(BaseModel):
    fix_id: str


class ApproveRequest(BaseModel):
    approver_name: str = "Engineer"
