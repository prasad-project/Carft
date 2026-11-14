"""Plain data containers passed between the extraction services and the parser."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Line:
    text: str
    page: int = 1
    source: str = "embedded"          # embedded | ocr | docx | docling
    ocr_conf: Optional[float] = None   # 0-100, only for OCR lines


@dataclass
class PageContent:
    page: int
    lines: list = field(default_factory=list)
    method: str = "embedded"           # embedded | ocr | none
    char_count: int = 0
    image_coverage: float = 0.0
    ocr_confidence: Optional[float] = None
    needs_ocr: bool = False
    ocr_failed: bool = False

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)


@dataclass
class ExtractedDocument:
    filename: str
    file_type: str                     # pdf | docx
    doc_type: str                      # text_pdf | scanned_pdf | mixed_pdf | docx
    pages: list
    links: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    extraction_method: str = "embedded_text"

    @property
    def lines(self) -> list:
        return [l for p in self.pages for l in p.lines]

    @property
    def ocr_pages(self) -> list:
        return [p.page for p in self.pages if p.method == "ocr"]

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)
