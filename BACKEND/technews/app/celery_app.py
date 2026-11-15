from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

s = get_settings()
celery = Celery("technews", broker=s.redis_url, backend=s.redis_url, include=["app.tasks"])
celery.conf.update(
    timezone=s.timezone, enable_utc=True, task_acks_late=True, worker_prefetch_multiplier=1,
    # Static, code-defined schedule (no DB scheduler) => restarts cannot create duplicate jobs.
    # Run exactly ONE beat instance; the Redis lock in the task is a second line of defence.
    beat_schedule={
        "ingest-every-8h": {"task": "app.tasks.scheduled_ingestion", "schedule": crontab(minute=0, hour=s.ingest_hours)},
        "recompute-rankings-hourly": {"task": "app.tasks.rerank", "schedule": crontab(minute=15)},
    },
)
