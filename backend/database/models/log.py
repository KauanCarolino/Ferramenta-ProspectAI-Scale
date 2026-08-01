"""Entradas de log de auditoria."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import GUID, Base, UUIDPrimaryKeyMixin, utcnow


class Log(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "logs"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # send|retry|followup|pause|resume|reply_detected|import|login|...
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="instagram")
    instagram_handle: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # success|failed|blocked|challenge|info
    result: Mapped[str] = mapped_column(String(32), nullable=False, default="info", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
