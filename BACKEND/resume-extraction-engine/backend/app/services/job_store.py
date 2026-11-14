"""In-memory job registry + private on-disk storage for uploaded files. No database.
Results live in memory only and are removed after the retention window (or on DELETE).
A restart loses jobs; the uploaded temp files are purged at startup."""
from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..core.config import get_settings
from ..core.logging import log
from ..core.security import hash_token, new_owner_token, token_matches
from ..utils.file_utils import ensure_private_dir, secure_delete

STAGES = [
    "Validating document", "Reading document", "Detecting document type", "Extracting text",
    "Detecting scanned pages", "Running OCR if required", "Identifying resume sections",
    "Extracting personal information", "Extracting education and experience",
    "Identifying skills and projects", "Organizing extracted information", "Generating structured JSON",
]


@dataclass
class Job:
    id: str
    owner_hash: str
    filename: str
    file_type: str
    size: int
    page_count: int
    path: Path
    created_at: float = field(default_factory=time.time)
    status: str = "uploaded"            # uploaded | processing | completed | failed
    stage_states: list = field(default_factory=lambda: ["pending"] * len(STAGES))
    current_stage: Optional[int] = None
    error: Optional[dict] = None
    result: Optional[dict] = None       # ResumeResult as dict (user may edit)
    pages: Optional[list] = None        # [{page, method, ocr_confidence, text}]
    raw_text: Optional[str] = None
    detail: Optional[str] = None        # live detail, e.g. "OCR page 2 of 3"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict = {}
        self._lock = threading.RLock()

    @property
    def dir(self) -> Path:
        return ensure_private_dir(get_settings().storage_dir)

    def purge_storage(self) -> None:
        d = get_settings().storage_dir
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        self.dir

    def create(self, filename: str, file_type: str, data: bytes, page_count: int):
        jid = uuid.uuid4().hex
        token = new_owner_token()
        path = self.dir / f"{jid}.{file_type}"
        path.write_bytes(data)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        job = Job(jid, hash_token(token), filename, file_type, len(data), page_count, path)
        with self._lock:
            self._jobs[jid] = job
        return job, token

    def get(self, jid: str, token: Optional[str] = None, check_owner: bool = True) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(jid)
        if job is None:
            return None
        if check_owner and not token_matches(token, job.owner_hash):
            return None
        return job

    def reset(self, job: Job) -> None:
        with self._lock:
            job.status, job.error, job.result, job.pages, job.raw_text = "uploaded", None, None, None, None
            job.stage_states = ["pending"] * len(STAGES)
            job.current_stage, job.detail = None, None

    def start(self, job: Job) -> None:
        with self._lock:
            job.status, job.started_at = "processing", time.time()

    def set_stage(self, job: Job, idx: int, state: str) -> None:
        with self._lock:
            job.stage_states[idx] = state
            if state == "running":
                job.current_stage = idx

    def fail(self, job: Job, code: str, message: str) -> None:
        with self._lock:
            if job.current_stage is not None and job.stage_states[job.current_stage] == "running":
                job.stage_states[job.current_stage] = "failed"
            job.status, job.error, job.finished_at = "failed", {"code": code, "message": message}, time.time()

    def complete(self, job: Job) -> None:
        with self._lock:
            job.status, job.finished_at, job.detail = "completed", time.time(), None

    def delete(self, jid: str) -> bool:
        with self._lock:
            job = self._jobs.pop(jid, None)
        if job:
            secure_delete(job.path)
        return job is not None

    def cleanup_expired(self) -> int:
        cutoff = time.time() - get_settings().retention_minutes * 60
        with self._lock:
            old = [j.id for j in self._jobs.values() if j.created_at < cutoff and j.status != "processing"]
        for jid in old:
            self.delete(jid)
        if old:
            log.info("retention cleanup removed %d job(s)", len(old))
        return len(old)

    def status_payload(self, job: Job) -> dict:
        done = sum(1 for s in job.stage_states if s == "done")
        return {
            "resume_id": job.id, "status": job.status,
            "progress": round(done / len(STAGES), 3),
            "current_stage": (job.current_stage + 1) if job.current_stage is not None else None,
            "current_stage_name": STAGES[job.current_stage] if job.current_stage is not None else None,
            "detail": job.detail, "total_stages": len(STAGES),
            "stages": [{"index": i + 1, "name": n, "state": s} for i, (n, s) in enumerate(zip(STAGES, job.stage_states))],
            "error": job.error,
            "elapsed_ms": int(((job.finished_at or time.time()) - job.started_at) * 1000) if job.started_at else None,
        }


job_store = JobStore()
