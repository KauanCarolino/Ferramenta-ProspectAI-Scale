"""Sourcing de leads via seguidores da própria conta Instagram (sem CSV)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.instagram import get_instagram_adapter
from database.models.account import Account
from database.models.lead import Lead
from schemas.importer import ImportConfirmResponse, ImportPreviewResponse, ImportPreviewRow
from services.importer.service import confirm_import
from utils.instagram import normalize_instagram_handle

logger = logging.getLogger(__name__)

DEFAULT_EMPRESA = "-"
DEFAULT_CARGO = "Seguidor"


def _get_account(db: Session, account_id: uuid.UUID) -> Account:
    from fastapi import HTTPException, status

    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")
    return account


def pull_followers_preview(
    db: Session,
    *,
    campaign_id: uuid.UUID,
    account_id: uuid.UUID,
    amount: int = 150,
) -> ImportPreviewResponse:
    """Busca seguidores da conta via adapter e monta um preview deduplicado (sem gravar)."""
    account = _get_account(db, account_id)
    adapter = get_instagram_adapter(
        account.username,
        session_path=account.session_path,
        proxy=account.proxy,
    )

    followers = adapter.list_followers(amount=amount)

    existing = {
        row[0]
        for row in db.execute(
            select(Lead.instagram).where(Lead.campaign_id == campaign_id)
        ).all()
    }

    seen: set[str] = set()
    preview: list[ImportPreviewRow] = []
    duplicate_count = 0
    for idx, follower in enumerate(followers):
        if len(preview) >= amount:
            break
        handle = normalize_instagram_handle(follower.username)
        if not handle:
            continue
        if handle in seen or handle in existing:
            duplicate_count += 1
            continue
        seen.add(handle)
        preview.append(
            ImportPreviewRow(
                row_number=idx + 1,
                nome=follower.full_name or f"@{handle}",
                empresa=DEFAULT_EMPRESA,
                cargo=DEFAULT_CARGO,
                instagram=handle,
                cidade=None,
                observacoes="Importado via seguidores da conta",
            )
        )

    return ImportPreviewResponse(
        campaign_id=campaign_id,
        total_rows=len(followers),
        valid_count=len(preview),
        rejected_count=0,
        duplicate_count=duplicate_count,
        preview=preview,
        rejected=[],
    )


def pull_and_confirm_followers(
    db: Session,
    *,
    campaign_id: uuid.UUID,
    account_id: uuid.UUID,
    amount: int = 150,
) -> ImportConfirmResponse:
    """Puxa seguidores e já persiste os leads válidos — sem passo manual de revisão."""
    preview = pull_followers_preview(db, campaign_id=campaign_id, account_id=account_id, amount=amount)
    result = confirm_import(db, campaign_id=campaign_id, preview=preview)
    logger.info(
        "Sourcing por seguidores campaign=%s account=%s inseridos=%s ignorados=%s",
        campaign_id,
        account_id,
        result.inserted,
        result.skipped_duplicates,
    )
    return result
