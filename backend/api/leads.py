"""Rotas de leads + endpoints de importação."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.lead import Lead
from database.session import get_db
from schemas.common import MessageResponse
from schemas.importer import (
    ImportConfirmRequest,
    ImportConfirmResponse,
    ImportFromFollowersRequest,
    ImportPreviewResponse,
)
from schemas.lead import LeadCreate, LeadRead, LeadUpdate
from services import leads as lead_service
from services.campaigns.service import get_campaign
from services.importer.service import confirm_import, preview_from_confirm_leads, preview_import
from services.logging.service import write_log
from services.sourcing.service import pull_and_confirm_followers

router = APIRouter()


@router.get("", response_model=list[LeadRead])
def list_leads(
    campaign_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[LeadRead]:
    return lead_service.list_leads(  # type: ignore[return-value]
        db,
        campaign_id=campaign_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=LeadRead, status_code=201)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> LeadRead:
    return lead_service.create_lead(db, payload)  # type: ignore[return-value]


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> LeadRead:
    return lead_service.get_lead(db, lead_id)  # type: ignore[return-value]


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
) -> LeadRead:
    return lead_service.update_lead(db, lead_id, payload)  # type: ignore[return-value]


@router.delete("/{lead_id}", response_model=MessageResponse)
def delete_lead(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> MessageResponse:
    lead_service.delete_lead(db, lead_id)
    return MessageResponse(detail="Lead removido")


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    campaign_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    get_campaign(db, campaign_id)
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo sem nome")
    content = await file.read()
    existing = {
        row[0]
        for row in db.execute(
            select(Lead.instagram).where(Lead.campaign_id == campaign_id)
        ).all()
    }
    try:
        result = preview_import(
            content,
            filename=file.filename,
            campaign_id=campaign_id,
            existing_handles=existing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return result


@router.post("/import/confirm", response_model=ImportConfirmResponse)
def import_confirm(
    payload: ImportConfirmRequest,
    db: Session = Depends(get_db),
) -> ImportConfirmResponse:
    get_campaign(db, payload.campaign_id)
    try:
        preview = preview_from_confirm_leads(payload.campaign_id, payload.leads)
        result = confirm_import(db, campaign_id=payload.campaign_id, preview=preview)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    write_log(
        db,
        action="import",
        result="success",
        campaign_id=payload.campaign_id,
        details=f"inserted={result.inserted} skipped={result.skipped_duplicates}",
    )
    return result


@router.post("/import/from-followers", response_model=ImportConfirmResponse)
def import_from_followers(
    payload: ImportFromFollowersRequest,
    db: Session = Depends(get_db),
) -> ImportConfirmResponse:
    """Puxa seguidores da conta Instagram informada e já persiste como leads da campanha."""
    get_campaign(db, payload.campaign_id)
    try:
        result = pull_and_confirm_followers(
            db,
            campaign_id=payload.campaign_id,
            account_id=payload.account_id,
            amount=payload.amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    write_log(
        db,
        action="import_followers",
        result="success",
        campaign_id=payload.campaign_id,
        account_id=payload.account_id,
        details=f"inserted={result.inserted} skipped={result.skipped_duplicates}",
    )
    return result
