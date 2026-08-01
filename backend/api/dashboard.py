"""Rota de resumo do dashboard."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.dashboard import DashboardSummary
from services.dashboard import get_dashboard_summary

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    campaign_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    return get_dashboard_summary(db, campaign_id=campaign_id)
