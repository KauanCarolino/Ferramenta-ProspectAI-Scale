"""Agregação do resumo do dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models.campaign import Campaign
from database.models.lead import Lead
from database.models.message import Message
from schemas.dashboard import DashboardSummary

_SENT_STATUSES = frozenset(
    {
        "enviado_d1",
        "aguardando_d4",
        "enviado_d4",
        "aguardando_d8",
        "enviado_d8",
        "concluido",
        "respondido",
    }
)


def get_dashboard_summary(
    db: Session,
    *,
    campaign_id: uuid.UUID | None = None,
) -> DashboardSummary:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    active_campaigns = (
        db.scalar(select(func.count()).select_from(Campaign).where(Campaign.status == "active"))
        or 0
    )

    status_campanha: str | None = None
    if campaign_id is not None:
        campaign = db.get(Campaign, campaign_id)
        status_campanha = campaign.status if campaign else None
    else:
        # Global summary: surface auto_paused so the dashboard banner can fire
        # without requiring a campaign_id filter.
        has_auto_paused = db.scalar(
            select(func.count())
            .select_from(Campaign)
            .where(Campaign.status == "auto_paused")
        )
        if has_auto_paused:
            status_campanha = "auto_paused"

    lead_count_stmt = select(func.count()).select_from(Lead)
    sent_stmt = select(func.count()).select_from(Lead).where(Lead.status.in_(_SENT_STATUSES))
    reply_stmt = (
        select(func.count())
        .select_from(Lead)
        .where(Lead.status.in_(("respondido", "concluido")), Lead.updated_at >= today_start)
    )
    msg_stmt = (
        select(func.count())
        .select_from(Message)
        .where(Message.result == "success", Message.sent_at >= today_start)
    )
    fail_stmt = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.result.in_(("failed", "blocked", "challenge")),
            Message.sent_at >= today_start,
        )
    )

    if campaign_id is not None:
        lead_count_stmt = lead_count_stmt.where(Lead.campaign_id == campaign_id)
        sent_stmt = sent_stmt.where(Lead.campaign_id == campaign_id)
        reply_stmt = reply_stmt.where(Lead.campaign_id == campaign_id)
        msg_stmt = msg_stmt.where(Message.campaign_id == campaign_id)
        fail_stmt = fail_stmt.where(Message.campaign_id == campaign_id)

    leads_totais = db.scalar(lead_count_stmt) or 0
    leads_enviados = db.scalar(sent_stmt) or 0
    leads_restantes = max(leads_totais - leads_enviados, 0)
    progresso = (leads_enviados / leads_totais * 100.0) if leads_totais else 0.0

    return DashboardSummary(
        campaign_id=campaign_id,
        enviadas_hoje=db.scalar(msg_stmt) or 0,
        respostas_hoje=db.scalar(reply_stmt) or 0,
        falhas_hoje=db.scalar(fail_stmt) or 0,
        progresso_pct=round(progresso, 2),
        leads_totais=leads_totais,
        leads_restantes=leads_restantes,
        leads_enviados=leads_enviados,
        campanhas_ativas=active_campaigns,
        status_campanha=status_campanha,
    )
