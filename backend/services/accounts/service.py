"""Gestão de contas Instagram (CRUD, login, refresh, inbox poll)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.instagram import InstagramAdapter, get_instagram_adapter
from config import get_settings
from database.models.account import Account
from database.models.lead import Lead
from database.models.reply import Reply
from schemas.account import AccountCreate, AccountUpdate
from services.logging.service import write_log
from services.scheduler.service import cancel_lead_pending
from utils.instagram import normalize_instagram_handle

logger = logging.getLogger(__name__)

AdapterFactory = Callable[..., InstagramAdapter]


@dataclass
class AccountAuthOutcome:
    """Conta + metadados do último login/challenge (não persistidos no ORM)."""

    account: Account
    login_detail: str | None = None
    challenge_pending: bool = False
    two_factor_pending: bool = False


def list_accounts(db: Session, *, skip: int = 0, limit: int = 50) -> list[Account]:
    stmt = select(Account).order_by(Account.username).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_account(db: Session, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")
    return account


def create_account(db: Session, data: AccountCreate) -> Account:
    existing = db.scalar(select(Account).where(Account.username == data.username))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conta '{data.username}' já cadastrada",
        )
    settings = get_settings()
    sessions_dir = Path(settings.sessions_dir)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_path = str(sessions_dir / f"{data.username}.session")

    # Senha intencionalmente NÃO é persistida.
    account = Account(
        username=data.username,
        proxy=data.proxy,
        notes=data.notes,
        status="offline",
        warmup_day=0,
        session_path=session_path,
        session_encrypted=None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info("Conta criada username=%s (senha descartada)", data.username)
    return account


def update_account(db: Session, account_id: uuid.UUID, data: AccountUpdate) -> Account:
    account = get_account(db, account_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account


def _build_adapter(
    account: Account,
    *,
    adapter_factory: AdapterFactory | None = None,
) -> InstagramAdapter:
    factory = adapter_factory or get_instagram_adapter
    return factory(
        account.username,
        session_path=account.session_path,
        proxy=account.proxy,
    )


def login_account(
    db: Session,
    account_id: uuid.UUID,
    password: str,
    *,
    verification_code: str | None = None,
    challenge_code: str | None = None,
    challenge_choice: str = "email",
    adapter_factory: AdapterFactory | None = None,
) -> AccountAuthOutcome:
    """Autentica via adapter, atualiza status/session_path.

    Senha e códigos nunca são persistidos. Em challenge/2FA a conta fica
    ``status=challenge``; ``login_detail`` distingue checkpoint vs 2FA.
    """
    account = get_account(db, account_id)
    adapter = _build_adapter(account, adapter_factory=adapter_factory)

    try:
        result = adapter.login(
            account.username,
            password,
            proxy=account.proxy,
            verification_code=verification_code,
            challenge_code=challenge_code,
            challenge_choice=challenge_choice,  # type: ignore[arg-type]
        )
    except Exception as exc:
        account.status = "offline"
        write_log(
            db,
            action="login",
            result="failed",
            account_id=account.id,
            instagram_handle=account.username,
            error=f"{type(exc).__name__}",
            commit=False,
        )
        db.commit()
        db.refresh(account)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Login falhou: {type(exc).__name__}",
        ) from exc

    detail = result.detail
    if result.two_factor_pending:
        account.status = "challenge"
        log_result = "challenge"
        detail = detail or "two_factor_required"
    elif result.challenge_pending:
        account.status = "challenge"
        log_result = "challenge"
    elif result.success:
        account.status = "active"
        log_result = "success"
        if account.session_path is None:
            settings = get_settings()
            account.session_path = str(Path(settings.sessions_dir) / f"{account.username}.session")
    else:
        account.status = "offline"
        log_result = "failed"

    write_log(
        db,
        action="login",
        result=log_result,
        account_id=account.id,
        instagram_handle=account.username,
        error=None if log_result == "success" else detail,
        commit=False,
    )
    db.commit()
    db.refresh(account)
    logger.info("login_account @%s → status=%s", account.username, account.status)
    return AccountAuthOutcome(
        account=account,
        login_detail=detail,
        challenge_pending=result.challenge_pending and not result.two_factor_pending,
        two_factor_pending=result.two_factor_pending,
    )


def resolve_account_challenge(
    db: Session,
    account_id: uuid.UUID,
    code: str,
    *,
    choice: str = "email",
    adapter_factory: AdapterFactory | None = None,
) -> AccountAuthOutcome:
    """Resolve checkpoint Instagram com código email/SMS (nunca persistido)."""
    account = get_account(db, account_id)
    adapter = _build_adapter(account, adapter_factory=adapter_factory)

    try:
        result = adapter.resolve_challenge(code, choice=choice)  # type: ignore[arg-type]
    except Exception as exc:
        write_log(
            db,
            action="challenge_resolve",
            result="failed",
            account_id=account.id,
            instagram_handle=account.username,
            error=f"{type(exc).__name__}",
            commit=False,
        )
        db.commit()
        db.refresh(account)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Challenge resolve falhou: {type(exc).__name__}",
        ) from exc

    if result.success:
        account.status = "active"
        log_result = "success"
        error = None
    else:
        account.status = "challenge"
        log_result = "challenge"
        error = result.detail

    write_log(
        db,
        action="challenge_resolve",
        result=log_result,
        account_id=account.id,
        instagram_handle=account.username,
        error=error,
        commit=False,
    )
    db.commit()
    db.refresh(account)
    logger.info(
        "resolve_account_challenge @%s → status=%s",
        account.username,
        account.status,
    )
    return AccountAuthOutcome(
        account=account,
        login_detail=result.detail if not result.success else "challenge_resolved",
        challenge_pending=not result.success and result.challenge_pending,
        two_factor_pending=result.two_factor_pending,
    )


def refresh_account_status(
    db: Session,
    account_id: uuid.UUID,
    *,
    adapter_factory: AdapterFactory | None = None,
) -> Account:
    """Consulta adapter.get_account_status e atualiza o status da conta."""
    account = get_account(db, account_id)
    adapter = _build_adapter(account, adapter_factory=adapter_factory)
    info = adapter.get_account_status()

    if info.challenge_pending:
        account.status = "challenge"
    elif info.session_valid:
        if account.status in {"offline", "challenge"}:
            account.status = "active"
    else:
        if account.status == "active":
            account.status = "offline"

    write_log(
        db,
        action="refresh_status",
        result="success" if info.session_valid else info.detail or "invalid",
        account_id=account.id,
        instagram_handle=account.username,
        details=info.detail,
        commit=False,
    )
    db.commit()
    db.refresh(account)
    return account


def process_inbox_replies(
    db: Session,
    account_id: uuid.UUID | None = None,
    *,
    adapter_factory: AdapterFactory | None = None,
    since_id: str | None = None,
) -> dict[str, int]:
    """Poll inbox das contas, marca leads respondidos e cancela jobs/follow-ups."""
    if account_id is not None:
        accounts = [get_account(db, account_id)]
    else:
        accounts = list(
            db.scalars(
                select(Account).where(Account.status.in_(("active", "warming"))).order_by(Account.username)
            ).all()
        )

    accounts_polled = 0
    replies_seen = 0
    leads_matched = 0
    errors = 0

    for account in accounts:
        accounts_polled += 1
        adapter = _build_adapter(account, adapter_factory=adapter_factory)
        try:
            inbox = adapter.check_inbox(since_id=since_id)
        except Exception:
            logger.exception("inbox poll falhou para @%s", account.username)
            errors += 1
            write_log(
                db,
                action="reply_detected",
                result="failed",
                account_id=account.id,
                instagram_handle=account.username,
                error="inbox_poll_error",
                commit=False,
            )
            continue

        info = adapter.get_account_status()
        if info.challenge_pending and account.status != "challenge":
            account.status = "challenge"

        replies_seen += len(inbox)
        for reply in inbox:
            handle = normalize_instagram_handle(reply.username)
            if not handle:
                continue

            leads = list(
                db.scalars(
                    select(Lead).where(
                        Lead.instagram == handle,
                        Lead.status != "respondido",
                    )
                ).all()
            )
            for lead in leads:
                lead.status = "respondido"
                cancel_lead_pending(db, lead.id, commit=False)
                db.add(
                    Reply(
                        campaign_id=lead.campaign_id,
                        lead_id=lead.id,
                        account_id=account.id,
                        content=reply.text,
                        instagram_thread_id=reply.thread_id or None,
                    )
                )
                write_log(
                    db,
                    action="reply_detected",
                    result="success",
                    campaign_id=lead.campaign_id,
                    lead_id=lead.id,
                    account_id=account.id,
                    instagram_handle=handle,
                    details=reply.message_id,
                    commit=False,
                )
                leads_matched += 1

    db.commit()
    return {
        "accounts_polled": accounts_polled,
        "replies_seen": replies_seen,
        "leads_matched": leads_matched,
        "errors": errors,
    }
