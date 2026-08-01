"""CRUD e listagem de leads."""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.lead import Lead
from schemas.lead import LeadCreate, LeadUpdate
from services.campaigns.service import get_campaign
from utils.instagram import normalize_instagram_handle

logger = logging.getLogger(__name__)


def list_leads(
    db: Session,
    *,
    campaign_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Lead]:
    stmt = select(Lead).order_by(Lead.created_at.desc())
    if campaign_id is not None:
        stmt = stmt.where(Lead.campaign_id == campaign_id)
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_lead(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado")
    return lead


def create_lead(db: Session, data: LeadCreate) -> Lead:
    get_campaign(db, data.campaign_id)
    handle = normalize_instagram_handle(data.instagram)
    if not handle:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Handle Instagram inválido",
        )
    existing = db.scalar(
        select(Lead).where(Lead.campaign_id == data.campaign_id, Lead.instagram == handle)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lead com Instagram '{handle}' já existe nesta campanha",
        )
    payload = data.model_dump()
    payload["instagram"] = handle
    lead = Lead(**payload, status="novo")
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(db: Session, lead_id: uuid.UUID, data: LeadUpdate) -> Lead:
    lead = get_lead(db, lead_id)
    payload = data.model_dump(exclude_unset=True)
    if "instagram" in payload:
        handle = normalize_instagram_handle(payload["instagram"])
        if not handle:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Handle Instagram inválido",
            )
        conflict = db.scalar(
            select(Lead).where(
                Lead.campaign_id == lead.campaign_id,
                Lead.instagram == handle,
                Lead.id != lead.id,
            )
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lead com Instagram '{handle}' já existe nesta campanha",
            )
        payload["instagram"] = handle
    for key, value in payload.items():
        setattr(lead, key, value)
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead_id: uuid.UUID) -> None:
    lead = get_lead(db, lead_id)
    db.delete(lead)
    db.commit()
