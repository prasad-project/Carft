"""Section heading detection via a normalised heading dictionary (exact whole-line matches only)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..utils.text_utils import strip_bullet

HEADINGS = {
    "summary": ["summary", "professional summary", "career summary", "profile", "professional profile",
                "about me", "about", "objective", "career objective", "executive summary",
                "personal statement", "summary of qualifications", "profile summary"],
    "education": ["education", "academic background", "qualifications", "academic details",
                  "academic qualifications", "educational qualifications", "education and training",
                  "academics", "educational background", "academic profile", "education details"],
    "experience": ["experience", "work experience", "professional experience", "employment history",
                   "employment", "work history", "internship", "internships", "internship experience",
                   "career history", "relevant experience", "industrial experience", "experience summary",
                   "professional background", "work experience and internships", "internships and experience"],
    "skills": ["skills", "technical skills", "key skills", "core competencies", "skills summary",
               "technical proficiency", "technical expertise", "areas of expertise", "competencies",
               "tools and technologies", "technologies", "skills and tools", "skills and technologies",
               "it skills", "core skills", "technical skills and tools", "skill set", "skillset",
               "technical summary", "tech stack"],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "project experience",
                 "selected projects", "technical projects", "notable projects", "project work",
                 "projects and open source", "side projects"],
    "certifications": ["certifications", "certificates", "licenses and certifications", "certification",
                       "courses and certifications", "professional certifications", "licenses",
                       "certifications and courses", "certifications and licenses", "courses"],
    "achievements": ["achievements", "accomplishments", "key achievements", "honors", "honours",
                     "extracurricular", "extracurricular activities", "competitions", "hackathons",
                     "achievements and awards", "achievements and extracurricular", "accolades",
                     "positions of responsibility"],
    "awards": ["awards", "awards and honors", "awards and honours", "honors and awards", "scholarships",
               "awards and recognition", "awards and scholarships", "recognition"],
    "publications": ["publications", "research publications", "papers", "research papers", "patents",
                     "research", "publications and patents", "research experience"],
    "languages": ["languages", "language proficiency", "languages known", "language skills"],
    "volunteer": ["volunteer experience", "volunteering", "volunteer work", "social work",
                  "community service", "leadership", "leadership and volunteering", "volunteer"],
    "training": ["training", "trainings", "workshops", "training and workshops", "professional development",
                 "courses completed", "training and courses"],
    "interests": ["interests", "hobbies", "hobbies and interests", "interests and hobbies",
                  "personal interests", "hobbies and activities"],
    "references": ["references", "reference"],
    "personal_details": ["personal details", "personal information", "personal profile", "declaration",
                         "personal data", "contact", "contact information", "contact details"],
}
_LOOKUP = {h: k for k, hs in HEADINGS.items() for h in hs}


def heading_key(text: str):
    t, _ = strip_bullet(text)
    if ":" in t.rstrip(":"):
        return None
    t = t.rstrip(":").strip()
    if not t or len(t.split()) > 7:
        return None
    norm = re.sub(r"\s+", " ", re.sub(r"[^a-z& ]", " ", t.lower().replace("&", " and "))).strip()
    return _LOOKUP.get(norm)


@dataclass
class Section:
    key: str
    title: str
    lines: list = field(default_factory=list)


@dataclass
class SplitResult:
    header: list
    sections: list

    def get(self, key: str) -> list:
        return [s for s in self.sections if s.key == key]

    def lines_for(self, key: str) -> list:
        return [l for s in self.get(key) for l in s.lines]


def split_sections(lines: list) -> SplitResult:
    header, sections, cur = [], [], None
    for ln in lines:
        k = heading_key(ln.text)
        if k:
            cur = Section(k, ln.text.strip().rstrip(":"))
            sections.append(cur)
        elif cur is None:
            header.append(ln)
        else:
            cur.lines.append(ln)
    return SplitResult(header, sections)
