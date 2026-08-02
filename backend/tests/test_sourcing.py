"""Testes do sourcing de leads via seguidores do Instagram (sem CSV)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from adapters.instagram import FollowerInfo
from database.models.account import Account
from database.models.campaign import Campaign
from database.models.lead import Lead
from services.sourcing.service import pull_and_confirm_followers, pull_followers_preview


def _make_campaign(db: Session) -> Campaign:
    campaign = Campaign(name="Campanha seguidores")
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _make_account(db: Session) -> Account:
    account = Account(username="minha_conta", status="active")
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _patch_adapter(monkeypatch: pytest.MonkeyPatch, followers: list[FollowerInfo]) -> MagicMock:
    fake_adapter = MagicMock()
    fake_adapter.list_followers.return_value = followers
    monkeypatch.setattr(
        "services.sourcing.service.get_instagram_adapter",
        lambda *a, **k: fake_adapter,
    )
    return fake_adapter


@pytest.mark.unit
def test_pull_followers_preview_maps_and_dedupes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _make_campaign(db_session)
    account = _make_account(db_session)
    followers = [
        FollowerInfo(username="Alice", full_name="Alice A", user_id="1"),
        FollowerInfo(username="alice", full_name="Duplicada no lote", user_id="1"),
        FollowerInfo(username="bob_b", full_name=None, user_id="2"),
    ]
    _patch_adapter(monkeypatch, followers)

    preview = pull_followers_preview(
        db_session, campaign_id=campaign.id, account_id=account.id, amount=150
    )

    assert preview.total_rows == 3
    assert preview.valid_count == 2
    assert preview.duplicate_count == 1
    usernames = {row.instagram for row in preview.preview}
    assert usernames == {"alice", "bob_b"}
    bob_row = next(row for row in preview.preview if row.instagram == "bob_b")
    assert bob_row.nome == "@bob_b"
    assert bob_row.empresa == "-"
    assert bob_row.cargo == "Seguidor"


@pytest.mark.unit
def test_pull_followers_preview_respects_amount(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _make_campaign(db_session)
    account = _make_account(db_session)
    followers = [FollowerInfo(username=f"user_{i}") for i in range(10)]
    _patch_adapter(monkeypatch, followers)

    preview = pull_followers_preview(
        db_session, campaign_id=campaign.id, account_id=account.id, amount=3
    )

    assert preview.valid_count == 3


@pytest.mark.unit
def test_pull_followers_preview_skips_leads_already_in_campaign(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _make_campaign(db_session)
    account = _make_account(db_session)
    db_session.add(
        Lead(
            campaign_id=campaign.id,
            nome="Já existe",
            empresa="-",
            cargo="Seguidor",
            instagram="alice",
        )
    )
    db_session.commit()
    followers = [FollowerInfo(username="alice"), FollowerInfo(username="bob_b")]
    _patch_adapter(monkeypatch, followers)

    preview = pull_followers_preview(
        db_session, campaign_id=campaign.id, account_id=account.id, amount=150
    )

    assert preview.valid_count == 1
    assert preview.preview[0].instagram == "bob_b"
    assert preview.duplicate_count == 1


@pytest.mark.unit
def test_pull_and_confirm_followers_persists_leads(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _make_campaign(db_session)
    account = _make_account(db_session)
    followers = [FollowerInfo(username="alice"), FollowerInfo(username="bob_b")]
    _patch_adapter(monkeypatch, followers)

    result = pull_and_confirm_followers(
        db_session, campaign_id=campaign.id, account_id=account.id, amount=150
    )

    assert result.inserted == 2
    assert result.skipped_duplicates == 0
    leads = db_session.query(Lead).filter(Lead.campaign_id == campaign.id).all()
    assert {lead.instagram for lead in leads} == {"alice", "bob_b"}


@pytest.mark.unit
def test_pull_followers_preview_unknown_account_raises_404(
    db_session: Session,
) -> None:
    from fastapi import HTTPException

    campaign = _make_campaign(db_session)
    with pytest.raises(HTTPException) as exc_info:
        pull_followers_preview(
            db_session,
            campaign_id=campaign.id,
            account_id=campaign.id,  # id qualquer que não existe em accounts
            amount=150,
        )
    assert exc_info.value.status_code == 404
