"""Rotas de templates."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.common import MessageResponse
from schemas.template import (
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateRead,
    TemplateUpdate,
)
from services import templates as template_service

router = APIRouter()


@router.get("", response_model=list[TemplateRead])
def list_templates(
    campaign_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TemplateRead]:
    return template_service.list_templates(  # type: ignore[return-value]
        db, campaign_id=campaign_id, skip=skip, limit=limit
    )


@router.post("/preview", response_model=TemplatePreviewResponse)
def preview_template(payload: TemplatePreviewRequest) -> TemplatePreviewResponse:
    return template_service.preview_template(payload)


@router.post("", response_model=TemplateRead, status_code=201)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)) -> TemplateRead:
    return template_service.create_template(db, payload)  # type: ignore[return-value]


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(template_id: uuid.UUID, db: Session = Depends(get_db)) -> TemplateRead:
    return template_service.get_template(db, template_id)  # type: ignore[return-value]


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
) -> TemplateRead:
    return template_service.update_template(db, template_id, payload)  # type: ignore[return-value]


@router.delete("/{template_id}", response_model=MessageResponse)
def delete_template(template_id: uuid.UUID, db: Session = Depends(get_db)) -> MessageResponse:
    template_service.delete_template(db, template_id)
    return MessageResponse(detail="Template removido")
