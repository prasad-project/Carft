"""Upload validation: extension, MIME, magic bytes, size, emptiness, corruption, encryption, page count,
and active-content / macro checks. Nothing in the uploaded file is ever executed."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz

from ..core.config import get_settings

ALLOWED_MIME = {
    "pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}


class ValidationError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class ValidatedFile:
    file_type: str
    page_count: int
    warnings: list


def _ext(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def validate_bytes(filename: str, content_type, data: bytes) -> ValidatedFile:
    s = get_settings()
    ext = _ext(filename)
    if ext not in ("pdf", "docx"):
        raise ValidationError("UNSUPPORTED_TYPE", "Only PDF and DOCX files are supported.", 415)
    if not data:
        raise ValidationError("EMPTY_FILE", "The file is empty.")
    if len(data) > s.max_file_bytes:
        raise ValidationError("FILE_TOO_LARGE", f"File exceeds {s.max_file_bytes // (1024 * 1024)} MB.", 413)
    if content_type and content_type.split(";")[0].strip().lower() not in ALLOWED_MIME[ext]:
        raise ValidationError("MIME_MISMATCH", "File content type does not match its extension.", 415)
    if ext == "pdf":
        if not data.lstrip()[:5] == b"%PDF-":
            raise ValidationError("BAD_SIGNATURE", "File is not a valid PDF (signature mismatch).", 415)
        return _validate_pdf(data, s.max_pages)
    if data[:4] != b"PK\x03\x04":
        raise ValidationError("BAD_SIGNATURE", "File is not a valid DOCX (signature mismatch).", 415)
    return _validate_docx(data)


def _validate_pdf(data: bytes, max_pages: int) -> ValidatedFile:
    warnings: list = []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        raise ValidationError("CORRUPTED_FILE", "The PDF is corrupted or unreadable.")
    try:
        if doc.needs_pass or doc.is_encrypted:
            raise ValidationError("PASSWORD_PROTECTED", "Password-protected PDFs are not supported.")
        n = doc.page_count
        if n == 0:
            raise ValidationError("EMPTY_FILE", "The PDF has no pages.")
        if n > max_pages:
            raise ValidationError("TOO_MANY_PAGES", f"PDF has {n} pages; the limit is {max_pages}.")
    finally:
        doc.close()
    # Best-effort active-content scan on raw bytes (misses objects hidden in compressed streams).
    # Match executable action dictionaries, not harmless navigation actions or arbitrary text.
    action_patterns = (rb"/S\s*/(?:JavaScript|Launch)\b",)
    if any(re.search(pattern, data) for pattern in action_patterns):
        raise ValidationError("ACTIVE_CONTENT", "PDF contains active content (JavaScript/Launch) and was rejected.")
    return ValidatedFile("pdf", n, warnings)


def _validate_docx(data: bytes) -> ValidatedFile:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValidationError("CORRUPTED_FILE", "The DOCX is corrupted.")
    names = zf.namelist()
    if "word/document.xml" not in names:
        raise ValidationError("CORRUPTED_FILE", "Not a valid DOCX (word/document.xml missing).")
    if any(n.lower().endswith("vbaproject.bin") for n in names):
        raise ValidationError("ACTIVE_CONTENT", "Documents containing macros are rejected.")
    if "EncryptedPackage" in names or "EncryptionInfo" in names:
        raise ValidationError("PASSWORD_PROTECTED", "Encrypted DOCX files are not supported.")
    total = sum(i.file_size for i in zf.infolist())
    if total > 200 * 1024 * 1024 or total > 100 * max(len(data), 1):
        raise ValidationError("ZIP_BOMB", "DOCX expands to an unsafe size and was rejected.")
    try:
        import docx
        docx.Document(io.BytesIO(data))
    except Exception:
        raise ValidationError("CORRUPTED_FILE", "The DOCX could not be opened.")
    return ValidatedFile("docx", 1, [])


def scan_malware(path: Path) -> None:
    """Optional ClamAV scan (CLAMAV_ENABLED=true and `clamscan` installed). Fails closed if enabled but missing."""
    if not get_settings().clamav_enabled:
        return
    exe = shutil.which("clamscan")
    if not exe:
        raise ValidationError("SCANNER_UNAVAILABLE", "Malware scanner is enabled but not installed.", 503)
    r = subprocess.run([exe, "--no-summary", str(path)], capture_output=True, timeout=60)
    if r.returncode == 1:
        raise ValidationError("MALWARE_DETECTED", "The file failed the malware scan.")
    if r.returncode != 0:
        raise ValidationError("SCANNER_ERROR", "Malware scan could not be completed.", 503)


def revalidate_on_disk(path: Path, filename: str) -> ValidatedFile:
    return validate_bytes(filename, None, path.read_bytes())
