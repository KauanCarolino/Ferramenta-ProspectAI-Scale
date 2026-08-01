"""Model de conta Instagram."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Account(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "accounts"

    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    # active|warming|paused|challenge|banned|offline
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="offline", index=True)
    proxy: Mapped[str | None] = mapped_column(String(512), nullable=True)
    warmup_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Path do arquivo de sessão ou blob criptografado (stub) — nunca commitar sessões reais.
    session_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    session_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
