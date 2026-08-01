"""Schemas de log."""

from __future__ import annotations

import uuid
from datetime import datetime

from schemas.common import ORMModel


class LogRead(ORMModel):
    id: uuid.UUID
    timestamp: datetime
    campaign_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    account_id: uuid.UUID | None
    action: str
    channel: str
    instagram_handle: str | None
    result: str
    error: str | None
    message_hash: str | None
    details: str | None
