"""Serviço de logging de auditoria."""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.log import Log

logger = logging.getLogger(__name__)

CSV_HEADERS = (
    "timestamp",
    "action",
    "result",
    "channel",
    "campaign_id",
    "lead_id",
    "account_id",
    "instagram_handle",
    "error",
    "details",
    "message_hash",
)

EXPORT_DEFAULT_LIMIT = 10_000
EXPORT_MAX_LIMIT = 50_000


def write_log(
    db: Session,
    *,
    action: str,
    result: str = "info",
    channel: str = "instagram",
    campaign_id: uuid.UUID | None = None,
    lead_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    instagram_handle: str | None = None,
    error: str | None = None,
    message_hash: str | None = None,
    details: str | None = None,
    commit: bool = True,
) -> Log:
    entry = Log(
        timestamp=datetime.now(timezone.utc),
        action=action,
        result=result,
        channel=channel,
        campaign_id=campaign_id,
        lead_id=lead_id,
        account_id=account_id,
        instagram_handle=instagram_handle,
        error=error,
        message_hash=message_hash,
        details=details,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry


def list_logs(
    db: Session,
    *,
    campaign_id: uuid.UUID | None = None,
    today_only: bool = False,
    result: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Log]:
    stmt = select(Log).order_by(Log.timestamp.desc())
    if campaign_id is not None:
        stmt = stmt.where(Log.campaign_id == campaign_id)
    if result:
        stmt = stmt.where(Log.result == result)
    if today_only:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = stmt.where(Log.timestamp >= start)
    return list(db.scalars(stmt.offset(skip).limit(limit)).all())


def export_logs_csv(
    db: Session,
    *,
    campaign_id: uuid.UUID | None = None,
    today_only: bool = False,
    result: str | None = None,
    limit: int = EXPORT_DEFAULT_LIMIT,
) -> str:
    """Exporta logs filtrados como CSV UTF-8 (header + linhas)."""
    capped = max(1, min(limit, EXPORT_MAX_LIMIT))
    rows = list_logs(
        db,
        campaign_id=campaign_id,
        today_only=today_only,
        result=result,
        skip=0,
        limit=capped,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADERS)
    for row in rows:
        ts = row.timestamp
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        writer.writerow(
            [
                ts.isoformat() if ts is not None else "",
                row.action,
                row.result,
                row.channel,
                str(row.campaign_id) if row.campaign_id else "",
                str(row.lead_id) if row.lead_id else "",
                str(row.account_id) if row.account_id else "",
                row.instagram_handle or "",
                row.error or "",
                row.details or "",
                row.message_hash or "",
            ]
        )
    return buf.getvalue()
