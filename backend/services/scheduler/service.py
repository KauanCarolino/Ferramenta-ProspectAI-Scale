"""Scheduler de campanhas — distribuição de slots, pausa/retomada, agendamento de follow-ups.

Estratégia de pausa
-------------------
``cancel_pending_jobs`` marca todos os scheduled_jobs ``pending`` (e followups
``pending`` correspondentes) da campanha como ``cancelled``.

Estratégia de retomada
----------------------
``resume_pending_jobs`` reativa jobs/followups ``cancelled`` cujo
``scheduled_at`` ainda está no futuro → ``pending``.

Jobs cancelados com ``scheduled_at`` já no passado são redistribuídos nas
próximas janelas diárias (a partir de amanhã, ou hoje se ainda dentro da janela),
preservando a ordem dos leads, o batching de ``messages_per_day``, as regras de
intervalo e o round-robin de contas — assim nada fica preso após uma pausa longa.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.account import Account
from database.models.campaign import Campaign
from database.models.followup import FollowUp
from database.models.lead import Lead
from database.models.scheduled_job import ScheduledJob
from services.antiban import (
    RoundRobinState,
    build_day_caps,
    next_account_round_robin,
)
from services.scheduler.slots import followup_at, generate_day_slots

logger = logging.getLogger(__name__)

ACTIVE_ACCOUNT_STATUSES = frozenset({"active", "warming"})
FOLLOWUP_OFFSETS: dict[str, int] = {"d4": 3, "d8": 7}  # dias após o horário de envio d1


def schedule_campaign(
    db: Session,
    campaign_id: uuid.UUID,
    *,
    start_date: date | None = None,
    rng: random.Random | None = None,
) -> dict[str, object]:
    """Cria linhas d1 de ``ScheduledJob`` para leads ainda em ``novo``.

    Distribui leads em lotes de ``messages_per_day`` ao longo de ``duration_days``,
    atribui horários dentro da janela diária com intervalos aleatórios e faz
    round-robin entre contas active/warming (com consciência de warm-up/cota).
    """
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError(f"Campanha não encontrada: {campaign_id}")

    rng = rng or random.Random()
    day0 = start_date or datetime.now(UTC).date()
    accounts = _active_accounts(db)
    leads = _leads_needing_d1(db, campaign_id)
    if not leads:
        logger.info("schedule_campaign %s — nenhum lead novo para agendar", campaign_id)
        return {
            "campaign_id": str(campaign_id),
            "jobs_created": 0,
            "status": "ok",
            "detail": "Nenhum lead com status novo.",
        }

    per_day = campaign.messages_per_day
    jobs_created = 0
    day_caps = build_day_caps(accounts) if accounts else {}
    rr_state = RoundRobinState()
    account_ids = [a.id for a in accounts]

    for day_offset in range(campaign.duration_days):
        chunk_start = day_offset * per_day
        if chunk_start >= len(leads):
            break
        chunk = leads[chunk_start : chunk_start + per_day]
        slots = generate_day_slots(
            day0 + timedelta(days=day_offset),
            len(chunk),
            campaign.window_start,
            campaign.window_end,
            campaign.min_interval_sec,
            campaign.max_interval_sec,
            rng=rng,
        )
        # Novo dia de agendamento → zera contagem de atribuições do RR.
        rr_state.day_assignments.clear()
        for lead, slot in zip(chunk, slots, strict=True):
            account_id = None
            if accounts:
                account_id = next_account_round_robin(
                    db,
                    account_ids,
                    state=rr_state,
                    respect_rate_limit=False,
                    day_caps=day_caps,
                )
            job = ScheduledJob(
                campaign_id=campaign_id,
                lead_id=lead.id,
                account_id=account_id,
                stage="d1",
                scheduled_at=slot,
                status="pending",
                channel=campaign.channel,
            )
            db.add(job)
            lead.status = "agendado"
            jobs_created += 1

    # Leads restantes além de duration_days * messages_per_day permanecem ``novo``.
    db.commit()
    logger.info(
        "schedule_campaign %s — criados %s jobs d1 para %s leads",
        campaign_id,
        jobs_created,
        len(leads),
    )
    return {
        "campaign_id": str(campaign_id),
        "jobs_created": jobs_created,
        "status": "ok",
        "detail": f"Agendados {jobs_created} jobs d1 em {campaign.duration_days} dia(s).",
    }


def cancel_pending_jobs(db: Session, campaign_id: uuid.UUID) -> int:
    """Marca jobs pendentes (e followups pendentes) como cancelled. Retorna a contagem de jobs."""
    jobs = list(
        db.scalars(
            select(ScheduledJob).where(
                ScheduledJob.campaign_id == campaign_id,
                ScheduledJob.status == "pending",
            )
        ).all()
    )
    for job in jobs:
        job.status = "cancelled"

    followups = list(
        db.scalars(
            select(FollowUp).where(
                FollowUp.campaign_id == campaign_id,
                FollowUp.status == "pending",
            )
        ).all()
    )
    for fu in followups:
        fu.status = "cancelled"

    db.commit()
    logger.info(
        "cancel_pending_jobs %s — cancelados %s jobs, %s followups",
        campaign_id,
        len(jobs),
        len(followups),
    )
    return len(jobs)


def resume_pending_jobs(
    db: Session,
    campaign_id: uuid.UUID,
    *,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> dict[str, object]:
    """Reativa jobs cancelados — futuros no lugar; passados redistribuídos."""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError(f"Campanha não encontrada: {campaign_id}")

    now = now or datetime.now(UTC)
    rng = rng or random.Random()

    cancelled = list(
        db.scalars(
            select(ScheduledJob)
            .where(
                ScheduledJob.campaign_id == campaign_id,
                ScheduledJob.status == "cancelled",
            )
            .order_by(ScheduledJob.scheduled_at.asc())
        ).all()
    )

    reactivated = 0
    rescheduled = 0
    past_jobs: list[ScheduledJob] = []

    for job in cancelled:
        scheduled = _as_aware(job.scheduled_at)
        if scheduled >= now:
            job.status = "pending"
            reactivated += 1
        else:
            past_jobs.append(job)

    # Reativa followups cancelados com data futura no lugar.
    followups = list(
        db.scalars(
            select(FollowUp).where(
                FollowUp.campaign_id == campaign_id,
                FollowUp.status == "cancelled",
            )
        ).all()
    )
    fu_reactivated = 0
    for fu in followups:
        if _as_aware(fu.scheduled_at) >= now:
            fu.status = "pending"
            fu_reactivated += 1

    if past_jobs:
        rescheduled = _respread_jobs(db, campaign, past_jobs, now=now, rng=rng)

    db.commit()
    logger.info(
        "resume_pending_jobs %s — reativados=%s reagendados=%s followups=%s",
        campaign_id,
        reactivated,
        rescheduled,
        fu_reactivated,
    )
    return {
        "campaign_id": str(campaign_id),
        "reactivated": reactivated,
        "rescheduled": rescheduled,
        "followups_reactivated": fu_reactivated,
        "status": "ok",
    }


def schedule_followups_for_d1(
    db: Session,
    *,
    campaign: Campaign,
    lead: Lead,
    d1_scheduled_at: datetime,
    parent_message_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
    commit: bool = False,
) -> list[ScheduledJob]:
    """Cria FollowUp + ScheduledJob d4/d8 relativos ao horário de envio d1."""
    created: list[ScheduledJob] = []
    for stage, days in FOLLOWUP_OFFSETS.items():
        when = followup_at(
            d1_scheduled_at,
            days_offset=days,
            window_start=campaign.window_start,
            window_end=campaign.window_end,
        )
        fu = FollowUp(
            campaign_id=campaign.id,
            lead_id=lead.id,
            parent_message_id=parent_message_id,
            stage=stage,
            scheduled_at=when,
            status="pending",
        )
        db.add(fu)
        job = ScheduledJob(
            campaign_id=campaign.id,
            lead_id=lead.id,
            account_id=account_id,
            stage=stage,
            scheduled_at=when,
            status="pending",
            channel=campaign.channel,
        )
        db.add(job)
        created.append(job)

    if commit:
        db.commit()
    return created


def cancel_lead_pending(
    db: Session,
    lead_id: uuid.UUID,
    *,
    commit: bool = False,
) -> int:
    """Cancela followups e jobs pendentes de um lead (ex.: após resposta)."""
    jobs = list(
        db.scalars(
            select(ScheduledJob).where(
                ScheduledJob.lead_id == lead_id,
                ScheduledJob.status == "pending",
            )
        ).all()
    )
    for job in jobs:
        job.status = "cancelled"

    followups = list(
        db.scalars(
            select(FollowUp).where(
                FollowUp.lead_id == lead_id,
                FollowUp.status == "pending",
            )
        ).all()
    )
    for fu in followups:
        fu.status = "cancelled"

    if commit:
        db.commit()
    return len(jobs)


def list_campaign_jobs(
    db: Session,
    campaign_id: uuid.UUID,
    *,
    limit: int = 50,
    status: str | None = "pending",
) -> list[ScheduledJob]:
    stmt = (
        select(ScheduledJob)
        .where(ScheduledJob.campaign_id == campaign_id)
        .order_by(ScheduledJob.scheduled_at.asc())
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(ScheduledJob.status == status)
    return list(db.scalars(stmt).all())


def _leads_needing_d1(db: Session, campaign_id: uuid.UUID) -> list[Lead]:
    """Leads em ``novo`` sem job d1 existente (não-failed)."""
    existing_lead_ids = set(
        db.scalars(
            select(ScheduledJob.lead_id).where(
                ScheduledJob.campaign_id == campaign_id,
                ScheduledJob.stage == "d1",
                ScheduledJob.status.in_(("pending", "running", "done", "cancelled")),
            )
        ).all()
    )
    leads = list(
        db.scalars(
            select(Lead)
            .where(Lead.campaign_id == campaign_id, Lead.status == "novo")
            .order_by(Lead.created_at.asc())
        ).all()
    )
    return [lead for lead in leads if lead.id not in existing_lead_ids]


def _active_accounts(db: Session) -> list[Account]:
    return list(
        db.scalars(
            select(Account)
            .where(Account.status.in_(ACTIVE_ACCOUNT_STATUSES))
            .order_by(Account.created_at.asc())
        ).all()
    )


def _respread_jobs(
    db: Session,
    campaign: Campaign,
    jobs: list[ScheduledJob],
    *,
    now: datetime,
    rng: random.Random,
) -> int:
    """Reatribui jobs cancelados no passado às próximas janelas."""
    if not jobs:
        return 0

    accounts = _active_accounts(db)
    per_day = campaign.messages_per_day
    # Começa hoje se a janela ainda estiver aberta; senão amanhã.
    day0 = now.date()
    end_today = datetime.combine(day0, campaign.window_end, tzinfo=UTC)
    if now >= end_today:
        day0 = day0 + timedelta(days=1)

    day_caps = build_day_caps(accounts) if accounts else {}
    rr_state = RoundRobinState()
    account_ids = [a.id for a in accounts]
    count = 0
    for day_offset in range(0, campaign.duration_days + 30):  # limite superior generoso
        chunk_start = day_offset * per_day
        if chunk_start >= len(jobs):
            break
        chunk = jobs[chunk_start : chunk_start + per_day]
        target_day = day0 + timedelta(days=day_offset)
        slots = generate_day_slots(
            target_day,
            len(chunk),
            campaign.window_start,
            campaign.window_end,
            campaign.min_interval_sec,
            campaign.max_interval_sec,
            rng=rng,
        )
        rr_state.day_assignments.clear()
        # Se redistribuindo para "hoje", empurra qualquer slot já passado de ``now``.
        for job, slot in zip(chunk, slots, strict=True):
            when = slot if slot >= now else now + timedelta(seconds=rng.randint(30, 120))
            # Mantém dentro da janela daquele dia quando possível.
            day_end = datetime.combine(when.date(), campaign.window_end, tzinfo=UTC)
            if when > day_end:
                when = datetime.combine(
                    when.date() + timedelta(days=1),
                    campaign.window_start,
                    tzinfo=UTC,
                )
            account_id = job.account_id
            if accounts:
                account_id = next_account_round_robin(
                    db,
                    account_ids,
                    state=rr_state,
                    respect_rate_limit=False,
                    day_caps=day_caps,
                )
            job.scheduled_at = when
            job.account_id = account_id
            job.status = "pending"
            count += 1
    return count


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
