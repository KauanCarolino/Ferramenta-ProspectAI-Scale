"""Métricas diárias agregadas."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class MetricsDaily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "metrics_daily"
    __table_args__ = (
        UniqueConstraint("campaign_id", "day", name="uq_metrics_daily_campaign_day"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
