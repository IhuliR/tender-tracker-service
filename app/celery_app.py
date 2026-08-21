from celery import Celery

from app.config import settings


celery_app = Celery(
    "tender_tracker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    enable_utc=True,
    result_serializer="json",
    task_serializer="json",
    timezone="UTC",
)
