import pytest

from app.services.ocr_service import ocr_available
from app.services.pipeline import extract_document
from tests.synthetic import TRUTH


def _check(res):
    r = res.model_dump(mode="json")
    pi = r["personal_information"]
    assert pi["full_name"] == TRUTH["name"] and pi["email"] == TRUTH["email"]
    assert pi["phone"] == TRUTH["phone"] and "Gurugram" in pi["location"]
    assert r["social_profiles"]["linkedin"] == TRUTH["linkedin"] and r["social_profiles"]["github"] == TRUTH["github"]
    assert [e["institution"] for e in r["education"]] == TRUTH["institutions"]
    assert [e["job_title"] for e in r["experience"]] == TRUTH["titles"]
    assert [e["company"] for e in r["experience"]] == TRUTH["companies"]
    assert [p["name"] for p in r["projects"]] == TRUTH["projects"]
    assert [c["name"] for c in r["certifications"]] == TRUTH["certs"]
    assert [l["name"] for l in r["languages"]] == TRUTH["languages"]
    s = r["skills"]
    flat = {x for k, v in s.items() if k != "inferred_from_context" for x in v}
    assert set(TRUTH["skills"]) <= flat
    assert "traces" or r["extraction_metadata"]["field_traces"]["personal_information.email"]["source_page"] == 1
    return r


@pytest.mark.parametrize("key", ["pdf", "pdf2", "two", "docx"])
def test_native_formats(files, key):
    doc, res = extract_document(files[key], files[key].name)
    r = _check(res)
    assert not r["document"]["ocr_used"]


@pytest.mark.skipif(not ocr_available(), reason="tesseract not installed")
def test_scanned_pdf_via_ocr(files):
    doc, res = extract_document(files["scanned"], "scan.pdf")
    r = _check(res)
    assert r["document"]["ocr_used"] and r["extraction_metadata"]["ocr_pages"] == [1]
    t = r["extraction_metadata"]["field_traces"]["personal_information.email"]
    assert t["confidence"] <= 1 and t["source_text"]


def test_nothing_invented_on_sparse_document(tmp_path):
    import pymupdf
    d = pymupdf.open()
    p = d.new_page()
    p.insert_text((50, 80), "Just some random notes about my weekend plans and groceries to buy tomorrow.", fontsize=11)
    f = tmp_path / "sparse.pdf"
    d.save(str(f))
    _, res = extract_document(f, "sparse.pdf")
    r = res.model_dump(mode="json")
    assert r["personal_information"]["email"] is None and r["personal_information"]["full_name"] is None
    assert r["education"] == [] and r["experience"] == []
    assert "personal_information.email" in r["extraction_metadata"]["missing_fields"]
