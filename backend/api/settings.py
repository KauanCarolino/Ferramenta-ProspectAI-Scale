"""API de settings — expõe defaults de campanha/anti-ban para o dashboard."""

from fastapi import APIRouter

from config import get_settings
from schemas.settings import AppSettingsResponse

router = APIRouter()


@router.get("", response_model=AppSettingsResponse)
def get_app_settings() -> AppSettingsResponse:
    settings = get_settings()
    return AppSettingsResponse(
        daily_dm_limit=settings.antiban_max_dm_per_account_per_day,
        min_delay_seconds=settings.antiban_min_delay_sec,
        max_delay_seconds=settings.antiban_max_delay_sec,
        warmup_days=4,
        proxy_rotation=bool(settings.proxy_urls_list),
    )
