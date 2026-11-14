import os
import tempfile
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="resume_test_"))
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"

import pytest  # noqa: E402

from tests import synthetic as S  # noqa: E402


@pytest.fixture(scope="session")
def files(tmp_path_factory):
    d = tmp_path_factory.mktemp("resumes")
    f = {
        "pdf": S.build_pdf(d / "single.pdf"),
        "pdf2": S.build_pdf(d / "multi.pdf", pages=2),
        "two": S.build_pdf(d / "two.pdf", two_column=True),
        "docx": S.build_docx(d / "r.docx"),
    }
    f["scanned"] = S.build_scanned_pdf(d / "scan.pdf", f["pdf"])
    return f
