"""Schemas de campanha."""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from schemas.common import ORMModel

CampaignStatus = Literal[
    "draft",
    "active",
    "paused",
    "completed",
    "cancelled",
    "auto_paused",
]


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    channel: str = Field(default="instagram", max_length=32)
    messages_per_day: int = Field(default=150, ge=1, le=500)
    duration_days: int = Field(default=10, ge=1, le=90)
    window_start: time = Field(default=time(9, 0))
    window_end: time = Field(default=time(18, 0))
    min_interval_sec: int = Field(default=120, ge=30)
    max_interval_sec: int = Field(default=300, ge=60)
    description: str | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.min_interval_sec > self.max_interval_sec:
            raise ValueError("min_interval_sec deve ser <= max_interval_sec")
        if self.window_start >= self.window_end:
            raise ValueError("window_start deve ser anterior a window_end")
        return self


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    messages_per_day: int | None = Field(default=None, ge=1, le=500)
    duration_days: int | None = Field(default=None, ge=1, le=90)
    window_start: time | None = None
    window_end: time | None = None
    min_interval_sec: int | None = Field(default=None, ge=30)
    max_interval_sec: int | None = Field(default=None, ge=60)
    description: str | None = None
    status: CampaignStatus | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if (
            self.min_interval_sec is not None
            and self.max_interval_sec is not None
            and self.min_interval_sec > self.max_interval_sec
        ):
            raise ValueError("min_interval_sec deve ser <= max_interval_sec")
        if (
            self.window_start is not None
            and self.window_end is not None
            and self.window_start >= self.window_end
        ):
            raise ValueError("window_start deve ser anterior a window_end")
        return self


class CampaignRead(ORMModel):
    id: uuid.UUID
    name: str
    status: str
    channel: str
    messages_per_day: int
    duration_days: int
    window_start: time
    window_end: time
    min_interval_sec: int
    max_interval_sec: int
    description: str | None
    created_at: datetime
    updated_at: datetime
