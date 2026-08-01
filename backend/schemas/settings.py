"""Settings públicas do app para o dashboard (somente leitura na Fase 1)."""

from pydantic import BaseModel, Field


class AppSettingsResponse(BaseModel):
    daily_dm_limit: int = Field(description="Limite padrão de mensagens por dia / orientado à conta")
    min_delay_seconds: int
    max_delay_seconds: int
    warmup_days: int = Field(description="Duração da rampa de warm-up em dias")
    proxy_rotation: bool
