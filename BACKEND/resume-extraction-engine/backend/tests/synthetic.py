"""Synthetic resume generator (PDF single/two-column/multipage, DOCX, scanned PDF) with ground truth."""
from __future__ import annotations

from pathlib import Path

import os

import pymupdf as fitz

_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_HAS = os.path.exists(_REG) and os.path.exists(_BOLD)


def _f(page, bold=False):
    """Register a Unicode font on the page (so en dashes and bullets survive)."""
    name = "ub" if bold else "ur"
    if _HAS:
        page.insert_font(fontname=name, fontfile=_BOLD if bold else _REG)
        return name
    return "hebo" if bold else "helv"

TRUTH = {
    "name": "Priya Sharma", "email": "priya.sharma@example.com", "phone": "+91 98765 43210",
    "location": "Gurugram, Haryana, India",
    "linkedin": "https://linkedin.com/in/priya-sharma-dev", "github": "https://github.com/priyasharma",
    "institutions": ["Indian Institute of Technology, Delhi", "Delhi Public School, R.K. Puram"],
    "companies": ["Acme Technologies Pvt Ltd", "Globex Corp"],
    "titles": ["Software Engineer", "Data Analyst Intern"],
    "projects": ["Resume Parser", "Sales Dashboard"],
    "skills": ["Python", "Java", "FastAPI", "React", "PostgreSQL", "Docker", "Git", "AWS", "TensorFlow", "Power BI"],
    "certs": ["AWS Certified Cloud Practitioner", "Machine Learning Specialization"],
    "languages": ["English", "Hindi"],
}

# ("H", text) heading | ("T", text) plain | ("B", text) bullet
BODY = [
    ("H", "Summary"),
    ("T", "Backend engineer with 3 years of experience building data-heavy web services and ML pipelines."),
    ("H", "Education"),
    ("T", "Indian Institute of Technology, Delhi | 2019 – 2023"),
    ("T", "B.Tech in Computer Science | CGPA: 8.9/10"),
    ("T", "Delhi Public School, R.K. Puram | 2017 – 2019"),
    ("T", "Class XII (CBSE) | 94.2%"),
    ("H", "Experience"),
    ("T", "Software Engineer | Acme Technologies Pvt Ltd | Gurugram, India | Jan 2023 – Present"),
    ("B", "Built FastAPI microservices handling 2M requests per day"),
    ("B", "Reduced API latency by 40% using Redis caching"),
    ("B", "Mentored two junior developers on code reviews"),
    ("T", "Data Analyst Intern | Globex Corp | Jun 2022 – Aug 2022"),
    ("B", "Created Power BI dashboards for the sales team"),
    ("B", "Automated weekly reports with Python and Pandas"),
    ("H", "Skills"),
    ("T", "Programming Languages: Python, Java, SQL"),
    ("T", "Frameworks: FastAPI, React"),
    ("T", "Databases: PostgreSQL, MongoDB"),
    ("T", "Tools: Git, Docker, AWS, Power BI, TensorFlow"),
    ("T", "Soft Skills: Teamwork, Communication"),
    ("H", "Projects"),
    ("T", "Resume Parser | Python, FastAPI, Tesseract | github.com/priyasharma/resume-parser"),
    ("B", "Extracts structured JSON from PDF and DOCX resumes locally"),
    ("B", "Achieved 92% field accuracy on a 50 resume test set"),
    ("T", "Sales Dashboard | Power BI, SQL"),
    ("B", "Interactive dashboard tracking regional revenue"),
    ("H", "Certifications"),
    ("B", "AWS Certified Cloud Practitioner - Amazon Web Services - Mar 2023"),
    ("B", "Machine Learning Specialization - Coursera - Credential ID: ABC12345"),
    ("H", "Achievements"),
    ("B", "Winner, Smart India Hackathon 2022"),
    ("B", "Ranked top 5% in Google Kickstart 2021"),
    ("H", "Languages"),
    ("T", "English (Fluent), Hindi (Native)"),
    ("H", "Interests"),
    ("T", "Chess, Open source, Trail running"),
]
HEADER = ["PRIYA SHARMA", "Backend Software Engineer",
          "priya.sharma@example.com | +91 98765 43210 | Gurugram, Haryana, India",
          "linkedin.com/in/priya-sharma-dev | github.com/priyasharma"]


def _write(page, items, x, y, w, step=14.0):
    for kind, text in items:
        if kind == "H":
            y += 6
            page.insert_text((x, y), text.upper(), fontsize=12, fontname=_f(page, True))
            y += step + 2
        elif kind == "B":
            page.insert_text((x, y), "•", fontsize=10, fontname=_f(page))
            page.insert_text((x + 12, y), text, fontsize=10, fontname=_f(page))
            y += step
        else:
            parts = text.split(" | ")
            if len(parts) > 1 and any(c.isdigit() for c in parts[-1]) and len(parts) >= 2 and kind == "T" and (
                    "–" in parts[-1] and ("20" in parts[-1])):
                page.insert_text((x, y), " | ".join(parts[:-1]), fontsize=10, fontname=_f(page, True))
                tw = fitz.get_text_length(parts[-1], fontname="helv", fontsize=10) * 1.1
                page.insert_text((x + w - tw, y), parts[-1], fontsize=10, fontname=_f(page))
            else:
                page.insert_text((x, y), text, fontsize=10, fontname=_f(page))
            y += step
    return y


def _wrap(items, width):
    import textwrap
    out = []
    for kind, text in items:
        if kind == "H" or len(text) <= width:
            out.append((kind, text))
            continue
        if " | " in text and kind == "T":
            parts = text.split(" | ")
            half = max(1, len(parts) // 2)
            out += [(kind, " | ".join(parts[:half])), (kind, " | ".join(parts[half:]))]
            continue
        lines = textwrap.wrap(text, width)
        out.append((kind, lines[0]))
        out += [("T", l) for l in lines[1:]]
    return out


def build_pdf(path: Path, two_column: bool = False, pages: int = 1) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    y = 50
    page.insert_text((50, y), HEADER[0], fontsize=20, fontname=_f(page, True))
    y += 18
    for h in HEADER[1:]:
        page.insert_text((50, y), h, fontsize=10, fontname=_f(page))
        y += 13
    y += 8
    if two_column:
        side_keys = {"Skills", "Certifications", "Languages", "Interests", "Achievements"}
        secs, cur = [], None
        for kind, text in BODY:
            if kind == "H":
                cur = [text, []]
                secs.append(cur)
            cur[1].append((kind, text))
        side = [it for t, its in secs if t in side_keys for it in its]
        main = [it for t, its in secs if t not in side_keys for it in its]
        _write(page, _wrap(side, 34), 40, y, 170)
        _write(page, _wrap(main, 62), 240, y, 330)
    else:
        items = BODY
        if pages > 1:
            _write(page, items[:30], 50, y, 495)
            page = doc.new_page()
            _write(page, items[30:], 50, 60, 495)
        else:
            _write(page, items, 50, y, 495, step=12.5)
    doc.save(str(path))
    doc.close()
    return path


def build_docx(path: Path) -> Path:
    import docx
    d = docx.Document()
    d.add_paragraph(HEADER[0].title())
    for h in HEADER[1:]:
        d.add_paragraph(h)
    for kind, text in BODY:
        if kind == "H":
            d.add_heading(text, level=1)
        elif kind == "B":
            d.add_paragraph(text, style="List Bullet")
        else:
            d.add_paragraph(text)
    d.save(str(path))
    return path


def build_scanned_pdf(path: Path, src_pdf: Path, rotate: int = 0, dpi: int = 200) -> Path:
    """Rasterise a text PDF into an image-only PDF (no embedded text)."""
    out = fitz.open()
    with fitz.open(src_pdf) as src:
        for p in src:
            pix = p.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
            page = out.new_page(width=p.rect.width, height=p.rect.height)
            page.insert_image(page.rect, pixmap=pix)
            if rotate:
                page.set_rotation(rotate)
    out.save(str(path))
    out.close()
    return path
