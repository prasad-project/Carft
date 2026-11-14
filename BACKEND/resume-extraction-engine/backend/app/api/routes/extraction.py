from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel

from ...core.security import rate_limit
from ...services.job_store import job_store
from ...services.pipeline import run_extraction
from ..deps import get_owned_job

router = APIRouter(prefix="/api/v1/resumes", tags=["extraction"])


class ExtractRequest(BaseModel):
    resume_id: str


@router.post("/extract", status_code=202, dependencies=[Depends(rate_limit)])
async def start_extraction(body: ExtractRequest, bg: BackgroundTasks, x_owner_token: str | None = Header(None)):
    job = job_store.get(body.resume_id, x_owner_token)
    if job is None:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Resume not found."})
    if job.status == "processing":
        raise HTTPException(409, {"code": "ALREADY_PROCESSING", "message": "Extraction already running."})
    if job.status in ("failed", "completed"):
        job_store.reset(job)  # retry / re-run
    job_store.start(job)
    bg.add_task(run_extraction, job.id)
    return job_store.status_payload(job)


@router.get("/{resume_id}/status")
async def get_status(job=Depends(get_owned_job)):
    return job_store.status_payload(job)
