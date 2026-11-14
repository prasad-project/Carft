"""Tesseract OCR for pages without usable embedded text."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

from ..core.config import get_settings
from ..utils.text_utils import normalize_line
from .image_preprocessor import preprocess, rotate_90s
from .models import Line


_OCR_BULLET = re.compile(r"^(?:[¢«»©®°€§›~=]|[eo](?=\s+[A-Z0-9]))\s*(?=\S)")


def _fix_bullet(text: str) -> str:
    """Tesseract frequently renders list bullets as ¢ « ° o e ... at line start."""
    m = _OCR_BULLET.match(text)
    return "• " + text[m.end():] if m and len(text) > 3 else text


class OCRUnavailable(Exception):
    pass


def ocr_available() -> bool:
    return get_settings().ocr_enabled and shutil.which("tesseract") is not None


def render_pdf_page(path: Path, page_no: int, dpi: int) -> np.ndarray:
    """pdf2image (poppler) first, PyMuPDF as fallback. Returns BGR image."""
    try:
        from pdf2image import convert_from_path

        pil = convert_from_path(str(path), dpi=dpi, first_page=page_no, last_page=page_no)[0]
        return cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception:
        import pymupdf as fitz

        with fitz.open(path) as doc:
            pix = doc[page_no - 1].get_pixmap(dpi=dpi)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR)


def _fix_orientation(img: np.ndarray) -> np.ndarray:
    try:
        osd = pytesseract.image_to_osd(img, output_type=Output.DICT)
        if float(osd.get("orientation_conf", 0)) > 2 and int(osd.get("rotate", 0)):
            return rotate_90s(img, int(osd["rotate"]))
    except Exception:
        pass
    return img


def ocr_image(img_bgr: np.ndarray, page: int):
    """Returns (lines, mean_confidence 0-100)."""
    if not ocr_available():
        raise OCRUnavailable("Tesseract is not installed or OCR is disabled.")
    s = get_settings()
    img = _fix_orientation(img_bgr)
    binary = preprocess(img)
    data = pytesseract.image_to_data(
        binary, lang=s.ocr_lang, config="--oem 3 --psm 3", output_type=Output.DICT
    )
    groups: dict = {}
    for i, word in enumerate(data["text"]):
        word = (word or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not word or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(key, []).append((word, conf))
    lines, confs = [], []
    for key in sorted(groups):
        words = groups[key]
        text = _fix_bullet(normalize_line(" ".join(w for w, _ in words)))
        c = sum(c for _, c in words) / len(words)
        if text:
            lines.append(Line(text, page, "ocr", round(c, 1)))
            confs.extend(c for _, c in words)
    mean = round(sum(confs) / len(confs), 1) if confs else 0.0
    return lines, mean


def ocr_pdf_page(path: Path, page_no: int):
    img = render_pdf_page(path, page_no, get_settings().ocr_dpi)
    return ocr_image(img, page_no)


def ocr_blob(blob: bytes, page: int = 1):
    arr = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ValueError("unreadable image")
    return ocr_image(arr, page)
