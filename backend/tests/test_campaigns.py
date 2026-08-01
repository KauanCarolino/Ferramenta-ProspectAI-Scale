"""Testes de cancelamento de campanha (transições + jobs)."""

from __future__ import annotations

import random
import uuid
from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.campaign import Campaign
from database.models.lead import Lead
from database.models.scheduled_job import ScheduledJob
from services.campaigns.service import cancel_campaign
from services.scheduler.service import schedule_campaign


def _make_campaign(db: Session, **overrides: object) -> Campaign:
    defaults: dict[str, object] = {
        "name": f"Camp {uuid.uuid4().hex[:6]}",
        "status": "draft",
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


@pytest.mark.unit
@pytest.mark.parametrize("status", ["draft", "active", "paused", "auto_paused"])
def test_cancel_from_allowed_statuses(db_session: Session, status: str) -> None:
    campaign = _make_campaign(db_session, status=status)
    result = cancel_campaign(db_session, campaign.id)
    assert result.status == "cancelled"
    db_session.refresh(campaign)
    assert campaign.status == "cancelled"


@pytest.mark.unit
def test_cancel_from_completed_raises_409(db_session: Session) -> None:
    campaign = _make_campaign(db_session, status="completed")
    with pytest.raises(HTTPException) as exc_info:
        cancel_campaign(db_session, campaign.id)
    assert exc_info.value.status_code == 409
    db_session.refresh(campaign)
    assert campaign.status == "completed"


@pytest.mark.unit
def test_cancel_from_cancelled_is_idempotent(db_session: Session) -> None:
    """Mesmo status é no-op em `_assert_transition` (não 409)."""
    campaign = _make_campaign(db_session, status="cancelled")
    result = cancel_campaign(db_session, campaign.id)
    assert result.status == "cancelled"
    db_session.refresh(campaign)
    assert campaign.status == "cancelled"


@pytest.mark.unit
def test_cancel_cancels_pending_jobs(db_session: Session) -> None:
    campaign = _make_campaign(db_session, status="active", messages_per_day=4, duration_days=1)
    _make_leads(db_session, campaign.id, 4)
    schedule_campaign(db_session, campaign.id, start_date=date(2026, 8, 1), rng=random.Random(7))

    pending_before = list(
        db_session.scalars(
            select(ScheduledJob).where(
                ScheduledJob.campaign_id == campaign.id,
                ScheduledJob.status == "pending",
            )
        ).all()
    )
    assert len(pending_before) == 4

    cancel_campaign(db_session, campaign.id)

    jobs = list(
        db_session.scalars(select(ScheduledJob).where(ScheduledJob.campaign_id == campaign.id)).all()
    )
    assert all(j.status == "cancelled" for j in jobs)
    db_session.refresh(campaign)
    assert campaign.status == "cancelled"
