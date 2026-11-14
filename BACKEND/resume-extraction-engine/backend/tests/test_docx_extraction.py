from app.services.docx_extractor import extract_docx


def test_docx_paragraphs_headings_bullets(files):
    pages, _, _, _ = extract_docx(files["docx"])
    texts = [l.text for l in pages[0].lines]
    assert "Priya Sharma" in texts[0]
    assert any(t.startswith("• Built FastAPI") for t in texts)
    assert "Education" in texts


def test_docx_table_and_hyperlink(tmp_path):
    import docx
    d = docx.Document()
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "Skills"
    t.cell(0, 1).text = "Python, Java"
    p = d.add_paragraph()
    part = d.part
    rid = part.relate_to("https://github.com/jane", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), rid)
    r = OxmlElement("w:r")
    tt = OxmlElement("w:t")
    tt.text = "GitHub"
    r.append(tt)
    h.append(r)
    p._p.append(h)
    f = tmp_path / "t.docx"
    d.save(str(f))
    pages, links, _, _ = extract_docx(f)
    txt = pages[0].text
    assert "Python, Java" in txt
    assert "https://github.com/jane" in links
