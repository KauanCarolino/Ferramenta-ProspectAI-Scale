"""Lógica de negócio de campanhas."""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.campaign import Campaign
from schemas.campaign import CampaignCreate, CampaignUpdate

logger = logging.getLogger(__name__)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active", "cancelled"},
    "active": {"paused", "completed", "cancelled", "auto_paused"},
    "paused": {"active", "cancelled"},
    "auto_paused": {"active", "cancelled", "paused"},
    "completed": set(),
    "cancelled": set(),
}


def list_campaigns(db: Session, *, skip: int = 0, limit: int = 50) -> list[Campaign]:
    stmt = select(Campaign).order_by(Campaign.created_at.desc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_campaign(db: Session, campaign_id: uuid.UUID) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campanha não encontrada")
    return campaign


def create_campaign(db: Session, data: CampaignCreate) -> Campaign:
    campaign = Campaign(**data.model_dump(), status="draft")
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    logger.info("Campanha criada id=%s name=%s", campaign.id, campaign.name)
    return campaign


def update_campaign(db: Session, campaign_id: uuid.UUID, data: CampaignUpdate) -> Campaign:
    campaign = get_campaign(db, campaign_id)
    payload = data.model_dump(exclude_unset=True)
    if "status" in payload:
        _assert_transition(campaign.status, payload["status"])
    for key, value in payload.items():
        setattr(campaign, key, value)
    db.commit()
    db.refresh(campaign)
    return campaign


def _assert_transition(current: str, new: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if new == current:
        return
    if new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transição de status inválida: {current} → {new}",
        )


def start_campaign(db: Session, campaign_id: uuid.UUID) -> Campaign:
    from services.scheduler.service import schedule_campaign

    campaign = get_campaign(db, campaign_id)
    _assert_transition(campaign.status, "active")
    campaign.status = "active"
    db.commit()
    db.refresh(campaign)
    schedule_result = schedule_campaign(db, campaign_id)
    logger.info(
        "Campanha iniciada id=%s jobs_created=%s",
        campaign.id,
        schedule_result.get("jobs_created"),
    )
    return campaign


def pause_campaign(db: Session, campaign_id: uuid.UUID) -> Campaign:
    from services.scheduler.service import cancel_pending_jobs

    campaign = get_campaign(db, campaign_id)
    _assert_transition(campaign.status, "paused")
    campaign.status = "paused"
    db.commit()
    db.refresh(campaign)
    cancelled = cancel_pending_jobs(db, campaign_id)
    logger.info("Campanha pausada id=%s cancelled_jobs=%s", campaign.id, cancelled)
    return campaign


def cancel_campaign(db: Session, campaign_id: uuid.UUID) -> Campaign:
    from services.scheduler.service import cancel_pending_jobs

    campaign = get_campaign(db, campaign_id)
    _assert_transition(campaign.status, "cancelled")
    campaign.status = "cancelled"
    db.commit()
    db.refresh(campaign)
    cancelled = cancel_pending_jobs(db, campaign_id)
    logger.info("Campanha cancelada id=%s cancelled_jobs=%s", campaign.id, cancelled)
    return campaign


def resume_campaign(db: Session, campaign_id: uuid.UUID) -> Campaign:
    from services.scheduler.service import resume_pending_jobs

    campaign = get_campaign(db, campaign_id)
    _assert_transition(campaign.status, "active")
    campaign.status = "active"
    db.commit()
    db.refresh(campaign)
    resume_result = resume_pending_jobs(db, campaign_id)
    logger.info("Campanha retomada id=%s resume=%s", campaign.id, resume_result)
    return campaign
