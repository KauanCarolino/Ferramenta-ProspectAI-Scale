"""Model de lead."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class Lead(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("campaign_id", "instagram", name="uq_leads_campaign_instagram"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    empresa: Mapped[str] = mapped_column(String(255), nullable=False)
    cargo: Mapped[str] = mapped_column(String(255), nullable=False)
    instagram: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    cidade: Mapped[str | None] = mapped_column(String(150), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # novo|agendado|enviado_d1|aguardando_d4|enviado_d4|aguardando_d8|enviado_d8|
    # concluido|respondido|falhou|pausado
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="novo", index=True)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="leads")  # noqa: F821
