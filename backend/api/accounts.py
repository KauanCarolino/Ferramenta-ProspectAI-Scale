"""Rotas de contas."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.account import (
    AccountAuthResponse,
    AccountChallengeRequest,
    AccountCreate,
    AccountLoginRequest,
    AccountRead,
    AccountUpdate,
    InboxPollResult,
)
from services import accounts as account_service
from services.accounts.service import AccountAuthOutcome

router = APIRouter()


def _to_auth_response(outcome: AccountAuthOutcome) -> AccountAuthResponse:
    base = AccountRead.model_validate(outcome.account).model_dump()
    return AccountAuthResponse(
        **base,
        login_detail=outcome.login_detail,
        challenge_pending=outcome.challenge_pending,
        two_factor_pending=outcome.two_factor_pending,
    )


@router.get("", response_model=list[AccountRead])
def list_accounts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AccountRead]:
    return account_service.list_accounts(db, skip=skip, limit=limit)  # type: ignore[return-value]


@router.post("", response_model=AccountRead, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> AccountRead:
    return account_service.create_account(db, payload)  # type: ignore[return-value]


@router.post("/inbox-poll", response_model=InboxPollResult)
def inbox_poll(
    account_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> InboxPollResult:
    """Rota estática antes de ``/{account_id}``."""
    result = account_service.process_inbox_replies(db, account_id=account_id)
    return InboxPollResult(**result)


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: uuid.UUID, db: Session = Depends(get_db)) -> AccountRead:
    return account_service.get_account(db, account_id)  # type: ignore[return-value]


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
) -> AccountRead:
    return account_service.update_account(db, account_id, payload)  # type: ignore[return-value]


@router.post("/{account_id}/login", response_model=AccountAuthResponse)
def login_account(
    account_id: uuid.UUID,
    payload: AccountLoginRequest,
    db: Session = Depends(get_db),
) -> AccountAuthResponse:
    """Login Instagram — senha/códigos só na chamada; nunca persistidos.

    Challenge sem código → ``status=challenge``, ``login_detail=challenge_required``.
    2FA → ``two_factor_pending=true``, ``login_detail=two_factor_required``.
    """
    outcome = account_service.login_account(
        db,
        account_id,
        payload.password,
        verification_code=payload.verification_code,
        challenge_code=payload.challenge_code,
        challenge_choice=payload.challenge_choice,
    )
    return _to_auth_response(outcome)


@router.post("/{account_id}/challenge", response_model=AccountAuthResponse)
def resolve_account_challenge(
    account_id: uuid.UUID,
    payload: AccountChallengeRequest,
    db: Session = Depends(get_db),
) -> AccountAuthResponse:
    """Resolve checkpoint ChallengeRequired com código email/SMS."""
    outcome = account_service.resolve_account_challenge(
        db,
        account_id,
        payload.code,
        choice=payload.choice,
    )
    return _to_auth_response(outcome)


@router.post("/{account_id}/refresh-status", response_model=AccountRead)
def refresh_account_status(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AccountRead:
    return account_service.refresh_account_status(db, account_id)  # type: ignore[return-value]
