"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    max_file_bytes: int
    max_pages: int
    retention_minutes: int
    rate_limit_per_minute: int
    ocr_enabled: bool
    ocr_lang: str
    ocr_dpi: int
    min_chars_per_page: int
    clamav_enabled: bool
    cors_origins: tuple


@lru_cache
def get_settings() -> Settings:
    default_dir = Path(tempfile.gettempdir()) / "resume_engine_storage"
    return Settings(
        storage_dir=Path(os.getenv("STORAGE_DIR", str(default_dir))),
        max_file_bytes=int(float(os.getenv("MAX_FILE_MB", "10")) * 1024 * 1024),
        max_pages=int(os.getenv("MAX_PAGES", "20")),
        retention_minutes=int(os.getenv("RETENTION_MINUTES", "60")),
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
        ocr_enabled=_bool("OCR_ENABLED", True),
        ocr_lang=os.getenv("OCR_LANG", "eng"),
        ocr_dpi=int(os.getenv("OCR_DPI", "300")),
        min_chars_per_page=int(os.getenv("MIN_CHARS_PER_PAGE", "50")),
        clamav_enabled=_bool("CLAMAV_ENABLED", False),
        cors_origins=tuple(
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
        ),
    )
