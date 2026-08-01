"""Rotas de listagem e export de logs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.log import LogRead
from services.logging.service import EXPORT_DEFAULT_LIMIT, EXPORT_MAX_LIMIT, export_logs_csv, list_logs

router = APIRouter()


@router.get("/export")
def export_logs(
    campaign_id: uuid.UUID | None = None,
    today: bool = Query(False),
    result: str | None = None,
    limit: int = Query(EXPORT_DEFAULT_LIMIT, ge=1, le=EXPORT_MAX_LIMIT),
    db: Session = Depends(get_db),
) -> Response:
    csv_body = export_logs_csv(
        db,
        campaign_id=campaign_id,
        today_only=today,
        result=result,
        limit=limit,
    )
    filename = f"prospectai-logs-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=list[LogRead])
def get_logs(
    campaign_id: uuid.UUID | None = None,
    today: bool = Query(False),
    result: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[LogRead]:
    return list_logs(  # type: ignore[return-value]
        db,
        campaign_id=campaign_id,
        today_only=today,
        result=result,
        skip=skip,
        limit=limit,
    )
