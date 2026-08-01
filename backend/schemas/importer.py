"""Schemas de preview / confirmação do importer."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ImportRejectedRow(BaseModel):
    row_number: int
    raw: dict[str, str | None] = Field(default_factory=dict)
    reasons: list[str]


class ImportPreviewRow(BaseModel):
    row_number: int
    nome: str
    empresa: str
    cargo: str
    instagram: str
    cidade: str | None = None
    observacoes: str | None = None


class ImportPreviewResponse(BaseModel):
    campaign_id: uuid.UUID | None = None
    total_rows: int
    valid_count: int
    rejected_count: int
    duplicate_count: int
    preview: list[ImportPreviewRow]
    rejected: list[ImportRejectedRow]


class ImportConfirmLead(BaseModel):
    """Linha de lead para confirmação — sem campaign_id por lead; use request.campaign_id."""

    nome: str = Field(..., min_length=1, max_length=255)
    empresa: str = Field(..., min_length=1, max_length=255)
    cargo: str = Field(..., min_length=1, max_length=255)
    instagram: str = Field(..., min_length=1, max_length=150)
    cidade: str | None = Field(default=None, max_length=150)
    observacoes: str | None = None


class ImportConfirmRequest(BaseModel):
    campaign_id: uuid.UUID
    leads: list[ImportConfirmLead] = Field(default_factory=list)


class ImportConfirmResponse(BaseModel):
    campaign_id: uuid.UUID
    inserted: int
    skipped_duplicates: int
