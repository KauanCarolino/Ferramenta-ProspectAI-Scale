"""Testes do adapter Instagram (stub + InstagrapiAdapter com Client mockado)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.instagram import (
    AccountStatusInfo,
    InboxReply,
    InstagrapiAdapter,
    LoginResult,
    StubInstagramAdapter,
    get_instagram_adapter,
)
from database.models.account import Account
from database.models.campaign import Campaign
from database.models.lead import Lead
from database.models.reply import Reply
from database.models.scheduled_job import ScheduledJob
from services.accounts.service import login_account, process_inbox_replies, resolve_account_challenge


@pytest.mark.unit
def test_factory_defaults_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import get_settings

    monkeypatch.delenv("INSTAGRAM_ADAPTER", raising=False)
    get_settings.cache_clear()
    monkeypatch.setenv("INSTAGRAM_ADAPTER", "stub")
    get_settings.cache_clear()
    try:
        adapter = get_instagram_adapter(username="x")
        assert isinstance(adapter, StubInstagramAdapter)
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
def test_factory_instagrapi_when_configured() -> None:
    with patch("instagrapi.Client"):
        adapter = get_instagram_adapter(username="u", adapter="instagrapi")
    assert isinstance(adapter, InstagrapiAdapter)


@pytest.mark.unit
def test_stub_send_and_login() -> None:
    stub = StubInstagramAdapter(username="a")
    result = stub.login("a", "secret")
    assert isinstance(result, LoginResult)
    assert result.success is True
    assert stub.resolve_challenge("123456").success is True
    dm = stub.send_dm("lead", "oi")
    assert dm.success is True
    assert stub.check_inbox() == []
    assert stub.resolve_user_id("lead") == "stub-uid-lead"


@pytest.mark.unit
def test_instagrapi_login_success(tmp_path) -> None:
    client = MagicMock()
    session = tmp_path / "user.session"
    adapter = InstagrapiAdapter(
        username="user",
        session_path=str(session),
        client=client,
    )
    result = adapter.login("user", "pw")
    assert result.success is True
    assert result.challenge_pending is False
    client.login.assert_called_once_with("user", "pw")
    client.dump_settings.assert_called()
    assert adapter.get_account_status().session_valid is True
    assert adapter.get_account_status().challenge_pending is False
    # Handlers nunca são o default interativo de stdin
    assert callable(client.challenge_code_handler)
    assert client.challenge_code_handler("user", None) == ""
    assert client.handle_exception is not None


@pytest.mark.unit
def test_instagrapi_login_challenge_persists_sidecar(tmp_path) -> None:
    from instagrapi.exceptions import ChallengeRequired

    challenge_json = {
        "message": "challenge_required",
        "challenge": {"api_path": "/challenge/1/abc/", "native_flow": False},
    }
    client = MagicMock()
    client.login.side_effect = ChallengeRequired({"message": "challenge_required"})
    client.last_json = challenge_json
    session = tmp_path / "u.session"
    adapter = InstagrapiAdapter(
        username="user",
        session_path=str(session),
        client=client,
    )
    result = adapter.login("user", "pw")
    assert result.success is False
    assert result.challenge_pending is True
    assert result.two_factor_pending is False
    assert result.detail == "challenge_required"
    status = adapter.get_account_status()
    assert status.challenge_pending is True
    assert status.session_valid is False
    sidecar = Path(f"{session}.challenge.json")
    assert sidecar.is_file()
    assert json.loads(sidecar.read_text(encoding="utf-8"))["message"] == "challenge_required"
    client.dump_settings.assert_called()
    # Não deve ter chamado challenge_resolve sem código
    client.challenge_resolve.assert_not_called()


@pytest.mark.unit
def test_instagrapi_resolve_challenge_success(tmp_path) -> None:
    challenge_json = {
        "message": "challenge_required",
        "challenge": {"api_path": "/challenge/1/abc/"},
    }
    session = tmp_path / "u.session"
    session.write_text("{}", encoding="utf-8")
    sidecar = Path(f"{session}.challenge.json")
    sidecar.write_text(json.dumps(challenge_json), encoding="utf-8")

    client = MagicMock()
    client.challenge_resolve.return_value = True
    adapter = InstagrapiAdapter(username="user", session_path=str(session), client=client)
    adapter._challenge_pending = True

    result = adapter.resolve_challenge("123456", choice="email")
    assert result.success is True
    assert result.challenge_pending is False
    client.load_settings.assert_called()
    client.challenge_resolve.assert_called_once_with(challenge_json)
    assert not sidecar.is_file()
    assert adapter.get_account_status().session_valid is True
    # Handler devolve o código (sem stdin)
    assert client.challenge_code_handler("user", 1) == "123456"


@pytest.mark.unit
def test_instagrapi_challenge_choice_sms_on_select_verify_method() -> None:
    """``choice=sms`` envia ChallengeChoice.SMS em select_verify_method."""
    from instagrapi.mixins.challenge import ChallengeChoice

    client = MagicMock()
    adapter = InstagrapiAdapter(username="user", session_path=None, client=client)
    adapter._active_challenge_choice = "sms"
    client.last_json = {
        "step_name": "select_verify_method",
        "step_data": {"email": "x@y.com", "phone_number": "+1 555"},
    }
    client.challenge_code_or_raised.return_value = "123456"

    def _fake_send(url: str, data: dict) -> None:
        if "security_code" in data:
            client.last_json = {
                "step_name": "select_verify_method",
                "step_data": {"email": "x@y.com", "phone_number": "+1 555"},
                "action": "close",
                "status": "ok",
            }

    client._send_private_request.side_effect = _fake_send

    assert adapter._challenge_choice_resolver_installed is True
    assert client.challenge_resolve_simple("/challenge/1/abc/") is True
    client._send_private_request.assert_any_call(
        "challenge/1/abc/",
        {"choice": str(ChallengeChoice.SMS.value)},
    )
    client.challenge_code_or_raised.assert_called_once_with(
        ChallengeChoice.SMS,
        wait_seconds=5,
        attempts=24,
    )


@pytest.mark.unit
def test_instagrapi_login_with_challenge_code_resolves(tmp_path) -> None:
    from instagrapi.exceptions import ChallengeRequired

    challenge_json = {
        "message": "challenge_required",
        "challenge": {"api_path": "/challenge/1/abc/"},
    }
    client = MagicMock()
    client.login.side_effect = ChallengeRequired({"message": "challenge_required"})
    client.last_json = challenge_json
    client.challenge_resolve.return_value = True
    session = tmp_path / "u.session"
    adapter = InstagrapiAdapter(username="user", session_path=str(session), client=client)

    result = adapter.login("user", "pw", challenge_code="654321", challenge_choice="sms")
    assert result.success is True
    client.challenge_resolve.assert_called_once()
    assert adapter.get_account_status().session_valid is True


@pytest.mark.unit
def test_instagrapi_login_two_factor_pending(tmp_path) -> None:
    from instagrapi.exceptions import TwoFactorRequired

    client = MagicMock()
    client.login.side_effect = TwoFactorRequired({"message": "two_factor_required"})
    session = tmp_path / "u.session"
    adapter = InstagrapiAdapter(username="user", session_path=str(session), client=client)

    result = adapter.login("user", "pw")
    assert result.success is False
    assert result.two_factor_pending is True
    assert result.challenge_pending is True
    assert result.detail == "two_factor_required"
    status = adapter.get_account_status()
    assert status.two_factor_pending is True
    assert status.detail == "two_factor_required"


@pytest.mark.unit
def test_instagrapi_login_passes_verification_code(tmp_path) -> None:
    client = MagicMock()
    session = tmp_path / "u.session"
    adapter = InstagrapiAdapter(username="user", session_path=str(session), client=client)
    result = adapter.login("user", "pw", verification_code="111222")
    assert result.success is True
    client.login.assert_called_once_with("user", "pw", verification_code="111222")


@pytest.mark.unit
def test_instagrapi_send_dm_success(tmp_path) -> None:
    client = MagicMock()
    client.user_id_from_username.return_value = 12345
    client.direct_send.return_value = SimpleNamespace(id="msg-1")
    session = tmp_path / "u.session"
    session.write_text("{}")
    adapter = InstagrapiAdapter(username="me", session_path=str(session), client=client)
    result = adapter.send_dm("lead", "hello")
    assert result.success is True
    assert result.message_id == "msg-1"
    client.direct_send.assert_called_once()


@pytest.mark.unit
def test_instagrapi_send_dm_blocked(tmp_path) -> None:
    from instagrapi.exceptions import FeedbackRequired

    client = MagicMock()
    client.user_id_from_username.return_value = 1
    client.direct_send.side_effect = FeedbackRequired({"message": "feedback_required"})
    session = tmp_path / "u.session"
    session.write_text("{}")
    adapter = InstagrapiAdapter(username="me", session_path=str(session), client=client)
    result = adapter.send_dm("lead", "hello")
    assert result.success is False
    assert result.blocked is True


@pytest.mark.unit
def test_instagrapi_send_dm_challenge(tmp_path) -> None:
    from instagrapi.exceptions import ChallengeRequired

    client = MagicMock()
    client.user_id_from_username.return_value = 1
    client.direct_send.side_effect = ChallengeRequired({"message": "challenge"})
    session = tmp_path / "u.session"
    session.write_text("{}")
    adapter = InstagrapiAdapter(username="me", session_path=str(session), client=client)
    result = adapter.send_dm("lead", "hello")
    assert result.challenge is True
    assert result.success is False


@pytest.mark.unit
def test_instagrapi_check_inbox_mapping(tmp_path) -> None:
    client = MagicMock()
    client.user_id = 99
    peer = SimpleNamespace(pk=42, username="LeadUser")
    own = SimpleNamespace(pk=99, username="me")
    msg_peer = SimpleNamespace(id="m2", user_id=42, text="Oi de volta")
    msg_own = SimpleNamespace(id="m1", user_id=99, text="nosso envio")
    thread = SimpleNamespace(id="t1", users=[peer, own], messages=[msg_own, msg_peer])
    client.direct_threads.return_value = [thread]

    session = tmp_path / "u.session"
    session.write_text("{}")
    adapter = InstagrapiAdapter(username="me", session_path=str(session), client=client)
    replies = adapter.check_inbox()
    assert len(replies) == 1
    assert replies[0].username == "leaduser"
    assert replies[0].text == "Oi de volta"
    assert replies[0].thread_id == "t1"


@pytest.mark.unit
def test_stub_list_followers_returns_amount() -> None:
    adapter = StubInstagramAdapter(username="me")
    followers = adapter.list_followers(amount=3)
    assert len(followers) == 3
    assert followers[0].username == "stub_follower_1"
    assert followers[0].full_name


@pytest.mark.unit
def test_instagrapi_list_followers_maps_users(tmp_path) -> None:
    client = MagicMock()
    client.user_id = 99
    follower_a = SimpleNamespace(pk=1, username="Alice", full_name="Alice A")
    follower_b = SimpleNamespace(pk=2, username="bob_b", full_name="")
    client.user_followers.return_value = {1: follower_a, 2: follower_b}

    session = tmp_path / "u.session"
    session.write_text("{}")
    adapter = InstagrapiAdapter(username="me", session_path=str(session), client=client)
    followers = adapter.list_followers(amount=50)

    assert len(followers) == 2
    assert followers[0].username == "alice"
    assert followers[0].full_name == "Alice A"
    assert followers[1].username == "bob_b"
    assert followers[1].full_name is None
    client.user_followers.assert_called_once_with(99, amount=50)


@pytest.mark.unit
def test_instagrapi_list_followers_challenge_returns_empty(tmp_path) -> None:
    from instagrapi.exceptions import ChallengeRequired

    client = MagicMock()
    client.user_id = 99
    client.user_followers.side_effect = ChallengeRequired({"message": "challenge"})
    session = tmp_path / "u.session"
    session.write_text("{}")
    adapter = InstagrapiAdapter(username="me", session_path=str(session), client=client)
    followers = adapter.list_followers()
    assert followers == []


@pytest.mark.unit
def test_login_account_updates_status(db_session: Session) -> None:
    account = Account(
        username=f"acc_{uuid.uuid4().hex[:6]}",
        status="offline",
        session_path="/tmp/fake.session",
    )
    db_session.add(account)
    db_session.commit()

    class _LoginOk:
        def login(self, username: str, password: str, **kwargs) -> LoginResult:
            _ = username, password, kwargs
            return LoginResult(success=True)

        def get_account_status(self) -> AccountStatusInfo:
            return AccountStatusInfo(username="x", session_valid=True, challenge_pending=False)

    outcome = login_account(
        db_session,
        account.id,
        "secret",
        adapter_factory=lambda *a, **k: _LoginOk(),  # type: ignore[return-value]
    )
    assert outcome.account.status == "active"


@pytest.mark.unit
def test_login_account_challenge_status(db_session: Session) -> None:
    account = Account(
        username=f"acc_{uuid.uuid4().hex[:6]}",
        status="offline",
        session_path="/tmp/fake.session",
    )
    db_session.add(account)
    db_session.commit()

    class _LoginChallenge:
        def login(self, username: str, password: str, **kwargs) -> LoginResult:
            _ = username, password, kwargs
            return LoginResult(success=False, challenge_pending=True, detail="challenge_required")

    outcome = login_account(
        db_session,
        account.id,
        "secret",
        adapter_factory=lambda *a, **k: _LoginChallenge(),  # type: ignore[return-value]
    )
    assert outcome.account.status == "challenge"
    assert outcome.challenge_pending is True
    assert outcome.two_factor_pending is False
    assert outcome.login_detail == "challenge_required"


@pytest.mark.unit
def test_login_account_two_factor_status(db_session: Session) -> None:
    account = Account(
        username=f"acc_{uuid.uuid4().hex[:6]}",
        status="offline",
        session_path="/tmp/fake.session",
    )
    db_session.add(account)
    db_session.commit()

    class _Login2FA:
        def login(self, username: str, password: str, **kwargs) -> LoginResult:
            _ = username, password, kwargs
            return LoginResult(
                success=False,
                challenge_pending=True,
                two_factor_pending=True,
                detail="two_factor_required",
            )

    outcome = login_account(
        db_session,
        account.id,
        "secret",
        adapter_factory=lambda *a, **k: _Login2FA(),  # type: ignore[return-value]
    )
    assert outcome.account.status == "challenge"
    assert outcome.two_factor_pending is True
    assert outcome.challenge_pending is False
    assert outcome.login_detail == "two_factor_required"


@pytest.mark.unit
def test_resolve_account_challenge_service(db_session: Session) -> None:
    account = Account(
        username=f"acc_{uuid.uuid4().hex[:6]}",
        status="challenge",
        session_path="/tmp/fake.session",
    )
    db_session.add(account)
    db_session.commit()

    class _ResolveOk:
        def resolve_challenge(self, code: str, *, choice: str = "email") -> LoginResult:
            _ = code, choice
            return LoginResult(success=True, detail="challenge_resolved")

    outcome = resolve_account_challenge(
        db_session,
        account.id,
        "999000",
        choice="sms",
        adapter_factory=lambda *a, **k: _ResolveOk(),  # type: ignore[return-value]
    )
    assert outcome.account.status == "active"
    assert outcome.login_detail == "challenge_resolved"


@pytest.mark.unit
def test_process_inbox_replies_marks_lead(db_session: Session) -> None:
    campaign = Campaign(name=f"c-{uuid.uuid4().hex[:6]}", status="active", channel="instagram")
    account = Account(
        username=f"acc_{uuid.uuid4().hex[:6]}",
        status="active",
        session_path="/tmp/x.session",
    )
    db_session.add_all([campaign, account])
    db_session.flush()

    lead = Lead(
        campaign_id=campaign.id,
        nome="Ana",
        empresa="X",
        cargo="Dev",
        instagram="ana_lead",
        status="aguardando_d4",
    )
    db_session.add(lead)
    db_session.flush()

    job = ScheduledJob(
        campaign_id=campaign.id,
        lead_id=lead.id,
        account_id=account.id,
        stage="d4",
        status="pending",
        channel="instagram",
        scheduled_at=datetime(2026, 8, 10),
    )
    db_session.add(job)
    db_session.commit()

    class _InboxAdapter:
        def check_inbox(self, *, since_id: str | None = None) -> list[InboxReply]:
            return [
                InboxReply(
                    thread_id="th1",
                    username="ana_lead",
                    text="Interessada!",
                    message_id="m9",
                )
            ]

        def get_account_status(self) -> AccountStatusInfo:
            return AccountStatusInfo(
                username=account.username,
                session_valid=True,
                challenge_pending=False,
            )

    result = process_inbox_replies(
        db_session,
        account_id=account.id,
        adapter_factory=lambda *a, **k: _InboxAdapter(),  # type: ignore[return-value]
    )
    assert result["leads_matched"] == 1
    assert result["replies_seen"] == 1
    db_session.refresh(lead)
    assert lead.status == "respondido"
    db_session.refresh(job)
    assert job.status == "cancelled"
    replies = list(db_session.scalars(select(Reply)).all())
    assert len(replies) == 1
    assert replies[0].content == "Interessada!"
