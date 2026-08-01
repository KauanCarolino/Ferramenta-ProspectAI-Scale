"""Schemas de template."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.common import ORMModel

TemplateStage = Literal["d1", "d4", "d8"]


class TemplateCreate(BaseModel):
    campaign_id: uuid.UUID
    stage: TemplateStage
    body: str = Field(..., min_length=1)
    name: str | None = Field(default=None, max_length=255)


class TemplateUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, max_length=255)
    stage: TemplateStage | None = None


class TemplateRead(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    stage: str
    body: str
    name: str | None
    created_at: datetime
    updated_at: datetime


class TemplatePreviewRequest(BaseModel):
    body: str = Field(..., min_length=1)
    variables: dict[str, str | None] = Field(default_factory=dict)
    seed: str | None = Field(default=None, description="Seed opcional para Spintax determinístico")


class TemplatePreviewResponse(BaseModel):
    rendered: str
    variables_used: list[str]
    spintax_groups: int
