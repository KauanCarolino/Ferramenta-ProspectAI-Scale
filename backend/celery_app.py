"""Aplicação Celery para workers do scheduler ProspectAI.

Rodar worker:
  cd backend && celery -A celery_app.celery worker -l info

Rodar beat (varredura periódica de jobs vencidos + inbox, opcional):
  cd backend && celery -A celery_app.celery beat -l info

Testes unitários devem chamar ``services.scheduler.worker.process_due_jobs``
diretamente (ou definir ``CELERY_TASK_ALWAYS_EAGER=true``) — Redis não é necessário.
"""

from __future__ import annotations

import logging

from celery import Celery

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery = Celery(
    "prospectai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Modo eager para testes / offline: defina CELERY_TASK_ALWAYS_EAGER=true no env.
    task_always_eager=settings.app_env == "test",
    beat_schedule={
        "process-due-jobs-every-minute": {
            "task": "scheduler.process_due_jobs",
            "schedule": 60.0,  # segundos
        },
        "process-inbox-replies-every-5-min": {
            "task": "accounts.process_inbox_replies",
            "schedule": 300.0,
        },
    },
)


@celery.task(name="scheduler.process_due_jobs")
def process_due_jobs_task(limit: int = 100) -> dict[str, int]:
    """Entrypoint Celery — abre sessão DB e processa jobs vencidos."""
    from database.session import SessionLocal, init_db
    from services.scheduler.worker import process_due_jobs

    init_db()
    db = SessionLocal()
    try:
        result = process_due_jobs(db, limit=limit)
        logger.info("process_due_jobs_task finalizado: %s", result)
        return result
    finally:
        db.close()


@celery.task(name="accounts.process_inbox_replies")
def process_inbox_replies_task(account_id: str | None = None) -> dict[str, int]:
    """Polling periódico da inbox (Celery beat ~5 min)."""
    import uuid

    from database.session import SessionLocal, init_db
    from services.accounts.service import process_inbox_replies

    init_db()
    db = SessionLocal()
    try:
        aid = uuid.UUID(account_id) if account_id else None
        result = process_inbox_replies(db, account_id=aid)
        logger.info("process_inbox_replies_task finalizado: %s", result)
        return result
    finally:
        db.close()
