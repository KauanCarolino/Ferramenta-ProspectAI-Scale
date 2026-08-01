"""Pacote do serviço de scheduler."""

from services.scheduler.service import (
    cancel_lead_pending,
    cancel_pending_jobs,
    list_campaign_jobs,
    resume_pending_jobs,
    schedule_campaign,
    schedule_followups_for_d1,
)
from services.scheduler.slots import generate_day_slots

__all__ = [
    "cancel_lead_pending",
    "cancel_pending_jobs",
    "generate_day_slots",
    "list_campaign_jobs",
    "process_due_jobs",
    "resume_pending_jobs",
    "schedule_campaign",
    "schedule_followups_for_d1",
]


def __getattr__(name: str) -> object:
    """Export lazy para evitar imports circulares (campaigns ↔ templates ↔ worker)."""
    if name == "process_due_jobs":
        from services.scheduler.worker import process_due_jobs

        return process_due_jobs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
