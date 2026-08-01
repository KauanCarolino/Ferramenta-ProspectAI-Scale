"""Testes do endpoint de health."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
