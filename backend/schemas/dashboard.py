"""Schema do resumo do dashboard."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    campaign_id: uuid.UUID | None = None
    enviadas_hoje: int = 0
    respostas_hoje: int = 0
    falhas_hoje: int = 0
    progresso_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    leads_totais: int = 0
    leads_restantes: int = 0
    leads_enviados: int = 0
    campanhas_ativas: int = 0
    status_campanha: str | None = None
