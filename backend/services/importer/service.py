"""Importador de leads CSV/XLSX — validar, normalizar, deduplicar."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.lead import Lead
from schemas.importer import (
    ImportConfirmLead,
    ImportConfirmResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportRejectedRow,
)
from utils.instagram import normalize_instagram_handle

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("nome", "empresa", "cargo", "instagram")
OPTIONAL_COLUMNS = ("cidade", "observacoes")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

# Aliases de nome de coluna (minúsculas) → canônico
_COLUMN_ALIASES: dict[str, str] = {
    "nome": "nome",
    "name": "nome",
    "empresa": "empresa",
    "company": "empresa",
    "cargo": "cargo",
    "title": "cargo",
    "job_title": "cargo",
    "instagram": "instagram",
    "ig": "instagram",
    "handle": "instagram",
    "insta": "instagram",
    "cidade": "cidade",
    "city": "cidade",
    "observacoes": "observacoes",
    "observações": "observacoes",
    "notes": "observacoes",
    "obs": "observacoes",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in _COLUMN_ALIASES:
            mapping[col] = _COLUMN_ALIASES[key]
    return df.rename(columns=mapping)


def _cell_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def read_leads_dataframe(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Carrega CSV ou XLSX em um DataFrame."""
    name = (filename or "").lower()
    if isinstance(source, (str, Path)):
        path = Path(source)
        name = path.name.lower()
        if name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(path, engine="openpyxl")
        else:
            df = pd.read_csv(path)
    elif isinstance(source, bytes):
        buffer = io.BytesIO(source)
        if name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(buffer, engine="openpyxl")
        else:
            df = pd.read_csv(buffer)
    else:
        # BinaryIO / UploadFile.file (stream de upload)
        data = source.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        buffer = io.BytesIO(data)
        if name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(buffer, engine="openpyxl")
        else:
            df = pd.read_csv(buffer)
    return df


def preview_import(
    source: str | Path | BinaryIO | bytes,
    *,
    filename: str | None = None,
    campaign_id: UUID | None = None,
    existing_handles: set[str] | None = None,
) -> ImportPreviewResponse:
    """Valida linhas do arquivo, normaliza handles, deduplica — sem gravar no DB."""
    df = read_leads_dataframe(source, filename=filename)
    df = _normalize_columns(df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(missing)}")

    existing = set(existing_handles or [])
    seen_in_file: set[str] = set()
    preview: list[ImportPreviewRow] = []
    rejected: list[ImportRejectedRow] = []
    duplicate_count = 0

    for idx, row in df.iterrows():
        row_number = int(idx) + 2  # cabeçalho = linha 1
        raw = {col: _cell_str(row.get(col)) for col in ALL_COLUMNS if col in df.columns}
        reasons: list[str] = []

        nome = raw.get("nome")
        empresa = raw.get("empresa")
        cargo = raw.get("cargo")
        instagram_raw = raw.get("instagram")

        if not nome:
            reasons.append("nome obrigatório")
        if not empresa:
            reasons.append("empresa obrigatória")
        if not cargo:
            reasons.append("cargo obrigatório")
        if not instagram_raw:
            reasons.append("instagram obrigatório")

        handle = normalize_instagram_handle(instagram_raw) if instagram_raw else None
        if instagram_raw and not handle:
            reasons.append("handle Instagram inválido")

        is_dup = False
        if handle:
            if handle in seen_in_file:
                reasons.append("duplicado no arquivo")
                is_dup = True
            elif handle in existing:
                reasons.append("duplicado na campanha")
                is_dup = True

        if reasons:
            if is_dup:
                duplicate_count += 1
            rejected.append(ImportRejectedRow(row_number=row_number, raw=raw, reasons=reasons))
            continue

        assert handle is not None and nome and empresa and cargo
        seen_in_file.add(handle)
        preview.append(
            ImportPreviewRow(
                row_number=row_number,
                nome=nome,
                empresa=empresa,
                cargo=cargo,
                instagram=handle,
                cidade=raw.get("cidade"),
                observacoes=raw.get("observacoes"),
            )
        )

    return ImportPreviewResponse(
        campaign_id=campaign_id,
        total_rows=len(df),
        valid_count=len(preview),
        rejected_count=len(rejected),
        duplicate_count=duplicate_count,
        preview=preview,
        rejected=rejected,
    )


def preview_from_confirm_leads(
    campaign_id: UUID,
    leads: list[ImportConfirmLead],
) -> ImportPreviewResponse:
    """Monta um preview normalizado a partir dos leads do payload de confirmação.

    Levanta ValueError se algum handle for inválido após a normalização.
    """
    if not leads:
        raise ValueError("Lista de leads vazia — use preview + confirme com leads válidos")

    preview_rows: list[ImportPreviewRow] = []
    invalid: list[str] = []
    for i, lead in enumerate(leads):
        handle = normalize_instagram_handle(lead.instagram)
        if not handle:
            invalid.append(f"leads[{i}].instagram inválido: {lead.instagram!r}")
            continue
        preview_rows.append(
            ImportPreviewRow(
                row_number=i + 1,
                nome=lead.nome,
                empresa=lead.empresa,
                cargo=lead.cargo,
                instagram=handle,
                cidade=lead.cidade,
                observacoes=lead.observacoes,
            )
        )

    if invalid:
        raise ValueError("; ".join(invalid))

    return ImportPreviewResponse(
        campaign_id=campaign_id,
        total_rows=len(leads),
        valid_count=len(preview_rows),
        rejected_count=0,
        duplicate_count=0,
        preview=preview_rows,
        rejected=[],
    )


def confirm_import(
    db: Session,
    *,
    campaign_id: UUID,
    preview: ImportPreviewResponse | None = None,
    source: str | Path | BinaryIO | bytes | None = None,
    filename: str | None = None,
) -> ImportConfirmResponse:
    """Persiste leads válidos a partir de um preview ou reparseando o arquivo fonte."""
    existing = {
        row[0]
        for row in db.execute(
            select(Lead.instagram).where(Lead.campaign_id == campaign_id)
        ).all()
    }

    if preview is None:
        if source is None:
            raise ValueError("Informe preview ou source para confirmar importação")
        preview = preview_import(
            source,
            filename=filename,
            campaign_id=campaign_id,
            existing_handles=existing,
        )

    inserted = 0
    skipped = 0
    invalid: list[str] = []
    for item in preview.preview:
        handle = normalize_instagram_handle(item.instagram)
        if not handle:
            invalid.append(
                f"linha {item.row_number}: handle Instagram inválido ({item.instagram!r})"
            )
            continue
        if handle in existing:
            skipped += 1
            continue
        lead = Lead(
            campaign_id=campaign_id,
            nome=item.nome,
            empresa=item.empresa,
            cargo=item.cargo,
            instagram=handle,
            cidade=item.cidade,
            observacoes=item.observacoes,
            status="novo",
        )
        db.add(lead)
        existing.add(handle)
        inserted += 1

    if invalid:
        db.rollback()
        raise ValueError("; ".join(invalid))

    db.commit()
    logger.info(
        "Importação confirmada campaign=%s inseridos=%s ignorados=%s",
        campaign_id,
        inserted,
        skipped,
    )
    return ImportConfirmResponse(
        campaign_id=campaign_id,
        inserted=inserted,
        skipped_duplicates=skipped,
    )
