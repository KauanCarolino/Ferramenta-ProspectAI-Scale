"""Rotas de campanhas."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate
from schemas.scheduled_job import ScheduledJobRead
from services import campaigns as campaign_service
from services.logging.service import write_log
from services.scheduler.service import list_campaign_jobs

router = APIRouter()


@router.get("", response_model=list[CampaignRead])
def list_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CampaignRead]:
    return campaign_service.list_campaigns(db, skip=skip, limit=limit)  # type: ignore[return-value]


@router.post("", response_model=CampaignRead, status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)) -> CampaignRead:
    return campaign_service.create_campaign(db, payload)  # type: ignore[return-value]


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)) -> CampaignRead:
    return campaign_service.get_campaign(db, campaign_id)  # type: ignore[return-value]


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
) -> CampaignRead:
    return campaign_service.update_campaign(db, campaign_id, payload)  # type: ignore[return-value]


@router.get("/{campaign_id}/jobs", response_model=list[ScheduledJobRead])
def get_campaign_jobs(
    campaign_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=500),
    status: str | None = Query("pending"),
    db: Session = Depends(get_db),
) -> list[ScheduledJobRead]:
    """Próximos N jobs da campanha (default: pending)."""
    campaign_service.get_campaign(db, campaign_id)
    return list_campaign_jobs(db, campaign_id, limit=limit, status=status)  # type: ignore[return-value]


@router.post("/{campaign_id}/start", response_model=CampaignRead)
def start_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = campaign_service.start_campaign(db, campaign_id)
    write_log(db, action="start", result="success", campaign_id=campaign_id)
    return campaign  # type: ignore[return-value]


@router.post("/{campaign_id}/pause", response_model=CampaignRead)
def pause_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = campaign_service.pause_campaign(db, campaign_id)
    write_log(db, action="pause", result="success", campaign_id=campaign_id)
    return campaign  # type: ignore[return-value]


@router.post("/{campaign_id}/cancel", response_model=CampaignRead)
def cancel_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = campaign_service.cancel_campaign(db, campaign_id)
    write_log(db, action="cancel", result="success", campaign_id=campaign_id)
    return campaign  # type: ignore[return-value]


@router.post("/{campaign_id}/resume", response_model=CampaignRead)
def resume_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = campaign_service.resume_campaign(db, campaign_id)
    write_log(db, action="resume", result="success", campaign_id=campaign_id)
    return campaign  # type: ignore[return-value]
