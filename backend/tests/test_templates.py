"""Testes de renderização, preview e validação de templates."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from schemas.campaign import CampaignCreate
from schemas.template import TemplatePreviewRequest
from services import campaigns as campaign_service
from services.templates.service import (
    preview_template,
    render_template,
    validate_template_body,
)


@pytest.mark.unit
def test_render_variables_and_spintax() -> None:
    body = "{Olá|Oi} {{nome}}, da {{empresa}}!"
    out = render_template(
        body,
        {"nome": "Ana", "empresa": "Acme"},
        seed="lead-1-d1",
    )
    assert "Ana" in out
    assert "Acme" in out
    assert out.startswith("Olá") or out.startswith("Oi")
    # Determinístico para a mesma seed
    out2 = render_template(body, {"nome": "Ana", "empresa": "Acme"}, seed="lead-1-d1")
    assert out == out2


@pytest.mark.unit
def test_render_unresolved_var() -> None:
    with pytest.raises(ValueError, match="não resolvidas"):
        render_template("Oi {{nome}}", {})


@pytest.mark.unit
def test_validate_unknown_var() -> None:
    issues = validate_template_body("Oi {{foobar}}")
    assert any("desconhecida" in msg for msg in issues)
    assert any("foobar" in msg for msg in issues)


@pytest.mark.unit
def test_validate_malformed_spintax() -> None:
    issues = validate_template_body("{Olá} sem pipe")
    assert any("sem alternativas" in msg for msg in issues)

    issues_empty = validate_template_body("{Olá|} {{nome}}")
    assert any("opção vazia" in msg for msg in issues_empty)


@pytest.mark.unit
def test_validate_ok() -> None:
    assert validate_template_body("{Olá|Oi} {{nome}}, {{empresa}}") == []


@pytest.mark.unit
def test_preview_ok() -> None:
    result = preview_template(
        TemplatePreviewRequest(
            body="{Olá|Oi} {{nome}}, vi a {{empresa}}...",
            variables={
                "nome": "Ana",
                "empresa": "Acme",
                "cargo": "CEO",
                "cidade": "SP",
                "observacoes": None,
                "instagram": "ana.acme",
            },
            seed="optional-preview-seed",
        )
    )
    assert "Ana" in result.rendered
    assert "Acme" in result.rendered
    assert result.variables_used == ["nome", "empresa"]
    assert result.spintax_groups == 1


@pytest.mark.unit
def test_preview_missing_var() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        preview_template(
            TemplatePreviewRequest(
                body="Oi {{nome}}, da {{empresa}}",
                variables={"nome": "Ana"},
            )
        )
    assert exc_info.value.status_code == 422
    assert "empresa" in str(exc_info.value.detail)


@pytest.mark.unit
def test_preview_null_var_is_missing() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        preview_template(
            TemplatePreviewRequest(
                body="Oi {{nome}}",
                variables={"nome": None},
            )
        )
    assert exc_info.value.status_code == 422
    assert "nome" in str(exc_info.value.detail)


@pytest.mark.unit
def test_preview_unknown_var() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        preview_template(
            TemplatePreviewRequest(
                body="Oi {{xyz}}",
                variables={"xyz": "ok"},
            )
        )
    assert exc_info.value.status_code == 422
    assert any("desconhecida" in str(item) for item in exc_info.value.detail)


@pytest.mark.unit
def test_preview_endpoint_ok(client: TestClient) -> None:
    response = client.post(
        "/api/v1/templates/preview",
        json={
            "body": "{Olá|Oi} {{nome}}, vi a {{empresa}}...",
            "variables": {
                "nome": "Ana",
                "empresa": "Acme",
                "cargo": "CEO",
                "cidade": "SP",
                "observacoes": None,
                "instagram": "ana.acme",
            },
            "seed": "optional-preview-seed",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Ana" in data["rendered"]
    assert data["variables_used"] == ["nome", "empresa"]
    assert data["spintax_groups"] == 1


@pytest.mark.unit
def test_preview_endpoint_missing_var(client: TestClient) -> None:
    response = client.post(
        "/api/v1/templates/preview",
        json={"body": "Oi {{nome}}", "variables": {}},
    )
    assert response.status_code == 422
    assert "nome" in str(response.json()["detail"])


@pytest.mark.unit
def test_create_rejects_unknown_var(client: TestClient, db_session: Session) -> None:
    campaign = campaign_service.create_campaign(
        db_session, CampaignCreate(name="Tpl Campaign", channel="instagram")
    )
    response = client.post(
        "/api/v1/templates",
        json={
            "campaign_id": str(campaign.id),
            "stage": "d1",
            "body": "Oi {{unknown_field}}",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("desconhecida" in str(item) for item in detail)


@pytest.mark.unit
def test_create_valid_template(client: TestClient, db_session: Session) -> None:
    campaign = campaign_service.create_campaign(
        db_session, CampaignCreate(name="Tpl OK", channel="instagram")
    )
    response = client.post(
        "/api/v1/templates",
        json={
            "campaign_id": str(campaign.id),
            "stage": "d1",
            "body": "{Olá|Oi} {{nome}}!",
            "name": "Abertura",
        },
    )
    assert response.status_code == 201
    assert response.json()["body"] == "{Olá|Oi} {{nome}}!"
