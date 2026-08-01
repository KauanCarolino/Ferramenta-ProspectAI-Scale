"""Schemas de conta."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.common import ORMModel

ChallengeChoiceLiteral = Literal["email", "sms"]


class AccountCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    proxy: str | None = Field(default=None, max_length=512)
    notes: str | None = None
    # Senha aceita no fluxo de create CLI/API; nunca armazenada em texto puro.
    password: str | None = Field(default=None, exclude=True)


class AccountUpdate(BaseModel):
    status: str | None = None
    proxy: str | None = Field(default=None, max_length=512)
    warmup_day: int | None = Field(default=None, ge=0, le=30)
    notes: str | None = None
    session_path: str | None = None


class AccountLoginRequest(BaseModel):
    """Body de login — senha/códigos usados só na chamada; nunca persistidos.

    Em ChallengeRequired sem ``challenge_code``, a conta fica ``status=challenge``.
    Em TwoFactorRequired, mesma status com detail ``two_factor_required``
    (reenviar login com ``verification_code``).
    """

    password: str = Field(..., min_length=1)
    verification_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Código 2FA (TOTP/SMS) quando TwoFactorRequired",
    )
    challenge_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Código do checkpoint email/SMS",
    )
    challenge_choice: ChallengeChoiceLiteral = Field(
        default="email",
        description="Canal preferido para o checkpoint: email ou sms",
    )


class AccountChallengeRequest(BaseModel):
    """Body para resolver checkpoint após ChallengeRequired."""

    code: str = Field(..., min_length=1, max_length=32)
    choice: ChallengeChoiceLiteral = Field(default="email")


class AccountRead(ORMModel):
    id: uuid.UUID
    username: str
    status: str
    proxy: str | None
    warmup_day: int
    session_path: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AccountAuthResponse(AccountRead):
    """Resposta enriquecida de login/challenge (campos extras não vêm do ORM)."""

    login_detail: str | None = Field(
        default=None,
        description=(
            "Detalhe do fluxo: challenge_required, two_factor_required, "
            "login_ok, challenge_resolved, etc."
        ),
    )
    challenge_pending: bool = Field(
        default=False,
        description="Checkpoint email/SMS pendente — use POST /{id}/challenge",
    )
    two_factor_pending: bool = Field(
        default=False,
        description="2FA pendente — reenvie login com verification_code",
    )


class InboxPollResult(BaseModel):
    accounts_polled: int = 0
    replies_seen: int = 0
    leads_matched: int = 0
    errors: int = 0
