"""Schemas de scheduled job."""

from __future__ import annotations

import uuid
from datetime import datetime

from schemas.common import ORMModel


class ScheduledJobRead(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    lead_id: uuid.UUID
    account_id: uuid.UUID | None
    stage: str
    scheduled_at: datetime
    status: str
    channel: str
    created_at: datetime
    updated_at: datetime
