"""E2e HTTP: login/challenge com adapter mockado via dependency injection no service."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from adapters.instagram import LoginResult
from database.models.account import Account
from services.accounts import service as account_service


@pytest.mark.e2e
def test_e2e_login_challenge_pending(client: TestClient, db_session: Session, monkeypatch) -> None:
    account = Account(
        username=f"e2e_{uuid.uuid4().hex[:6]}",
        status="offline",
        session_path="/tmp/e2e.session",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    class _ChallengeLogin:
        def login(self, username: str, password: str, **kwargs) -> LoginResult:
            _ = username, password, kwargs
            return LoginResult(
                success=False,
                challenge_pending=True,
                detail="challenge_required",
            )

    monkeypatch.setattr(
        account_service,
        "get_instagram_adapter",
        lambda *a, **k: _ChallengeLogin(),  # type: ignore[return-value]
    )

    response = client.post(
        f"/api/v1/accounts/{account.id}/login",
        json={"password": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "challenge"
    assert body["login_detail"] == "challenge_required"
    assert body["challenge_pending"] is True
    assert body["two_factor_pending"] is False


@pytest.mark.e2e
def test_e2e_login_two_factor_pending(client: TestClient, db_session: Session, monkeypatch) -> None:
    account = Account(
        username=f"e2e_{uuid.uuid4().hex[:6]}",
        status="offline",
        session_path="/tmp/e2e.session",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    class _TwoFactorLogin:
        def login(self, username: str, password: str, **kwargs) -> LoginResult:
            _ = username, password, kwargs
            return LoginResult(
                success=False,
                challenge_pending=True,
                two_factor_pending=True,
                detail="two_factor_required",
            )

    monkeypatch.setattr(
        account_service,
        "get_instagram_adapter",
        lambda *a, **k: _TwoFactorLogin(),  # type: ignore[return-value]
    )

    response = client.post(
        f"/api/v1/accounts/{account.id}/login",
        json={"password": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "challenge"
    assert body["login_detail"] == "two_factor_required"
    assert body["two_factor_pending"] is True
    assert body["challenge_pending"] is False


@pytest.mark.e2e
def test_e2e_resolve_challenge(client: TestClient, db_session: Session, monkeypatch) -> None:
    account = Account(
        username=f"e2e_{uuid.uuid4().hex[:6]}",
        status="challenge",
        session_path="/tmp/e2e.session",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    mock_adapter = MagicMock()
    mock_adapter.resolve_challenge.return_value = LoginResult(
        success=True,
        detail="challenge_resolved",
    )

    monkeypatch.setattr(
        account_service,
        "get_instagram_adapter",
        lambda *a, **k: mock_adapter,
    )

    response = client.post(
        f"/api/v1/accounts/{account.id}/challenge",
        json={"code": "654321", "choice": "sms"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["login_detail"] == "challenge_resolved"
    mock_adapter.resolve_challenge.assert_called_once_with("654321", choice="sms")
