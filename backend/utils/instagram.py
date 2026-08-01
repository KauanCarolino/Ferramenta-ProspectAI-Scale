"""Helpers de handle do Instagram."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Username Instagram: 1–30 chars, letras, números, pontos e underscores.
_HANDLE_RE = re.compile(r"^[a-z0-9._]{1,30}$")
_URL_PATH_RE = re.compile(r"^/?([a-zA-Z0-9._]{1,30})/?")


def normalize_instagram_handle(raw: str | None) -> str | None:
    """Normaliza handle Instagram ou URL de perfil para username minúsculo sem @.

    Aceita:
      - @user / user
      - https://instagram.com/user
      - https://www.instagram.com/user/
    Retorna None se vazio ou inválido.
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None

    lower = value.lower()
    if "instagram.com" in lower or lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(value if "://" in value else f"https://{value}")
        path = (parsed.path or "").strip("/")
        if not path:
            return None
        # Pega o primeiro segmento do path (ignora /p/, /reel/, etc.)
        first = path.split("/")[0]
        if first in {"p", "reel", "reels", "stories", "explore", "tv"}:
            return None
        value = first
    else:
        value = value.lstrip("@").strip()

    value = value.lower().strip().rstrip("/")
    if not value or not _HANDLE_RE.match(value):
        return None
    return value


def is_valid_instagram_handle(handle: str | None) -> bool:
    if not handle:
        return False
    return bool(_HANDLE_RE.match(handle))
