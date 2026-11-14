"""Orchestrates all parsers. Exposed as stages so the pipeline can report real progress."""
from __future__ import annotations

import re

from ..schemas.resume_schema import (AchievementEntry, AdditionalInfo, DocumentInfo, ExtractionMetadata,
                                     GenericEntry, PersonalInformation, ResumeResult, SocialProfiles,
                                     UnclassifiedText)
from ..services.models import ExtractedDocument, Line
from ..utils.text_utils import join_wrapped, strip_bullet
from .achievement_parser import parse_achievements
from .certification_parser import parse_certifications
from .common import Collector, cap_by_ocr, entry_meta, split_list
from .contact_parser import find_address, find_email, find_location, find_phone
from .date_parser import find_date_range
from .education_parser import parse_education
from .entries import group_entries, list_items
from .experience_parser import parse_experience
from .language_parser import human_language_items, parse_languages
from .personal_parser import find_headline, find_name, find_summary
from .project_parser import parse_projects
from .publication_parser import parse_publications
from .section_detector import split_sections
from .skills_parser import CATEGORIES, inferred_from_context, parse_skills
from .url_parser import URL_RE, EMAIL_RE, extract_social

_PAGE_MARK = re.compile(r"(?i)^\s*(?:page\s+\d+(?:\s*(?:of|/)\s*\d+)?|\d+\s*/\s*\d+)\s*$")


class ResumeParser:
    def __init__(self, doc: ExtractedDocument):
        self.doc = doc
        self.c = Collector()
        self.c.warnings.extend(doc.warnings)
        self.lines = [l for l in doc.lines if l.text.strip() and not _PAGE_MARK.match(l.text)]
        self.split = None
        self.r = ResumeResult()
        self.unclassified: list = []
        self._used_header: set = set()
        self.human_lang_lines: list = []

    # stage 7 ---------------------------------------------------------------------------------------
    def detect_sections(self):
        self.split = split_sections(self.lines)
        if not self.split.sections:
            self.c.warnings.append("No section headings detected; only header-level fields could be extracted.")
        return [s.key for s in self.split.sections]

    # stage 8 ---------------------------------------------------------------------------------------
    def parse_personal(self):
        c, header = self.c, self.split.header
        # If header is missing (document starts with a heading) fall back to the first few lines.
        scan = header if header else self.lines[:6]
        pi, soc = PersonalInformation(), SocialProfiles()
        email = find_email(scan, self.doc.links) or find_email(self.lines, self.doc.links)
        if email:
            pi.email = email[0]
            c.trace("personal_information.email", email[0], email[1], "email_regex", email[2])
        name = find_name(scan, pi.email)
        if name:
            pi.full_name, pi.first_name, pi.last_name = name[0], name[1], name[2]
            c.trace("personal_information.full_name", name[0], name[3], "name_position_shape_score", name[4])
            self._used_header.add(id(name[3]))
        phone = find_phone(scan, self.doc.links)
        if phone:
            pi.phone = phone[0]
            c.trace("personal_information.phone", phone[0], phone[1], "phone_regex", phone[2])
        loc = find_location(scan)
        if loc:
            pi.location = loc[0]
            c.trace("personal_information.location", loc[0], loc[1], "known_place_names", loc[2])
        addr = find_address(scan)
        if addr:
            pi.address = addr[0]
            c.trace("personal_information.address", addr[0], addr[1], "address_keywords", addr[2])
        if name:
            hl = find_headline(scan, name[3], name[0])
            if hl:
                pi.headline = hl[0]
                c.trace("personal_information.headline", hl[0], hl[1], "job_keyword_near_name", hl[2])
        summ_lines = self.split.lines_for("summary")
        if summ_lines:
            s = find_summary(summ_lines)
            if s:
                pi.summary = s[0]
                c.trace("personal_information.summary", s[0][:200], s[1], "summary_section", s[2])
        prof, ev = extract_social(scan, self.doc.links, self.lines)
        for k in ("linkedin", "github", "portfolio", "kaggle", "leetcode", "hackerrank"):
            if prof.get(k):
                setattr(soc, k, prof[k])
                u, ln = ev[k]
                c.trace(f"social_profiles.{k}", u, ln, "url_domain_classification",
                        0.95 if ln is not None else 0.9)
        soc.other = prof.get("other", [])
        if prof.get("website"):
            pi.website = prof["website"]
            u, ln = ev["website"]
            c.trace("personal_information.website", u, ln, "first_non_social_url_in_header", 0.8)
        self.r.personal_information, self.r.social_profiles = pi, soc
        self._leftover_header(scan if header else [], pi, soc)

    def _leftover_header(self, header, pi, soc):
        for ln in header:
            if id(ln) in self._used_header:
                continue
            t = EMAIL_RE.sub(" ", ln.text)
            t = URL_RE.sub(" ", t)
            for v in (pi.phone, pi.location, pi.headline, pi.address):
                if v:
                    t = t.replace(v, " ")
            t = re.sub(r"(?i)\b(?:email|e-mail|phone|mobile|tel|linkedin|github|portfolio|website|location|address|contact)\b\s*[:\-]?", " ", t)
            if len(re.findall(r"[A-Za-z0-9]", t)) >= 4:
                self.unclassified.append(UnclassifiedText(
                    text=ln.text, source_page=ln.page, reason="header text not matched to a known field"))

    # stage 9 ---------------------------------------------------------------------------------------
    def parse_education_experience(self):
        for s in self.split.get("education"):
            self.r.education += parse_education(s.lines)
        for s in self.split.get("experience"):
            default = "Internship" if re.search(r"(?i)intern", s.title) and not re.search(r"(?i)experience$", s.title) else None
            self.r.experience += parse_experience(s.lines, default_type=default)

    # stage 10 --------------------------------------------------------------------------------------
    def parse_skills_projects(self):
        skill_lines = []
        for ln in self.split.lines_for("skills"):
            t, _ = strip_bullet(ln.text)
            m = re.match(r"(?i)^languages?\s*[:\-–]\s*(.+)$", t)
            if m and human_language_items(m.group(1)):
                self.human_lang_lines.append(ln)
            else:
                skill_lines.append(ln)
        sk = parse_skills(skill_lines)
        ctx = [l for k in ("experience", "projects") for l in self.split.lines_for(k)]
        sk.inferred_from_context = inferred_from_context(ctx, sk)
        if not skill_lines:
            self.c.warnings.append("No skills section found; technologies found in experience/projects are listed under skills.inferred_from_context (unconfirmed).")
        self.r.skills = sk
        for s in self.split.get("projects"):
            self.r.projects += parse_projects(s.lines)

    # stage 11 --------------------------------------------------------------------------------------
    def parse_other(self):
        sp, r = self.split, self.r
        r.certifications = parse_certifications(sp.lines_for("certifications"))
        r.achievements = parse_achievements(sp.lines_for("achievements"))
        r.awards = parse_achievements(sp.lines_for("awards"))
        r.publications = parse_publications(sp.lines_for("publications"))
        r.languages = parse_languages(sp.lines_for("languages") + self.human_lang_lines)
        r.volunteer_experience = self._generic(sp.lines_for("volunteer"))
        r.training = self._generic(sp.lines_for("training"))
        for ln in sp.lines_for("interests"):
            t, _ = strip_bullet(ln.text)
            t = re.sub(r"(?i)^(?:interests|hobbies)\s*[:\-–]\s*", "", t)
            r.interests += [i for i in split_list(t) if len(i) < 60]
        r.interests = list(dict.fromkeys(r.interests))
        for key in ("references", "personal_details"):
            for s in sp.get(key):
                text = join_wrapped([strip_bullet(l.text)[0] for l in s.lines])
                if text:
                    r.additional_information.append(AdditionalInfo(
                        section=s.title, text=text, source_page=s.lines[0].page if s.lines else None))
        for s in sp.sections:
            if s.key == "summary" and r.personal_information.summary is None and s.lines:
                self.unclassified.append(UnclassifiedText(
                    text=join_wrapped([l.text for l in s.lines]), source_page=s.lines[0].page,
                    reason="summary section too short to confirm"))
        r.unclassified_text = self.unclassified

    def _generic(self, lines) -> list:
        out = []
        for e in group_entries(lines, max_header=2):
            h = " ".join(l.text for l in e.header)
            dr = find_date_range(h)
            title = re.split(r"\s+\|\s+|\s+[–—]\s+|\s+-\s+", re.sub(r"\s+", " ", h if not dr else h.replace(dr.raw, " ")).strip(" ,|-–—"))
            desc = join_wrapped([t for t, _, _ in e.body]) or None
            title = [t.strip(" ,|-–—") for t in title if t.strip(" ,|-–—")]
            out.append(GenericEntry(
                title=title[0] if title else None, organization=title[1] if len(title) > 1 else None,
                start_date=dr.start if dr else None, end_date=dr.end if dr else None, description=desc,
                **entry_meta(e.lines, 0.6 + 0.2 * bool(desc) + 0.2 * bool(dr))))
        return out

    # stage 12 --------------------------------------------------------------------------------------
    def build(self) -> ResumeResult:
        r, d = self.r, self.doc
        ocr_confs = [p.ocr_confidence for p in d.pages if p.ocr_confidence is not None]
        r.document = DocumentInfo(
            filename=d.filename, file_type=d.file_type, document_type=d.doc_type, total_pages=len(d.pages),
            extraction_method=d.extraction_method, ocr_used=bool(d.ocr_pages))
        pi = r.personal_information
        missing = [f"personal_information.{k}" for k in ("full_name", "email", "phone", "location") if not getattr(pi, k)]
        for k in ("education", "experience", "projects"):
            if not getattr(r, k):
                missing.append(k)
        if not any(getattr(r.skills, c) for c in CATEGORIES):
            missing.append("skills")
        review = [k for k, t in self.c.traces.items() if t.status == "needs_review"]
        for k in ("education", "experience", "projects", "certifications", "achievements", "awards",
                  "publications", "languages", "volunteer_experience", "training"):
            review += [f"{k}[{i}]" for i, e in enumerate(getattr(r, k)) if e.status == "needs_review"]
        count = sum(1 for k in ("full_name", "email", "phone", "location", "address", "headline", "summary", "website")
                    if getattr(pi, k))
        count += sum(1 for k in ("linkedin", "github", "portfolio", "kaggle", "leetcode", "hackerrank")
                     if getattr(r.social_profiles, k)) + len(r.social_profiles.other)
        count += sum(len(getattr(r.skills, c)) for c in CATEGORIES)
        secs = {}
        for k in ("education", "experience", "projects", "certifications", "achievements", "awards", "publications",
                  "languages", "volunteer_experience", "training", "interests", "additional_information",
                  "unclassified_text"):
            secs[k] = len(getattr(r, k))
            count += secs[k]
        r.extraction_metadata = ExtractionMetadata(
            pages_processed=len(d.pages), ocr_pages=d.ocr_pages,
            ocr_mean_confidence=round(sum(ocr_confs) / len(ocr_confs), 1) if ocr_confs else None,
            warnings=list(dict.fromkeys(self.c.warnings)), missing_fields=missing, needs_review=review,
            extracted_field_count=count, section_counts=secs, field_traces=self.c.traces)
        return ResumeResult.model_validate(r.model_dump())

    def run_all(self) -> ResumeResult:
        self.detect_sections()
        self.parse_personal()
        self.parse_education_experience()
        self.parse_skills_projects()
        self.parse_other()
        return self.build()
