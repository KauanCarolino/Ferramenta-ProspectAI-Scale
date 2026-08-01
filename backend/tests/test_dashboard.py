"""Testes do resumo do dashboard (status_campanha / auto_paused)."""

from __future__ import annotations

import uuid
from datetime import time

import pytest
from sqlalchemy.orm import Session

from database.models.campaign import Campaign
from services.dashboard import get_dashboard_summary


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


@pytest.mark.unit
def test_summary_without_campaign_id_surfaces_auto_paused(db_session: Session) -> None:
    _make_campaign(db_session, status="active")
    _make_campaign(db_session, status="auto_paused")

    summary = get_dashboard_summary(db_session, campaign_id=None)

    assert summary.status_campanha == "auto_paused"
    assert summary.campaign_id is None


@pytest.mark.unit
def test_summary_without_campaign_id_null_when_no_auto_paused(db_session: Session) -> None:
    _make_campaign(db_session, status="active")
    _make_campaign(db_session, status="paused")

    summary = get_dashboard_summary(db_session, campaign_id=None)

    assert summary.status_campanha is None


@pytest.mark.unit
def test_summary_with_campaign_id_uses_that_campaign_status(db_session: Session) -> None:
    active = _make_campaign(db_session, status="active")
    _make_campaign(db_session, status="auto_paused")

    summary = get_dashboard_summary(db_session, campaign_id=active.id)

    assert summary.status_campanha == "active"
    assert summary.campaign_id == active.id
