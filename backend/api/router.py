"""Router agregado /api/v1."""

from fastapi import APIRouter

from api import accounts, campaigns, dashboard, health, leads, logs, settings, templates

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
