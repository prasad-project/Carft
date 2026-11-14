"""End-to-end extraction pipeline. Each of the 12 stages does real work and is reported as it runs."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from ..core.config import get_settings
from ..core.logging import log
from ..parser.resume_parser import ResumeParser
from ..schemas.resume_schema import ResumeResult
from .docling_fallback import docling_available, extract_with_docling
from .document_detector import final_pdf_type, guess_pdf_type, mark_ocr_pages
from .docx_extractor import extract_docx
from .file_validation import ValidationError, revalidate_on_disk
from .job_store import STAGES, Job, job_store
from .models import ExtractedDocument, Line
from .ocr_service import OCRUnavailable, ocr_available, ocr_blob, ocr_pdf_page
from .pdf_extractor import extract_pdf, quick_scan


class PipelineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class _NullHooks:
    def stage(self, idx: int, state: str) -> None: ...
    def detail(self, text) -> None: ...


class _JobHooks:
    def __init__(self, job: Job):
        self.job = job

    def stage(self, idx, state):
        job_store.set_stage(self.job, idx, state)

    def detail(self, text):
        self.job.detail = text


class _Stage:
    def __init__(self, hooks, idx):
        self.h, self.i = hooks, idx

    def __enter__(self):
        self.h.stage(self.i, "running")
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            self.h.stage(self.i, "done")
        return False


def extract_document(path: Path, filename: str, hooks=None, parse: bool = True):
    """Runs the whole pipeline. Returns (ExtractedDocument, ResumeResult|None)."""
    hooks = hooks or _NullHooks()
    s = get_settings()
    ftype = path.suffix.lower().lstrip(".")
    t0 = time.perf_counter()
    blobs: list = []

    with _Stage(hooks, 0):
        try:
            revalidate_on_disk(path, filename)
        except ValidationError as e:
            raise PipelineError(e.code, e.message)
    with _Stage(hooks, 1):
        hooks.detail("Opening document")
    with _Stage(hooks, 2):
        if ftype == "pdf":
            stats = quick_scan(path)
            doc_type = guess_pdf_type(stats, s.min_chars_per_page)
        else:
            doc_type = "docx"
        hooks.detail(f"Detected: {doc_type}")
    with _Stage(hooks, 3):
        if ftype == "pdf":
            pages, links, meta = extract_pdf(path)
        else:
            pages, links, meta, blobs = extract_docx(path)
    doc = ExtractedDocument(filename=filename, file_type=ftype, doc_type=doc_type, pages=pages, links=links,
                            metadata=meta)
    with _Stage(hooks, 4):
        need = mark_ocr_pages(pages, s.min_chars_per_page) if ftype == "pdf" else []
        if ftype == "docx" and pages[0].char_count < s.min_chars_per_page and blobs:
            pages[0].needs_ocr, need = True, [1]
        hooks.detail(f"{len(need)} page(s) need OCR" if need else "No OCR needed")
    with _Stage(hooks, 5):
        _run_ocr(doc, path, blobs, hooks)
    total_chars = sum(sum(len(l.text) for l in p.lines) for p in doc.pages)
    if total_chars < 30 and docling_available():
        try:
            lines = extract_with_docling(path)
            doc.pages = [type(pages[0])(page=1, lines=[Line(t, 1, "docling") for t in lines], method="embedded")]
            doc.warnings.append("Text recovered using the Docling fallback.")
            total_chars = sum(len(t) for t in lines)
        except Exception:
            pass
    if total_chars < 30:
        raise PipelineError("NO_TEXT", "No readable text could be extracted from this document.")
    if ftype == "pdf":
        doc.doc_type = final_pdf_type(doc.pages)
    doc.extraction_method = (
        "docx" if ftype == "docx" and not doc.ocr_pages else
        "ocr" if doc.ocr_pages and len(doc.ocr_pages) == len(doc.pages) else
        "embedded_text+ocr" if doc.ocr_pages else "embedded_text")
    if not parse:
        return doc, None
    parser = ResumeParser(doc)
    with _Stage(hooks, 6):
        parser.detect_sections()
    with _Stage(hooks, 7):
        parser.parse_personal()
    with _Stage(hooks, 8):
        parser.parse_education_experience()
    with _Stage(hooks, 9):
        parser.parse_skills_projects()
    with _Stage(hooks, 10):
        parser.parse_other()
    with _Stage(hooks, 11):
        result = parser.build()
        result.document.processing_time_ms = int((time.perf_counter() - t0) * 1000)
    return doc, result


def _run_ocr(doc: ExtractedDocument, path: Path, blobs: list, hooks) -> None:
    targets = [p for p in doc.pages if p.needs_ocr]
    if not targets:
        return
    if not ocr_available():
        for p in targets:
            p.ocr_failed = True
        doc.warnings.append(
            f"OCR was required for page(s) {[p.page for p in targets]} but Tesseract is unavailable or disabled.")
        return
    for n, p in enumerate(targets, 1):
        hooks.detail(f"OCR page {n} of {len(targets)}")
        try:
            if doc.file_type == "pdf":
                lines, conf = ocr_pdf_page(path, p.page)
            else:
                lines, conf = [], 0.0
                for b in blobs[:5]:
                    try:
                        l, c = ocr_blob(b, 1)
                        lines += l
                        conf = c if not conf else (conf + c) / 2
                    except Exception:
                        continue
        except OCRUnavailable:
            p.ocr_failed = True
            continue
        except Exception as e:  # noqa: BLE001
            p.ocr_failed = True
            doc.warnings.append(f"OCR failed on page {p.page} ({type(e).__name__}).")
            continue
        ocr_chars = sum(len(l.text) for l in lines)
        if ocr_chars >= p.char_count:
            if doc.file_type == "docx":
                p.lines = p.lines + lines
            else:
                p.lines = lines
            p.method, p.ocr_confidence = "ocr", conf
        if conf and conf < 70:
            doc.warnings.append(f"Low OCR confidence ({conf:.0f}%) on page {p.page}; review extracted values.")


def run_extraction(job_id: str) -> None:
    """Background task entry point."""
    job = job_store.get(job_id, check_owner=False)
    if job is None:
        return
    job_store.start(job)
    try:
        doc, result = extract_document(job.path, job.filename, _JobHooks(job))
        job.pages = [{"page": p.page, "method": p.method, "ocr_confidence": p.ocr_confidence, "text": p.text}
                     for p in doc.pages]
        job.raw_text = doc.text
        job.result = result.model_dump(mode="json")
        job_store.complete(job)
    except PipelineError as e:
        job_store.fail(job, e.code, e.message)
    except Exception as e:  # noqa: BLE001  (never log content, only the exception type)
        log.error("extraction failed job=%s error=%s", job.id, type(e).__name__)
        job_store.fail(job, "EXTRACTION_FAILED", "Extraction failed unexpectedly. You can retry.")
