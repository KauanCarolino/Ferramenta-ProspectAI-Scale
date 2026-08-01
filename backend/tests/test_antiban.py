"""Testes unitários do anti-ban — warm-up, rate limit, circuit breaker, worker."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.instagram import SendResult
from config import Settings, get_settings
from database.models.account import Account
from database.models.campaign import Campaign
from database.models.lead import Lead
from database.models.log import Log
from database.models.message import Message
from database.models.scheduled_job import ScheduledJob
from database.models.template import Template
from services.antiban import (
    RoundRobinState,
    check_rate_limit,
    daily_cap_for_account,
    effective_warmup_day,
    maybe_advance_warmup,
    next_account_round_robin,
    should_auto_pause,
)
from services.antiban.service import build_day_caps
from services.scheduler.service import schedule_campaign
from services.scheduler.worker import process_due_jobs


def _settings(**overrides: object) -> Settings:
    base = {
        "antiban_max_dm_per_account_per_day": 50,
        "antiban_min_delay_sec": 120,
        "antiban_max_delay_sec": 300,
        "antiban_consecutive_failure_threshold": 5,
        "antiban_warmup_enabled": True,
        "proxy_urls": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _make_campaign(db: Session, **overrides: object) -> Campaign:
    defaults: dict[str, object] = {
        "name": f"Camp {uuid.uuid4().hex[:6]}",
        "status": "active",
        "messages_per_day": 3,
        "duration_days": 1,
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


def _make_account(db: Session, **overrides: object) -> Account:
    defaults: dict[str, object] = {
        "username": f"acc_{uuid.uuid4().hex[:8]}",
        "status": "active",
        "warmup_day": 0,
    }
    defaults.update(overrides)
    account = Account(**defaults)  # type: ignore[arg-type]
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


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


def _add_success(db: Session, account_id: uuid.UUID, campaign_id: uuid.UUID, when: datetime) -> None:
    lead = Lead(
        campaign_id=campaign_id,
        nome="X",
        empresa="Y",
        cargo="Z",
        instagram=f"u_{uuid.uuid4().hex[:6]}",
        status="aguardando_d4",
    )
    db.add(lead)
    db.flush()
    db.add(
        Message(
            campaign_id=campaign_id,
            lead_id=lead.id,
            account_id=account_id,
            stage="d1",
            content="hi",
            result="success",
            sent_at=when,
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# Warm-up caps
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_warmup_caps_by_day() -> None:
    settings = _settings(antiban_max_dm_per_account_per_day=50, antiban_warmup_enabled=True)
    warming = Account(username="w", status="warming", warmup_day=0)
    assert effective_warmup_day(warming) == 1
    assert daily_cap_for_account(warming, settings=settings) == 20

    warming.warmup_day = 2
    assert daily_cap_for_account(warming, settings=settings) == 40
    warming.warmup_day = 3
    # Cap de rampa 60 limitado pelo max diário configurado (50).
    assert daily_cap_for_account(warming, settings=settings) == 50
    warming.warmup_day = 4
    assert daily_cap_for_account(warming, settings=settings) == 50

    active = Account(username="a", status="active", warmup_day=0)
    assert effective_warmup_day(active) == 4
    assert daily_cap_for_account(active, settings=settings) == 50


@pytest.mark.unit
def test_warmup_disabled_uses_max() -> None:
    settings = _settings(antiban_warmup_enabled=False, antiban_max_dm_per_account_per_day=50)
    warming = Account(username="w", status="warming", warmup_day=1)
    assert daily_cap_for_account(warming, settings=settings) == 50


@pytest.mark.unit
def test_warmup_does_not_raise_cap_same_calendar_day(db_session: Session) -> None:
    """Após 20 sucessos no Dia 1, o 21º no mesmo dia continua negado (cap não sobe)."""
    settings = _settings(antiban_min_delay_sec=0, antiban_warmup_enabled=True)
    campaign = _make_campaign(db_session)
    account = _make_account(db_session, status="warming", warmup_day=1)
    now = datetime(2026, 8, 1, 15, 0, tzinfo=UTC)

    for _ in range(20):
        _add_success(db_session, account.id, campaign.id, now)

    with patch("services.antiban.service.get_settings", return_value=settings):
        # Ainda no mesmo dia: não avança.
        assert maybe_advance_warmup(db_session, account, now=now, settings=settings) is False
        assert account.warmup_day == 1

        decision = check_rate_limit(db_session, account.id, now=now, settings=settings)
        assert decision.allowed is False
        assert "daily_cap_reached" in decision.reason
        assert "20/20" in decision.reason


@pytest.mark.unit
def test_maybe_advance_warmup_on_next_utc_day(db_session: Session) -> None:
    settings = _settings(antiban_min_delay_sec=0)
    campaign = _make_campaign(db_session)
    account = _make_account(db_session, status="warming", warmup_day=1)
    day1 = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    day2 = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)

    for _ in range(20):
        _add_success(db_session, account.id, campaign.id, day1)

    with patch("services.antiban.service.get_settings", return_value=settings):
        assert maybe_advance_warmup(db_session, account, now=day2, settings=settings) is True
        assert account.warmup_day == 2
        # Cap do novo dia (ainda sem envios hoje) = 40.
        decision = check_rate_limit(db_session, account.id, now=day2, settings=settings)
        assert decision.allowed is True
        assert daily_cap_for_account(account, settings=settings) == 40


@pytest.mark.unit
def test_maybe_advance_warmup_promotes_to_active(db_session: Session) -> None:
    settings = _settings(antiban_max_dm_per_account_per_day=50)
    campaign = _make_campaign(db_session)
    account = _make_account(db_session, status="warming", warmup_day=3)
    # Dia 3 cap = min(60, 50) = 50
    day3 = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
    day4 = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
    for _ in range(50):
        _add_success(db_session, account.id, campaign.id, day3)

    with patch("services.antiban.service.get_settings", return_value=settings):
        assert maybe_advance_warmup(db_session, account, now=day4, settings=settings) is True
        assert account.warmup_day == 4
        assert account.status == "active"


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rate_limit_allow_and_deny_daily_cap(db_session: Session) -> None:
    settings = _settings(antiban_min_delay_sec=0, antiban_warmup_enabled=True)
    campaign = _make_campaign(db_session)
    account = _make_account(db_session, status="warming", warmup_day=1)
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    with patch("services.antiban.service.get_settings", return_value=settings):
        decision = check_rate_limit(db_session, account.id, now=now, settings=settings)
        assert decision.allowed is True

        for _ in range(20):
            _add_success(db_session, account.id, campaign.id, now)

        decision = check_rate_limit(db_session, account.id, now=now, settings=settings)
        assert decision.allowed is False
        assert "daily_cap_reached" in decision.reason
        assert decision.wait_seconds >= 60


@pytest.mark.unit
def test_rate_limit_min_delay(db_session: Session) -> None:
    settings = _settings(antiban_min_delay_sec=120, antiban_warmup_enabled=False)
    campaign = _make_campaign(db_session)
    account = _make_account(db_session, status="active", warmup_day=4)
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    _add_success(db_session, account.id, campaign.id, now - timedelta(seconds=30))

    decision = check_rate_limit(db_session, account.id, now=now, settings=settings)
    assert decision.allowed is False
    assert decision.reason.startswith("min_delay")
    assert 80 <= decision.wait_seconds <= 120


@pytest.mark.unit
def test_circuit_breaker_threshold() -> None:
    assert should_auto_pause(consecutive_failures=4, threshold=5) is False
    assert should_auto_pause(consecutive_failures=5, threshold=5) is True
    assert should_auto_pause(consecutive_failures=6, threshold=5) is True


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_round_robin_skips_account_at_daily_cap(db_session: Session) -> None:
    settings = _settings(antiban_min_delay_sec=0, antiban_warmup_enabled=True)
    campaign = _make_campaign(db_session)
    a1 = _make_account(db_session, status="warming", warmup_day=1)  # cap 20
    a2 = _make_account(db_session, status="warming", warmup_day=1)
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    for _ in range(20):
        _add_success(db_session, a1.id, campaign.id, now)

    state = RoundRobinState()
    with patch("services.antiban.service.get_settings", return_value=settings):
        chosen = [
            next_account_round_robin(
                db_session,
                [a1.id, a2.id],
                state=state,
                settings=settings,
                now=now,
                respect_rate_limit=True,
            )
            for _ in range(4)
        ]
    assert all(cid == a2.id for cid in chosen)


@pytest.mark.unit
def test_schedule_respects_warmup_day_caps(db_session: Session) -> None:
    """Conta warming dia 1 (cap 20) não recebe mais que o cap no mesmo dia de agenda."""
    settings = _settings(antiban_warmup_enabled=True)
    campaign = _make_campaign(db_session, messages_per_day=25, duration_days=1)
    _make_leads(db_session, campaign.id, 25)
    a1 = _make_account(db_session, status="warming", warmup_day=1)
    a2 = _make_account(db_session, status="active", warmup_day=4)

    with patch("services.scheduler.service.build_day_caps") as mock_caps:
        mock_caps.return_value = build_day_caps([a1, a2], settings=settings)
        schedule_campaign(
            db_session, campaign.id, start_date=date(2026, 8, 1), rng=random.Random(1)
        )

    jobs = list(db_session.scalars(select(ScheduledJob)).all())
    assert len(jobs) == 25
    by_acc: dict[uuid.UUID, int] = {}
    for job in jobs:
        assert job.account_id is not None
        by_acc[job.account_id] = by_acc.get(job.account_id, 0) + 1
    assert by_acc.get(a1.id, 0) <= 20
    assert by_acc.get(a2.id, 0) >= 5


# ---------------------------------------------------------------------------
# Worker integration
# ---------------------------------------------------------------------------


class _OkAdapter:
    def send_dm(self, username: str, text: str) -> SendResult:
        return SendResult(success=True, message_id="ok-1")


class _FailAdapter:
    def send_dm(self, username: str, text: str) -> SendResult:
        return SendResult(success=False, error="boom")


@pytest.mark.unit
def test_worker_defers_when_rate_limited(db_session: Session) -> None:
    settings = _settings(
        antiban_min_delay_sec=0,
        antiban_warmup_enabled=True,
        antiban_max_dm_per_account_per_day=50,
    )
    campaign = _make_campaign(db_session, status="active", messages_per_day=2, duration_days=1)
    account = _make_account(db_session, status="warming", warmup_day=1)
    leads = _make_leads(db_session, campaign.id, 2)
    db_session.add(Template(campaign_id=campaign.id, stage="d1", body="Oi {{nome}}"))
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    for _ in range(20):
        _add_success(db_session, account.id, campaign.id, now)

    for lead in leads:
        db_session.add(
            ScheduledJob(
                campaign_id=campaign.id,
                lead_id=lead.id,
                account_id=account.id,
                stage="d1",
                scheduled_at=now.replace(tzinfo=None) - timedelta(minutes=1),
                status="pending",
                channel="instagram",
            )
        )
        lead.status = "agendado"
    db_session.commit()

    with (
        patch("services.scheduler.worker.get_settings", return_value=settings),
        patch("services.antiban.service.get_settings", return_value=settings),
    ):
        result = process_due_jobs(
            db_session,
            now=now,
            adapter_factory=lambda *a, **k: _OkAdapter(),  # type: ignore[return-value,arg-type]
        )

    assert result["deferred"] == 2
    assert result["succeeded"] == 0
    jobs = list(db_session.scalars(select(ScheduledJob)).all())
    assert all(j.status == "pending" for j in jobs)
    for job in jobs:
        scheduled = job.scheduled_at if job.scheduled_at.tzinfo else job.scheduled_at.replace(
            tzinfo=UTC
        )
        assert scheduled > now


@pytest.mark.unit
def test_worker_auto_pause_after_n_failures(db_session: Session) -> None:
    settings = _settings(
        antiban_consecutive_failure_threshold=3,
        antiban_min_delay_sec=0,
        antiban_warmup_enabled=False,
    )
    campaign = _make_campaign(db_session, status="active", messages_per_day=5, duration_days=1)
    account = _make_account(db_session, status="active", warmup_day=4)
    leads = _make_leads(db_session, campaign.id, 5)
    db_session.add(Template(campaign_id=campaign.id, stage="d1", body="Oi {{nome}}"))
    now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    for i, lead in enumerate(leads):
        db_session.add(
            ScheduledJob(
                campaign_id=campaign.id,
                lead_id=lead.id,
                account_id=account.id,
                stage="d1",
                scheduled_at=now.replace(tzinfo=None) - timedelta(minutes=5 - i),
                status="pending",
                channel="instagram",
            )
        )
        lead.status = "agendado"
    db_session.commit()

    with (
        patch("services.scheduler.worker.get_settings", return_value=settings),
        patch("services.antiban.service.get_settings", return_value=settings),
    ):
        result = process_due_jobs(
            db_session,
            now=now,
            adapter_factory=lambda *a, **k: _FailAdapter(),  # type: ignore[return-value,arg-type]
        )

    db_session.refresh(campaign)
    assert campaign.status == "auto_paused"
    assert result["failed"] >= 3
    # Jobs restantes pending foram cancelados pelo auto_pause
    pending = list(
        db_session.scalars(
            select(ScheduledJob).where(ScheduledJob.status == "pending")
        ).all()
    )
    assert pending == []
    pause_logs = list(
        db_session.scalars(select(Log).where(Log.action == "pause")).all()
    )
    assert len(pause_logs) >= 1


@pytest.mark.unit
def test_settings_endpoint_exposes_antiban(client) -> None:
    get_settings.cache_clear()
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["daily_dm_limit"] == 50
    assert data["min_delay_seconds"] == 120
    assert data["max_delay_seconds"] == 300
    assert data["warmup_days"] == 4
    assert data["proxy_rotation"] is False
