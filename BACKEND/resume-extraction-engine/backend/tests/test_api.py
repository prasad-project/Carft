import time

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PDF = "application/pdf"


def _upload(path, name=None, ctype=PDF):
    with open(path, "rb") as f:
        return client.post("/api/v1/resumes/upload", files={"file": (name or path.name, f, ctype)})


def _wait(rid, tok, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/v1/resumes/{rid}/status", headers={"X-Owner-Token": tok}).json()
        if s["status"] in ("completed", "failed"):
            return s
        time.sleep(0.2)
    raise AssertionError("timeout")


def test_full_flow_and_downloads(files):
    r = _upload(files["pdf"])
    assert r.status_code == 201
    rid, tok = r.json()["resume_id"], r.json()["owner_token"]
    H = {"X-Owner-Token": tok}
    assert client.post("/api/v1/resumes/extract", json={"resume_id": rid}, headers=H).status_code == 202
    s = _wait(rid, tok)
    assert s["status"] == "completed" and s["progress"] == 1.0
    assert [x["state"] for x in s["stages"]] == ["done"] * 12
    res = client.get(f"/api/v1/resumes/{rid}/result", headers=H).json()
    assert res["personal_information"]["email"] == "priya.sharma@example.com"
    assert client.get(f"/api/v1/resumes/{rid}/text", headers=H).json()["pages"][0]["page"] == 1
    assert "attachment" in client.get(f"/api/v1/resumes/{rid}/download-json?token={tok}").headers["content-disposition"]
    assert "PRIYA" in client.get(f"/api/v1/resumes/{rid}/download-text", headers=H).text
    # edit + validation
    res["personal_information"]["phone"] = "+91 11111 22222"
    assert client.put(f"/api/v1/resumes/{rid}/result", json=res, headers=H).status_code == 200
    res["personal_information"]["email"] = "not-an-email"
    assert client.put(f"/api/v1/resumes/{rid}/result", json=res, headers=H).status_code == 422
    assert client.delete(f"/api/v1/resumes/{rid}", headers=H).status_code == 204
    assert client.get(f"/api/v1/resumes/{rid}/status", headers=H).status_code == 404


def test_ownership_enforced(files):
    r = _upload(files["pdf"]).json()
    rid = r["resume_id"]
    assert client.get(f"/api/v1/resumes/{rid}/status").status_code == 404
    assert client.get(f"/api/v1/resumes/{rid}/status", headers={"X-Owner-Token": "wrong"}).status_code == 404
    assert client.post("/api/v1/resumes/extract", json={"resume_id": rid}).status_code == 404


def test_result_before_ready_is_409(files):
    r = _upload(files["pdf"]).json()
    assert client.get(f"/api/v1/resumes/{r['resume_id']}/result", headers={"X-Owner-Token": r["owner_token"]}).status_code == 409


@pytest.mark.parametrize("name,ctype,data,code", [
    ("a.txt", "text/plain", b"hello", "UNSUPPORTED_TYPE"),
    ("a.pdf", PDF, b"", "EMPTY_FILE"),
    ("a.pdf", PDF, b"NOT A PDF AT ALL", "BAD_SIGNATURE"),
    ("a.pdf", PDF, b"%PDF-1.4 garbage garbage", "CORRUPTED_FILE"),
    ("a.pdf", "image/png", b"%PDF-1.4", "MIME_MISMATCH"),
    ("a.docx", "application/octet-stream", b"PK\x03\x04junk", "CORRUPTED_FILE"),
])
def test_rejections(name, ctype, data, code):
    r = client.post("/api/v1/resumes/upload", files={"file": (name, data, ctype)})
    assert r.status_code in (400, 413, 415) and r.json()["detail"]["code"] == code


def test_password_protected_pdf_rejected(tmp_path):
    d = pymupdf.open()
    d.new_page().insert_text((50, 50), "secret")
    f = tmp_path / "enc.pdf"
    d.save(str(f), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    assert _upload(f).json()["detail"]["code"] == "PASSWORD_PROTECTED"


def test_pdf_javascript_rejected(tmp_path):
    d = pymupdf.open()
    d.new_page().insert_text((50, 50), "hi")
    d.set_metadata({})
    f = tmp_path / "js.pdf"
    d.save(str(f))
    data = f.read_bytes().replace(b"%%EOF", b"1 0 obj << /S /JavaScript /JS (app.alert(1)) >> endobj\n%%EOF")
    r = client.post("/api/v1/resumes/upload", files={"file": ("js.pdf", data, PDF)})
    assert r.json()["detail"]["code"] == "ACTIVE_CONTENT"


def test_oversize_and_too_many_pages(tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_PAGES", "2")
    from app.core.config import get_settings
    get_settings.cache_clear()
    d = pymupdf.open()
    for _ in range(3):
        d.new_page().insert_text((50, 50), "page")
    f = tmp_path / "big.pdf"
    d.save(str(f))
    assert _upload(f).json()["detail"]["code"] == "TOO_MANY_PAGES"
    monkeypatch.setenv("MAX_FILE_MB", "0.0001")
    get_settings.cache_clear()
    assert client.post("/api/v1/resumes/upload", files={"file": ("a.pdf", b"%PDF-" + b"0" * 5000, PDF)}).status_code == 413
    monkeypatch.undo()
    get_settings.cache_clear()


def test_image_only_blank_pdf_reports_failure_and_retry(tmp_path):
    d = pymupdf.open()
    d.new_page()
    f = tmp_path / "blank.pdf"
    d.save(str(f))
    r = _upload(f).json()
    H = {"X-Owner-Token": r["owner_token"]}
    client.post("/api/v1/resumes/extract", json={"resume_id": r["resume_id"]}, headers=H)
    s = _wait(r["resume_id"], r["owner_token"])
    assert s["status"] == "failed" and s["error"]["code"] == "NO_TEXT"
    assert client.post("/api/v1/resumes/extract", json={"resume_id": r["resume_id"]}, headers=H).status_code == 202  # retry allowed


def test_retention_cleanup(files):
    from app.core.config import get_settings
    from app.services.job_store import job_store
    r = _upload(files["pdf"]).json()
    job = job_store.get(r["resume_id"], check_owner=False)
    job.created_at -= 10 * 3600
    path = job.path
    assert job_store.cleanup_expired() >= 1 and not path.exists()
