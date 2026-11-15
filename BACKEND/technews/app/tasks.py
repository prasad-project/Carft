import logging

import redis

from app.celery_app import celery
from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionJob
from app.services.ingest import run_ingestion
from app.services.ranking import recompute_rankings
from app.util import utcnow

log = logging.getLogger(__name__)
LOCK = "technews:ingestion:lock"


@celery.task(name="app.tasks.run_ingestion", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_ingestion_task(self, job_id=None, source_keys=None, trigger="schedule"):
    s = get_settings()
    lock = redis.Redis.from_url(s.redis_url).lock(LOCK, timeout=3600)
    if not lock.acquire(blocking=False):
        log.warning("ingestion_already_running")
        if job_id:
            with SessionLocal() as db:
                j = db.get(IngestionJob, job_id)
                j.status, j.finished_at = "skipped", utcnow()
                db.commit()
        return None
    try:
        return run_ingestion(SessionLocal, s, job_id=job_id, source_keys=source_keys, trigger=trigger)
    finally:
        lock.release()


@celery.task(name="app.tasks.scheduled_ingestion")
def scheduled_ingestion():
    return run_ingestion_task.apply(kwargs={"trigger": "schedule"}).get()


@celery.task(name="app.tasks.rerank")
def rerank():
    with SessionLocal() as db:
        return recompute_rankings(db, get_settings())


def enqueue_ingestion(job_id: int, source_keys: list[str] | None = None):
    run_ingestion_task.delay(job_id=job_id, source_keys=source_keys, trigger="manual")
