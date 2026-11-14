from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Query

from ..services.job_store import Job, job_store


def get_owned_job(resume_id: str, x_owner_token: Optional[str] = Header(None),
                  token: Optional[str] = Query(None)) -> Job:
    """404 for unknown id AND wrong token, so ids cannot be probed."""
    job = job_store.get(resume_id, x_owner_token or token)
    if job is None:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Resume not found."})
    return job
