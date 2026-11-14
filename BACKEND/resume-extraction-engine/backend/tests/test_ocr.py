import pytest

from app.services.ocr_service import ocr_available, ocr_pdf_page

pytestmark = pytest.mark.skipif(not ocr_available(), reason="tesseract not installed")


def test_ocr_reads_scanned_page(files):
    lines, conf = ocr_pdf_page(files["scanned"], 1)
    text = "\n".join(l.text for l in lines)
    assert "priya.sharma@example.com" in text.lower()
    assert conf > 80 and all(l.ocr_conf is not None for l in lines)


def test_ocr_handles_rotated_page(files, tmp_path):
    from tests.synthetic import build_scanned_pdf
    f = build_scanned_pdf(tmp_path / "rot.pdf", files["pdf"], rotate=180)
    lines, conf = ocr_pdf_page(f, 1)
    assert "priya.sharma@example.com" in "\n".join(l.text for l in lines).lower()
