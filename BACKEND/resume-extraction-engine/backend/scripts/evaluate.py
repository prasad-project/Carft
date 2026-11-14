"""Field-level precision/recall on differently-styled synthetic resumes (text-level) + timing on files.

Run:  python -m scripts.evaluate
Precision = correct extracted values / extracted values.  Recall = correct extracted / expected values.
Values are compared case-insensitively after whitespace normalisation. The set is small and synthetic:
treat the numbers as a regression signal, NOT as a real-world accuracy claim.
"""
from __future__ import annotations

import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.parser.common import lines_from_text  # noqa: E402
from app.parser.resume_parser import ResumeParser  # noqa: E402
from app.services.models import ExtractedDocument, PageContent  # noqa: E402

CASES = [
    ("us_style", """Michael T. Johnson
Senior Data Scientist
San Francisco, CA | michael.johnson@gmail.com | (415) 555-0132 | linkedin.com/in/mtjohnson
PROFESSIONAL SUMMARY
Data scientist with 8 years of experience in forecasting and experimentation.
PROFESSIONAL EXPERIENCE
Senior Data Scientist, Stripe Inc., San Francisco, CA          March 2019 – Present
- Built demand forecasting models that cut error by 18%
- Led a team of 4 analysts
Data Scientist, Lyft, San Francisco, CA          June 2015 – February 2019
- Designed A/B testing platform used by 30 teams
EDUCATION
University of California, Berkeley
M.S. in Statistics, 2013 – 2015, GPA: 3.9/4.0
EDUCATION_END
TECHNICAL SKILLS
Languages: Python, R, SQL
Tools: Tableau, Spark, Airflow
""".replace("EDUCATION_END\n", ""),
     {"name": ["Michael T. Johnson"], "email": ["michael.johnson@gmail.com"], "phone": ["(415) 555-0132"],
      "companies": ["Stripe Inc.", "Lyft"], "titles": ["Senior Data Scientist", "Data Scientist"],
      "institutions": ["University of California, Berkeley"], "skills": ["Python", "R", "SQL", "Tableau", "Spark", "Airflow"]}),
    ("indian_fresher", """ANANYA IYER
ananya.iyer@outlook.com
Mobile: +91 9876501234
Bengaluru, Karnataka
OBJECTIVE
Final-year student seeking a software engineering role.
EDUCATION
B.Tech in Computer Science and Engineering
Vellore Institute of Technology (VIT), Vellore    2021 - 2025
CGPA: 8.7/10
Class XII (CBSE) - Delhi Public School - 91.4%
INTERNSHIPS
Web Development Intern - Zoho Corporation        May 2023 - Jul 2023
• Built REST APIs with Django and PostgreSQL
SKILLS
Python, Java, C++, Django, React, MySQL, Git
PROJECTS
Smart Attendance System (OpenCV, Flask)
• Face recognition based attendance with 95% accuracy
Library Management | Java, MySQL
• CRUD application with login
CERTIFICATIONS
NPTEL - Data Structures and Algorithms (2023)
LANGUAGES
English, Hindi, Tamil
""", {"name": ["Ananya Iyer"], "email": ["ananya.iyer@outlook.com"], "phone": ["+91 9876501234"],
      "titles": ["Web Development Intern"], "companies": ["Zoho Corporation"],
      "institutions": ["Vellore Institute of Technology (VIT), Vellore", "Delhi Public School"],
      "projects": ["Smart Attendance System", "Library Management"],
      "skills": ["Python", "Java", "C++", "Django", "React", "MySQL", "Git"]}),
    ("company_first", """Rohan Mehta
Pune, Maharashtra | rohan.m@protonmail.com | +91-90000-11111 | github.com/rohanm
WORK HISTORY
Infosys Limited
Systems Engineer | Jan 2021 – Dec 2023
• Maintained CI pipelines using Jenkins and Docker
Capgemini
Analyst | 2019 – 2020
• Wrote SQL reports
EDUCATION
Savitribai Phule Pune University
B.E. Computer Engineering | 2015 – 2019 | First Class
SKILLS
Jenkins, Docker, SQL, Linux
""", {"name": ["Rohan Mehta"], "email": ["rohan.m@protonmail.com"], "phone": ["+91-90000-11111"],
      "companies": ["Infosys Limited", "Capgemini"], "titles": ["Systems Engineer", "Analyst"],
      "institutions": ["Savitribai Phule Pune University"], "skills": ["Jenkins", "Docker", "SQL", "Linux"]}),
    ("minimal", """Sara Khan
sara.khan@example.org
SKILLS
Python, Excel, Communication
EDUCATION
Jamia Millia Islamia University
BA Economics 2016 - 2019
""", {"name": ["Sara Khan"], "email": ["sara.khan@example.org"],
      "institutions": ["Jamia Millia Islamia University"], "skills": ["Python", "Excel", "Communication"]}),
    ("hard_nonstandard", """Contact: dev.patel@mail.com
Career Highlights
Dev Patel
Staff Engineer at Northwind Traders (2018 to now)
Where I studied
Gujarat Technological University, B.E. 2010-2014
Technical Toolkit
Python, Go, Kubernetes
""", {"name": ["Dev Patel"], "email": ["dev.patel@mail.com"], "companies": ["Northwind Traders"],
      "titles": ["Staff Engineer"], "institutions": ["Gujarat Technological University"],
      "skills": ["Python", "Go", "Kubernetes"]}),
]


def _doc(text: str) -> ExtractedDocument:
    lines = lines_from_text(text)
    p = PageContent(page=1, lines=lines, char_count=len(text))
    return ExtractedDocument("eval.txt", "pdf", "text_pdf", [p])


def _norm(s):
    return " ".join(str(s).lower().split())


def extract_values(r) -> dict:
    pi = r.personal_information
    sk = {x for k, v in r.skills.model_dump().items() if k != "inferred_from_context" for x in v}
    return {
        "name": [pi.full_name] if pi.full_name else [], "email": [pi.email] if pi.email else [],
        "phone": [pi.phone] if pi.phone else [],
        "companies": [e.company for e in r.experience if e.company], "titles": [e.job_title for e in r.experience if e.job_title],
        "institutions": [e.institution for e in r.education if e.institution],
        "projects": [p.name for p in r.projects if p.name], "skills": sorted(sk),
    }


def main():
    tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
    wrong = []
    for name, text, truth in CASES:
        t0 = time.perf_counter()
        r = ResumeParser(_doc(text)).run_all()
        ms = (time.perf_counter() - t0) * 1000
        got = extract_values(r)
        for field in set(got) | set(truth):
            g = {_norm(x) for x in got.get(field, [])}
            t = {_norm(x) for x in truth.get(field, [])}
            if field not in truth:
                continue                      # only score fields we have ground truth for
            tp[field] += len(g & t)
            fp[field] += len(g - t)
            fn[field] += len(t - g)
            for x in g - t:
                wrong.append(f"[{name}] WRONG {field}: {x!r}")
            for x in t - g:
                wrong.append(f"[{name}] MISSED {field}: {x!r}")
        print(f"{name:15s} parsed in {ms:5.1f} ms")
    print(f"\n{'field':14s} {'precision':>9s} {'recall':>7s}   (tp/fp/fn)")
    T = [0, 0, 0]
    for f in sorted(tp.keys() | fp.keys() | fn.keys()):
        p = tp[f] / (tp[f] + fp[f]) if tp[f] + fp[f] else 0.0
        r_ = tp[f] / (tp[f] + fn[f]) if tp[f] + fn[f] else 0.0
        print(f"{f:14s} {p:9.2f} {r_:7.2f}   ({tp[f]}/{fp[f]}/{fn[f]})")
        T[0] += tp[f]; T[1] += fp[f]; T[2] += fn[f]
    print(f"{'OVERALL':14s} {T[0] / max(T[0] + T[1], 1):9.2f} {T[0] / max(T[0] + T[2], 1):7.2f}")
    print("\nMismatches:")
    print("\n".join(wrong) or "  none")


if __name__ == "__main__":
    main()
