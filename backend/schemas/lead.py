"""Schemas de lead."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.common import ORMModel


class LeadCreate(BaseModel):
    campaign_id: uuid.UUID
    nome: str = Field(..., min_length=1, max_length=255)
    empresa: str = Field(..., min_length=1, max_length=255)
    cargo: str = Field(..., min_length=1, max_length=255)
    instagram: str = Field(..., min_length=1, max_length=150)
    cidade: str | None = Field(default=None, max_length=150)
    observacoes: str | None = None


class LeadUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=255)
    empresa: str | None = Field(default=None, min_length=1, max_length=255)
    cargo: str | None = Field(default=None, min_length=1, max_length=255)
    instagram: str | None = Field(default=None, min_length=1, max_length=150)
    cidade: str | None = Field(default=None, max_length=150)
    observacoes: str | None = None
    status: str | None = None


class LeadRead(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    nome: str
    empresa: str
    cargo: str
    instagram: str
    cidade: str | None
    observacoes: str | None
    status: str
    created_at: datetime
    updated_at: datetime
