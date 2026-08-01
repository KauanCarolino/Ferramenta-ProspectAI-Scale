"""Testes unitários do scheduler — slots, agendamento, follow-ups, pausa, process_due."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.instagram import SendResult
from database.models.account import Account
from database.models.campaign import Campaign
from database.models.followup import FollowUp
from database.models.lead import Lead
from database.models.message import Message
from database.models.scheduled_job import ScheduledJob
from database.models.template import Template
from services.scheduler.service import (
    cancel_pending_jobs,
    resume_pending_jobs,
    schedule_campaign,
    schedule_followups_for_d1,
)
from services.scheduler.slots import followup_at, generate_day_slots, window_duration_seconds
from services.scheduler.worker import process_due_jobs


def _make_campaign(db: Session, **overrides: object) -> Campaign:
    defaults: dict[str, object] = {
        "name": f"Camp {uuid.uuid4().hex[:6]}",
        "status": "draft",
        "messages_per_day": 3,
        "duration_days": 2,
        "window_start": time(9, 0),
        "window_end": time(18, 0),
        "min_interval_sec": 120,
        "max_interval_sec": 300,
    }
    defaults.update(overrides)
    campaign = Campaign(**defaults)  # type: ignore[arg-type]
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _make_leads(db: Session, campaign_id: uuid.UUID, n: int) -> list[Lead]:
    leads: list[Lead] = []
    for i in range(n):
        lead = Lead(
            campaign_id=campaign_id,
            nome=f"Lead {i}",
            empresa="Acme",
            cargo="Dev",
            instagram=f"user{i}_{uuid.uuid4().hex[:4]}",
            status="novo",
        )
        db.add(lead)
        leads.append(lead)
    db.commit()
    for lead in leads:
        db.refresh(lead)
    return leads


# ---------------------------------------------------------------------------
# Geração de slots
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_generate_day_slots_count_and_window() -> None:
    rng = random.Random(42)
    day = date(2026, 8, 1)
    slots = generate_day_slots(
        day,
        5,
        time(9, 0),
        time(18, 0),
        120,
        300,
        rng=rng,
    )
    assert len(slots) == 5
    start = datetime.combine(day, time(9, 0), tzinfo=UTC)
    end = datetime.combine(day, time(18, 0), tzinfo=UTC)
    for slot in slots:
        assert start <= slot <= end
    for a, b in zip(slots, slots[1:], strict=False):
        gap = (b - a).total_seconds()
        assert gap >= 120


@pytest.mark.unit
def test_generate_day_slots_exactly_n() -> None:
    rng = random.Random(1)
    slots = generate_day_slots(date(2026, 1, 1), 150, time(9, 0), time(18, 0), 120, 300, rng=rng)
    assert len(slots) == 150
    assert slots == sorted(slots)


@pytest.mark.unit
def test_generate_day_slots_fits_when_min_too_large() -> None:
    """Se min_interval * (n-1) > janela, ainda assim retorna n slots dentro da janela."""
    rng = random.Random(7)
    # Janela de 1h, 10 slots, min 600s → precisaria de 5400s; deve comprimir.
    slots = generate_day_slots(date(2026, 1, 1), 10, time(9, 0), time(10, 0), 600, 900, rng=rng)
    assert len(slots) == 10
    start = datetime.combine(date(2026, 1, 1), time(9, 0), tzinfo=UTC)
    end = datetime.combine(date(2026, 1, 1), time(10, 0), tzinfo=UTC)
    assert slots[0] >= start
    assert slots[-1] <= end


@pytest.mark.unit
def test_window_duration_seconds() -> None:
    assert window_duration_seconds(time(9, 0), time(18, 0)) == 9 * 3600


@pytest.mark.unit
def test_followup_at_offsets() -> None:
    base = datetime(2026, 8, 1, 10, 30, tzinfo=UTC)
    d4 = followup_at(base, days_offset=3, window_start=time(9, 0), window_end=time(18, 0))
    d8 = followup_at(base, days_offset=7, window_start=time(9, 0), window_end=time(18, 0))
    assert d4.date() == date(2026, 8, 4)
    assert d8.date() == date(2026, 8, 8)
    assert d4.hour == 10 and d4.minute == 30


# ---------------------------------------------------------------------------
# schedule_campaign
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_schedule_campaign_creates_jobs_for_leads(db_session: Session) -> None:
    campaign = _make_campaign(db_session, messages_per_day=3, duration_days=2)
    leads = _make_leads(db_session, campaign.id, 7)
    rng = random.Random(99)
    start = date(2026, 8, 1)

    result = schedule_campaign(db_session, campaign.id, start_date=start, rng=rng)

    assert result["jobs_created"] == 6  # 2 dias × 3; o 7º permanece novo
    jobs = list(
        db_session.scalars(
            select(ScheduledJob)
            .where(ScheduledJob.campaign_id == campaign.id)
            .order_by(ScheduledJob.scheduled_at.asc())
        ).all()
    )
    assert len(jobs) == 6
    assert all(j.stage == "d1" for j in jobs)
    assert all(j.status == "pending" for j in jobs)

    for lead in leads:
        db_session.refresh(lead)
    scheduled = [lead for lead in leads if lead.status == "agendado"]
    still_novo = [lead for lead in leads if lead.status == "novo"]
    assert len(scheduled) == 6
    assert len(still_novo) == 1

    dates = sorted(
        {
            (j.scheduled_at if j.scheduled_at.tzinfo else j.scheduled_at.replace(tzinfo=UTC)).date()
            for j in jobs
        }
    )
    assert dates[0] == start
    assert (dates[-1] - dates[0]).days == 1


@pytest.mark.unit
def test_schedule_campaign_round_robin_accounts(db_session: Session) -> None:
    campaign = _make_campaign(db_session, messages_per_day=4, duration_days=1)
    _make_leads(db_session, campaign.id, 4)
    a1 = Account(username=f"acc_a_{uuid.uuid4().hex[:4]}", status="active")
    a2 = Account(username=f"acc_b_{uuid.uuid4().hex[:4]}", status="warming")
    a3 = Account(username=f"acc_c_{uuid.uuid4().hex[:4]}", status="paused")  # ignorada
    db_session.add_all([a1, a2, a3])
    db_session.commit()

    schedule_campaign(db_session, campaign.id, start_date=date(2026, 8, 1), rng=random.Random(1))
    jobs = list(
        db_session.scalars(
            select(ScheduledJob)
            .where(ScheduledJob.campaign_id == campaign.id)
            .order_by(ScheduledJob.scheduled_at.asc())
        ).all()
    )
    account_ids = [j.account_id for j in jobs]
    assert None not in account_ids
    assert set(account_ids) == {a1.id, a2.id}
    # Round-robin: A, B, A, B
    assert account_ids[0] == a1.id
    assert account_ids[1] == a2.id
    assert account_ids[2] == a1.id
    assert account_ids[3] == a2.id


@pytest.mark.unit
def test_schedule_campaign_without_accounts(db_session: Session) -> None:
    campaign = _make_campaign(db_session, messages_per_day=2, duration_days=1)
    _make_leads(db_session, campaign.id, 2)
    schedule_campaign(db_session, campaign.id, start_date=date(2026, 8, 1), rng=random.Random(2))
    jobs = list(db_session.scalars(select(ScheduledJob)).all())
    assert len(jobs) == 2
    assert all(j.account_id is None for j in jobs)


# ---------------------------------------------------------------------------
# Follow-ups D+3 / D+7
# ---------------------------------------------------------------------------



@pytest.mark.unit
def test_schedule_followups_d3_d7(db_session: Session) -> None:
    campaign = _make_campaign(db_session)
    leads = _make_leads(db_session, campaign.id, 1)
    lead = leads[0]
    d1_at = datetime(2026, 8, 1, 11, 0, tzinfo=UTC)

    jobs = schedule_followups_for_d1(
        db_session,
        campaign=campaign,
        lead=lead,
        d1_scheduled_at=d1_at,
        parent_message_id=None,
        account_id=None,
        commit=True,
    )
    assert len(jobs) == 2
    by_stage = {j.stage: j for j in jobs}
    assert by_stage["d4"].scheduled_at.date() == date(2026, 8, 4)
    assert by_stage["d8"].scheduled_at.date() == date(2026, 8, 8)

    followups = list(db_session.scalars(select(FollowUp).where(FollowUp.lead_id == lead.id)).all())
    assert {f.stage for f in followups} == {"d4", "d8"}
    assert all(f.status == "pending" for f in followups)


# ---------------------------------------------------------------------------
# Pausa / retomada
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pause_cancels_pending_jobs(db_session: Session) -> None:
    campaign = _make_campaign(db_session, messages_per_day=5, duration_days=1)
    _make_leads(db_session, campaign.id, 5)
    schedule_campaign(db_session, campaign.id, start_date=date(2026, 8, 1), rng=random.Random(3))

    cancelled = cancel_pending_jobs(db_session, campaign.id)
    assert cancelled == 5
    jobs = list(db_session.scalars(select(ScheduledJob)).all())
    assert all(j.status == "cancelled" for j in jobs)


@pytest.mark.unit
def test_resume_reactivates_future_cancelled(db_session: Session) -> None:
    campaign = _make_campaign(db_session, messages_per_day=3, duration_days=1)
    _make_leads(db_session, campaign.id, 3)
    future_day = date(2026, 9, 1)
    schedule_campaign(db_session, campaign.id, start_date=future_day, rng=random.Random(4))
    cancel_pending_jobs(db_session, campaign.id)

    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    result = resume_pending_jobs(db_session, campaign.id, now=now, rng=random.Random(4))
    assert result["reactivated"] == 3
    jobs = list(db_session.scalars(select(ScheduledJob)).all())
    assert all(j.status == "pending" for j in jobs)


# ---------------------------------------------------------------------------
# process_due_jobs
# ---------------------------------------------------------------------------


class _OkAdapter:
    def send_dm(self, username: str, text: str) -> SendResult:
        return SendResult(success=True, message_id="ok-1")


class _FailAdapter:
    def send_dm(self, username: str, text: str) -> SendResult:
        return SendResult(success=False, error="boom")


@pytest.mark.unit
def test_process_due_jobs_updates_lead_and_message(db_session: Session) -> None:
    campaign = _make_campaign(db_session, status="active", messages_per_day=2, duration_days=1)
    leads = _make_leads(db_session, campaign.id, 2)
    db_session.add(
        Template(campaign_id=campaign.id, stage="d1", body="Oi {{nome}} da {{empresa}}")
    )
    db_session.commit()

    past = date(2026, 7, 1)
    schedule_campaign(db_session, campaign.id, start_date=past, rng=random.Random(5))
    # Garante campanha ativa (schedule não altera o status)
    campaign.status = "active"
    db_session.commit()

    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    result = process_due_jobs(
        db_session,
        now=now,
        adapter_factory=lambda *a, **k: _OkAdapter(),  # type: ignore[return-value,arg-type]
    )
    assert result["succeeded"] == 2
    assert result["failed"] == 0

    messages = list(db_session.scalars(select(Message)).all())
    assert len(messages) == 2
    assert all(m.result == "success" for m in messages)
    assert all("Oi" in m.content for m in messages)

    for lead in leads:
        db_session.refresh(lead)
        assert lead.status == "aguardando_d4"

    # Jobs de follow-up criados
    follow_jobs = list(
        db_session.scalars(select(ScheduledJob).where(ScheduledJob.stage.in_(("d4", "d8")))).all()
    )
    assert len(follow_jobs) == 4  # 2 leads × 2 estágios

    d1_jobs = list(
        db_session.scalars(select(ScheduledJob).where(ScheduledJob.stage == "d1")).all()
    )
    assert all(j.status == "done" for j in d1_jobs)


@pytest.mark.unit
def test_process_due_jobs_skips_paused_campaign(db_session: Session) -> None:
    campaign = _make_campaign(db_session, status="paused", messages_per_day=1, duration_days=1)
    _make_leads(db_session, campaign.id, 1)
    schedule_campaign(db_session, campaign.id, start_date=date(2026, 7, 1), rng=random.Random(6))
    campaign.status = "paused"
    db_session.commit()

    result = process_due_jobs(
        db_session,
        now=datetime(2026, 8, 1, tzinfo=UTC),
        adapter_factory=lambda *a, **k: _OkAdapter(),  # type: ignore[return-value,arg-type]
    )
    assert result["skipped"] >= 1
    assert result["succeeded"] == 0


@pytest.mark.unit
def test_process_due_cancels_when_lead_respondido(db_session: Session) -> None:
    campaign = _make_campaign(db_session, status="active", messages_per_day=1, duration_days=1)
    leads = _make_leads(db_session, campaign.id, 1)
    schedule_campaign(db_session, campaign.id, start_date=date(2026, 7, 1), rng=random.Random(8))
    campaign.status = "active"
    leads[0].status = "respondido"
    db_session.commit()

    result = process_due_jobs(
        db_session,
        now=datetime(2026, 8, 1, tzinfo=UTC),
        adapter_factory=lambda *a, **k: _OkAdapter(),  # type: ignore[return-value,arg-type]
    )
    assert result["skipped"] >= 1
    job = db_session.scalars(select(ScheduledJob)).first()
    assert job is not None
    assert job.status == "cancelled"
