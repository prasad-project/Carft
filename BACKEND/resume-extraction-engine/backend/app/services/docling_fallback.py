"""Optional Docling fallback for complex layouts. Not installed by default (pip install docling).
Used only when embedded text + OCR produced no usable text."""
from __future__ import annotations

from pathlib import Path


def docling_available() -> bool:
    try:
        import docling  # noqa: F401
        return True
    except Exception:
        return False


def extract_with_docling(path: Path):
    from docling.document_converter import DocumentConverter  # type: ignore

    md = DocumentConverter().convert(str(path)).document.export_to_markdown()
    return [ln for ln in md.splitlines() if ln.strip()]
