"""Motor de templates — variáveis + Spintax básico."""

from __future__ import annotations

import hashlib
import logging
import random
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.template import Template
from schemas.template import (
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateUpdate,
)
from services.campaigns.service import get_campaign

logger = logging.getLogger(__name__)

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_SPINTAX_RE = re.compile(r"\{([^{}|]+(?:\|[^{}|]+)+)\}")

ALLOWED_VARS = frozenset({"nome", "empresa", "cargo", "cidade", "observacoes", "instagram"})


def list_templates(
    db: Session,
    *,
    campaign_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Template]:
    stmt = select(Template).order_by(Template.stage)
    if campaign_id is not None:
        stmt = stmt.where(Template.campaign_id == campaign_id)
    return list(db.scalars(stmt.offset(skip).limit(limit)).all())


def get_template(db: Session, template_id: uuid.UUID) -> Template:
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template não encontrado")
    return template


def create_template(db: Session, data: TemplateCreate) -> Template:
    get_campaign(db, data.campaign_id)
    _raise_if_invalid_body(data.body)
    existing = db.scalar(
        select(Template).where(
            Template.campaign_id == data.campaign_id,
            Template.stage == data.stage,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe template para stage '{data.stage}' nesta campanha",
        )
    template = Template(**data.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(db: Session, template_id: uuid.UUID, data: TemplateUpdate) -> Template:
    template = get_template(db, template_id)
    payload = data.model_dump(exclude_unset=True)
    if "body" in payload and payload["body"] is not None:
        _raise_if_invalid_body(payload["body"])
    if "stage" in payload:
        conflict = db.scalar(
            select(Template).where(
                Template.campaign_id == template.campaign_id,
                Template.stage == payload["stage"],
                Template.id != template.id,
            )
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe template para stage '{payload['stage']}' nesta campanha",
            )
    for key, value in payload.items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: uuid.UUID) -> None:
    template = get_template(db, template_id)
    db.delete(template)
    db.commit()


def extract_variables(body: str) -> list[str]:
    """Retorna variáveis `{{var}}` na ordem de aparição (únicas)."""
    seen: list[str] = []
    for match in _VAR_RE.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def count_spintax_groups(body: str) -> int:
    """Conta grupos Spintax `{A|B|…}` no body (não aninhados)."""
    return len(_SPINTAX_RE.findall(body))


def validate_template_body(body: str) -> list[str]:
    """Valida `{{vars}}` e Spintax; retorna lista de problemas (vazia = ok)."""
    issues: list[str] = []

    for name in extract_variables(body):
        if name not in ALLOWED_VARS:
            allowed = ", ".join(sorted(ALLOWED_VARS))
            issues.append(f"Variável desconhecida: '{{{{{name}}}}}' (permitidas: {allowed})")

    issues.extend(_validate_spintax(body))
    return issues


def preview_template(data: TemplatePreviewRequest) -> TemplatePreviewResponse:
    """Renderiza preview; 422 se body inválido ou variáveis faltando."""
    _raise_if_invalid_body(data.body)

    variables_used = extract_variables(data.body)
    missing = [
        name
        for name in variables_used
        if name not in data.variables or data.variables[name] is None
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Variáveis faltando: {', '.join(missing)}",
        )

    try:
        rendered = render_template(data.body, data.variables, seed=data.seed)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return TemplatePreviewResponse(
        rendered=rendered,
        variables_used=variables_used,
        spintax_groups=count_spintax_groups(data.body),
    )


def render_template(
    body: str,
    variables: dict[str, str | None],
    *,
    seed: str | None = None,
) -> str:
    """Substitui {{vars}} e resolve Spintax {A|B|C}.

    O Spintax usa um RNG determinístico seedado por `seed` (ex.: lead_id + stage)
    para que o mesmo lead+stage sempre receba a mesma variação.
    """
    unresolved: list[str] = []

    def _replace_var(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables or variables[key] is None:
            unresolved.append(key)
            return match.group(0)
        return str(variables[key])

    text = _VAR_RE.sub(_replace_var, body)
    if unresolved:
        missing = ", ".join(sorted(set(unresolved)))
        raise ValueError(f"Variáveis não resolvidas: {missing}")

    rng = random.Random(_seed_int(seed) if seed else None)

    def _replace_spin(match: re.Match[str]) -> str:
        options = match.group(1).split("|")
        return rng.choice(options)

    # Resolve Spintax aninhado iterando algumas vezes.
    for _ in range(5):
        if not _SPINTAX_RE.search(text):
            break
        text = _SPINTAX_RE.sub(_replace_spin, text)
    return text


def _raise_if_invalid_body(body: str) -> None:
    issues = validate_template_body(body)
    if issues:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=issues,
        )


def _validate_spintax(body: str) -> list[str]:
    """Valida chaves `{…}` restantes após remover `{{vars}}`."""
    issues: list[str] = []
    stripped = _VAR_RE.sub("", body)
    i = 0
    length = len(stripped)
    while i < length:
        ch = stripped[i]
        if ch == "{":
            close = stripped.find("}", i + 1)
            if close == -1:
                issues.append("Spintax malformado: '{' sem fechamento")
                break
            inner = stripped[i + 1 : close]
            if "|" not in inner:
                issues.append(f"Spintax malformado: '{{{inner}}}' sem alternativas (|)")
            else:
                options = inner.split("|")
                if any(opt.strip() == "" for opt in options):
                    issues.append(f"Spintax malformado: opção vazia em '{{{inner}}}'")
            i = close + 1
        elif ch == "}":
            issues.append("Spintax malformado: '}' sem abertura")
            i += 1
        else:
            i += 1
    return issues


def _seed_int(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)
