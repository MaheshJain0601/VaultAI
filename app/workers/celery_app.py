"""Celery application configuration."""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "vault_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    
    # Result settings
    result_expires=3600,  # 1 hour
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    
    # Rate limiting for AI API calls
    task_annotations={
        "app.workers.tasks.process_document_task": {
            "rate_limit": "10/m"  # 10 documents per minute max
        }
    }
)

