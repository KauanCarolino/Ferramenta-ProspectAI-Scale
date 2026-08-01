"""Executa jobs agendados vencidos (sync — invocável pela CLI, Celery ou testes)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.instagram import InstagramAdapter, SendResult, get_instagram_adapter
from config import get_settings
from database.models.account import Account
from database.models.campaign import Campaign
from database.models.followup import FollowUp
from database.models.lead import Lead
from database.models.message import Message
from database.models.scheduled_job import ScheduledJob
from database.models.template import Template
from services.antiban import (
    check_rate_limit,
    count_consecutive_failures,
    should_auto_pause,
    trigger_auto_pause,
)
from services.logging.service import write_log
from services.scheduler.service import cancel_lead_pending, schedule_followups_for_d1
from services.templates.service import render_template

logger = logging.getLogger(__name__)

AdapterFactory = Callable[..., InstagramAdapter]

_STAGE_AFTER_SUCCESS: dict[str, str] = {
    "d1": "aguardando_d4",
    "d4": "aguardando_d8",
    "d8": "concluido",
}

_DEFAULT_BODY = "Olá {{nome}}!"


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def process_due_jobs(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 100,
    campaign_id: uuid.UUID | None = None,
    adapter_factory: AdapterFactory | None = None,
) -> dict[str, int]:
    """Processa jobs pendentes com ``scheduled_at <= now`` de campanhas ativas.

    Factory padrão: ``get_instagram_adapter`` (stub em CI; instagrapi se configurado).
    Passa username/session_path/proxy da Account do job.
    Retorna contagens: processed / succeeded / failed / skipped / deferred.
    """
    now = now or datetime.now(UTC)
    now_aware = _as_aware(now)
    # SQLite devolve UTC naive; compara em espaço UTC-naive para queries portáveis.
    now_db = now_aware.replace(tzinfo=None)
    factory = adapter_factory or get_instagram_adapter
    settings = get_settings()
    failure_threshold = settings.antiban_consecutive_failure_threshold

    stmt = (
        select(ScheduledJob)
        .where(
            ScheduledJob.status == "pending",
            ScheduledJob.scheduled_at <= now_db,
        )
        .order_by(ScheduledJob.scheduled_at.asc())
        .limit(limit)
    )
    if campaign_id is not None:
        stmt = stmt.where(ScheduledJob.campaign_id == campaign_id)

    jobs = list(db.scalars(stmt).all())
    processed = succeeded = failed = skipped = deferred = 0
    # Falhas consecutivas nesta execução (somadas ao histórico do DB).
    run_failures: dict[uuid.UUID, int] = {}

    for job in jobs:
        campaign = db.get(Campaign, job.campaign_id)
        if campaign is None or campaign.status != "active":
            skipped += 1
            continue

        lead = db.get(Lead, job.lead_id)
        if lead is None:
            job.status = "failed"
            processed += 1
            failed += 1
            db.commit()
            continue

        if lead.status == "respondido":
            cancel_lead_pending(db, lead.id, commit=False)
            job.status = "cancelled"
            skipped += 1
            db.commit()
            continue

        # Rate limit / min delay — defer sem marcar failed.
        if job.account_id is not None:
            decision = check_rate_limit(
                db,
                job.account_id,
                now=now_aware,
                settings=settings,
            )
            if not decision.allowed:
                wait = max(decision.wait_seconds, 1.0)
                new_at = now_aware + timedelta(seconds=wait)
                job.status = "pending"
                job.scheduled_at = new_at.replace(tzinfo=None)
                deferred += 1
                write_log(
                    db,
                    action="retry",
                    result="info",
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    account_id=job.account_id,
                    instagram_handle=lead.instagram,
                    details=f"deferred:{decision.reason} wait={wait:.0f}s",
                    commit=False,
                )
                db.commit()
                logger.info(
                    "Job %s deferred account=%s reason=%s wait=%.0fs",
                    job.id,
                    job.account_id,
                    decision.reason,
                    wait,
                )
                continue

        job.status = "running"
        db.flush()

        try:
            result = _execute_job(
                db,
                campaign=campaign,
                lead=lead,
                job=job,
                factory=factory,
                now=now_aware,
            )
        except Exception as exc:  # noqa: BLE001 — isola falhas por job
            logger.exception("Job %s falhou inesperadamente", job.id)
            job.status = "failed"
            lead.status = "falhou"
            write_log(
                db,
                action="send" if job.stage == "d1" else "followup",
                result="failed",
                campaign_id=campaign.id,
                lead_id=lead.id,
                account_id=job.account_id,
                instagram_handle=lead.instagram,
                error=str(exc),
                commit=False,
            )
            db.commit()
            processed += 1
            failed += 1
            _note_failure_and_maybe_pause(
                db,
                campaign,
                account_id=job.account_id,
                run_failures=run_failures,
                threshold=failure_threshold,
                reason=f"unexpected:{exc}",
                message_recorded=False,
            )
            continue

        processed += 1
        if result:
            succeeded += 1
            run_failures[campaign.id] = 0
        else:
            failed += 1
            _note_failure_and_maybe_pause(
                db,
                campaign,
                account_id=job.account_id,
                run_failures=run_failures,
                threshold=failure_threshold,
                reason="send_failed",
                message_recorded=True,
            )

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "deferred": deferred,
    }


def _note_failure_and_maybe_pause(
    db: Session,
    campaign: Campaign,
    *,
    account_id: uuid.UUID | None,
    run_failures: dict[uuid.UUID, int],
    threshold: int,
    reason: str,
    message_recorded: bool,
) -> None:
    db.refresh(campaign)
    if campaign.status != "active":
        return

    if message_recorded:
        consecutive = count_consecutive_failures(db, campaign.id)
    else:
        base = run_failures.get(campaign.id)
        if base is None:
            base = count_consecutive_failures(db, campaign.id)
        consecutive = base + 1
    run_failures[campaign.id] = consecutive

    if should_auto_pause(consecutive_failures=consecutive, threshold=threshold):
        trigger_auto_pause(
            db,
            campaign,
            reason=f"circuit_breaker:{consecutive}_failures ({reason})",
            account_id=account_id,
        )


def _execute_job(
    db: Session,
    *,
    campaign: Campaign,
    lead: Lead,
    job: ScheduledJob,
    factory: AdapterFactory,
    now: datetime | None = None,
) -> bool:
    body = _template_body(db, campaign.id, job.stage)
    variables = {
        "nome": lead.nome,
        "empresa": lead.empresa,
        "cargo": lead.cargo,
        "cidade": lead.cidade,
        "observacoes": lead.observacoes,
        "instagram": lead.instagram,
    }
    content = render_template(body, variables, seed=f"{lead.id}-{job.stage}")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    account = db.get(Account, job.account_id) if job.account_id else None
    adapter = _adapter_for_account(factory, account)
    send_result = adapter.send_dm(lead.instagram, content)
    action = "send" if job.stage == "d1" else "followup"

    message_result, ok = _map_send_result(send_result)
    _apply_account_send_status(account, send_result)

    sent_at = _as_aware(now or datetime.now(UTC)) if ok else None
    message = Message(
        campaign_id=campaign.id,
        lead_id=lead.id,
        account_id=job.account_id,
        stage=job.stage,
        content=content,
        content_hash=content_hash,
        result=message_result,
        error=send_result.error,
        sent_at=sent_at,
        channel=job.channel,
    )
    db.add(message)
    db.flush()

    write_log(
        db,
        action=action,
        result=message_result,
        campaign_id=campaign.id,
        lead_id=lead.id,
        account_id=job.account_id,
        instagram_handle=lead.instagram,
        error=send_result.error,
        message_hash=content_hash,
        commit=False,
    )

    if not ok:
        job.status = "failed"
        lead.status = "falhou"
        db.commit()
        return False

    job.status = "done"
    _mark_followup_done(db, lead_id=lead.id, stage=job.stage)

    if job.stage == "d1":
        schedule_followups_for_d1(
            db,
            campaign=campaign,
            lead=lead,
            d1_scheduled_at=job.scheduled_at
            if job.scheduled_at.tzinfo
            else job.scheduled_at.replace(tzinfo=UTC),
            parent_message_id=message.id,
            account_id=job.account_id,
            commit=False,
        )

    lead.status = _STAGE_AFTER_SUCCESS.get(job.stage, lead.status)
    db.commit()
    return True


def _template_body(db: Session, campaign_id: uuid.UUID, stage: str) -> str:
    template = db.scalar(
        select(Template).where(Template.campaign_id == campaign_id, Template.stage == stage)
    )
    return template.body if template is not None else _DEFAULT_BODY


def _adapter_for_account(factory: AdapterFactory, account: Account | None) -> InstagramAdapter:
    if account is None:
        return factory(None)
    return factory(
        account.username,
        session_path=account.session_path,
        proxy=account.proxy,
    )


def _apply_account_send_status(account: Account | None, result: SendResult) -> None:
    """Mapeia challenge/block do envio para status da conta."""
    if account is None:
        return
    if result.challenge:
        account.status = "challenge"
    elif result.blocked:
        account.status = "paused"


def _map_send_result(result: SendResult) -> tuple[str, bool]:
    if result.challenge:
        return "challenge", False
    if result.blocked:
        return "blocked", False
    if result.success:
        return "success", True
    return "failed", False


def _mark_followup_done(db: Session, *, lead_id: uuid.UUID, stage: str) -> None:
    if stage not in ("d4", "d8"):
        return
    fu = db.scalar(
        select(FollowUp).where(
            FollowUp.lead_id == lead_id,
            FollowUp.stage == stage,
            FollowUp.status == "pending",
        )
    )
    if fu is not None:
        fu.status = "done"
