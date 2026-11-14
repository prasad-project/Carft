from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import ValidationError

from ...schemas.resume_schema import ResumeResult
from ...services.job_store import job_store
from ..deps import get_owned_job

router = APIRouter(prefix="/api/v1/resumes", tags=["results"])


def _need_done(job):
    if job.status != "completed" or job.result is None:
        raise HTTPException(409, {"code": "NOT_READY", "message": f"Extraction is {job.status}."})


@router.get("/{resume_id}/text")
async def get_text(job=Depends(get_owned_job)):
    _need_done(job)
    return {"resume_id": job.id, "pages": job.pages}


@router.get("/{resume_id}/result")
async def get_result(job=Depends(get_owned_job)):
    _need_done(job)
    return job.result


@router.put("/{resume_id}/result")
async def put_result(body: dict, job=Depends(get_owned_job)):
    """Save user corrections. The body must validate against the ResumeResult schema."""
    _need_done(job)
    try:
        job.result = ResumeResult.model_validate(body).model_dump(mode="json")
    except ValidationError as e:
        raise HTTPException(422, {"code": "INVALID_RESULT", "message": "Corrected data failed validation.",
                                  "errors": json.loads(e.json(include_input=False))[:10]})
    return job.result


@router.get("/{resume_id}/download-json")
async def download_json(job=Depends(get_owned_job)):
    _need_done(job)
    return Response(json.dumps(job.result, indent=2, ensure_ascii=False), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="resume_extraction.json"'})


@router.get("/{resume_id}/download-text")
async def download_text(job=Depends(get_owned_job)):
    _need_done(job)
    return Response(job.raw_text or "", media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="resume_text.txt"'})


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(job=Depends(get_owned_job)):
    job_store.delete(job.id)
    return Response(status_code=204)
