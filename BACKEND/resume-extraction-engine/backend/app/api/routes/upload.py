from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from ...core.config import get_settings
from ...core.security import rate_limit
from ...services.file_validation import ValidationError, scan_malware, validate_bytes
from ...services.job_store import job_store
from ...utils.file_utils import safe_display_name, secure_delete

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


@router.post("/upload", status_code=201, dependencies=[Depends(rate_limit)])
async def upload_resume(file: UploadFile = File(...)):
    s = get_settings()
    buf = bytearray()
    while chunk := await file.read(1024 * 1024):
        buf.extend(chunk)
        if len(buf) > s.max_file_bytes:
            raise HTTPException(413, {"code": "FILE_TOO_LARGE", "message": f"File exceeds {s.max_file_bytes // (1024 * 1024)} MB."})
    name = safe_display_name(file.filename)
    try:
        v = await run_in_threadpool(validate_bytes, name, file.content_type, bytes(buf))
    except ValidationError as e:
        raise HTTPException(e.status, {"code": e.code, "message": e.message})
    job, token = job_store.create(name, v.file_type, bytes(buf), v.page_count)
    try:
        await run_in_threadpool(scan_malware, job.path)
    except ValidationError as e:
        job_store.delete(job.id)
        raise HTTPException(e.status, {"code": e.code, "message": e.message})
    return {"resume_id": job.id, "owner_token": token, "filename": job.filename, "file_type": job.file_type,
            "size_bytes": job.size, "page_count": job.page_count, "warnings": v.warnings}
