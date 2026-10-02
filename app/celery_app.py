from __future__ import annotations

from celery import Celery

from app.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    broker_url = settings.celery_broker_url or "redis://localhost:6379/1"
    result_backend = settings.celery_result_backend or "redis://localhost:6379/2"
    celery = Celery("eve_booking", broker=broker_url, backend=result_backend)
    celery.conf.update(
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    return celery


celery_app = create_celery_app()
