"""Model de campanha."""

from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        index=True,
    )  # draft|active|paused|completed|cancelled|auto_paused
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="instagram")
    messages_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=150)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    window_start: Mapped[time] = mapped_column(Time, nullable=False, default=time(9, 0))
    window_end: Mapped[time] = mapped_column(Time, nullable=False, default=time(18, 0))
    min_interval_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    max_interval_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="campaign")  # noqa: F821
    templates: Mapped[list["Template"]] = relationship(  # noqa: F821
        "Template",
        back_populates="campaign",
    )
