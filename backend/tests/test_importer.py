"""Testes unitários do importer."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.importer.service import preview_import
from utils.instagram import normalize_instagram_handle


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@User.Name", "user.name"),
        ("User_Name", "user_name"),
        ("https://instagram.com/AcmeCo", "acmeco"),
        ("https://www.instagram.com/acme.co/", "acme.co"),
        ("", None),
        ("not a handle!!!", None),
        ("https://instagram.com/p/ABC123", None),
    ],
)
def test_normalize_instagram_handle(raw: str, expected: str | None) -> None:
    assert normalize_instagram_handle(raw) == expected


@pytest.mark.unit
def test_preview_import_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "nome,empresa,cargo,instagram,cidade\n"
        "Ana,Acme,CEO,@Ana_Acme,SP\n"
        "Bob,Beta,CTO,bob_beta,RJ\n"
        "Ana2,Acme,CEO,@Ana_Acme,SP\n"
        "Bad,,Dev,not valid!!,\n"
        "Carl,Gamma,VP,https://instagram.com/carl.g,MG\n",
        encoding="utf-8",
    )
    result = preview_import(csv_path, filename="leads.csv")
    assert result.total_rows == 5
    assert result.valid_count == 3
    assert result.rejected_count == 2
    assert result.duplicate_count == 1
    handles = {row.instagram for row in result.preview}
    assert handles == {"ana_acme", "bob_beta", "carl.g"}


@pytest.mark.unit
def test_preview_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("nome,cargo\nA,B\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Colunas obrigatórias"):
        preview_import(path)
