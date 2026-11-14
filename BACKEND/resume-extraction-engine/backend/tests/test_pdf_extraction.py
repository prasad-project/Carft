from app.services.document_detector import final_pdf_type
from app.services.pdf_extractor import extract_pdf, quick_scan


def test_text_pdf_lines_and_pages(files):
    pages, links, _ = extract_pdf(files["pdf"])
    assert len(pages) == 1 and pages[0].char_count > 500
    text = pages[0].text
    assert "PRIYA SHARMA" in text and "priya.sharma@example.com" in text
    assert "Jan 2023 – Present" in text            # right-aligned date merged into its row


def test_multi_page(files):
    pages, _, _ = extract_pdf(files["pdf2"])
    assert [p.page for p in pages] == [1, 2] and all(p.char_count > 50 for p in pages)


def test_two_column_reading_order(files):
    pages, _, _ = extract_pdf(files["two"])
    t = pages[0].text
    assert t.index("EXPERIENCE") > t.index("EDUCATION") > t.index("INTERESTS")   # sidebar, then main
    assert t.index("Software Engineer") < t.index("Data Analyst Intern")


def test_scanned_has_no_text(files):
    stats = quick_scan(files["scanned"])
    assert stats[0][0] < 10 and stats[0][1] > 0.9
