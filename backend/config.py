"""Configurações da aplicação via pydantic-settings (.env)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Configuração de runtime carregada do ambiente / .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ProspectAI Scale"
    app_env: str = "development"
    debug: bool = True

    # SQLite para local/dev; sobrescreva com DSN PostgreSQL em produção.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'prospectai.db'}"

    # CORS — origem padrão do dashboard Vite.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Celery / Redis (stubs na Fase 1; ligados depois).
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Defaults de campanha
    default_messages_per_day: int = 150
    default_duration_days: int = 10
    default_window_start: str = "09:00"
    default_window_end: str = "18:00"
    default_min_interval_sec: int = 120
    default_max_interval_sec: int = 300

    # Anti-ban
    antiban_max_dm_per_account_per_day: int = 50
    antiban_min_delay_sec: int = 120
    antiban_max_delay_sec: int = 300
    antiban_consecutive_failure_threshold: int = 5
    antiban_warmup_enabled: bool = True
    # Lista de proxies separados por vírgula (opcional; rotação leve).
    proxy_urls: str = ""

    # Armazenamento de sessão das contas Instagram (só paths; nunca commitar sessões).
    sessions_dir: str = str(BACKEND_DIR / "data" / "sessions")

    # stub (default / CI) | instagrapi (env INSTAGRAM_ADAPTER)
    instagram_adapter: str = "stub"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def proxy_urls_list(self) -> list[str]:
        return [p.strip() for p in self.proxy_urls.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
