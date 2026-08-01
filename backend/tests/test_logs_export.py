"""Testes do export CSV de logs."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from services.logging.service import CSV_HEADERS, export_logs_csv, write_log


@pytest.mark.unit
def test_export_logs_csv_service_includes_header_and_row(db_session: Session) -> None:
    entry = write_log(
        db_session,
        action="send",
        result="success",
        channel="instagram",
        instagram_handle="prospect_user",
        details="dm enviado",
        message_hash="abc123",
    )

    csv_text = export_logs_csv(db_session, limit=100)
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    rows = list(reader)

    assert header == list(CSV_HEADERS)
    assert len(rows) == 1
    assert rows[0][1] == "send"
    assert rows[0][2] == "success"
    assert rows[0][3] == "instagram"
    assert rows[0][7] == "prospect_user"
    assert rows[0][9] == "dm enviado"
    assert rows[0][10] == "abc123"
    # ISO-8601 parseável
    datetime.fromisoformat(rows[0][0])
    assert entry.id is not None


@pytest.mark.unit
def test_export_logs_endpoint_returns_csv_attachment(client, db_session: Session) -> None:
    write_log(
        db_session,
        action="login",
        result="info",
        channel="instagram",
        error=None,
    )

    response = client.get("/api/v1/logs/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert "prospectai-logs-" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.csv"')

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert f"prospectai-logs-{today}.csv" in response.headers["content-disposition"]

    reader = csv.reader(io.StringIO(response.text))
    header = next(reader)
    rows = list(reader)
    assert header == list(CSV_HEADERS)
    assert any(row[1] == "login" and row[2] == "info" for row in rows)
