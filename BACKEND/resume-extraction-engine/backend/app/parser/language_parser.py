"""Spoken/written language parser (not programming languages)."""
from __future__ import annotations

import re

from ..schemas.resume_schema import LanguageEntry
from ..utils.text_utils import strip_bullet
from .common import entry_meta

HUMAN_LANGUAGES = {l.lower(): l for l in [
    "English", "Hindi", "Spanish", "French", "German", "Chinese", "Mandarin", "Cantonese", "Japanese", "Korean",
    "Arabic", "Russian", "Portuguese", "Italian", "Tamil", "Telugu", "Kannada", "Malayalam", "Marathi", "Bengali",
    "Gujarati", "Punjabi", "Urdu", "Odia", "Oriya", "Assamese", "Sanskrit", "Nepali", "Dutch", "Turkish", "Polish",
    "Swedish", "Thai", "Vietnamese", "Indonesian", "Malay", "Hebrew", "Greek", "Persian", "Konkani", "Maithili",
    "Sindhi", "Kashmiri", "Bhojpuri", "Haryanvi", "Rajasthani"]}
PROFICIENCY = re.compile(
    r"(?i)\b(native(?:\s+or\s+bilingual\s+proficiency)?|bilingual|mother\s+tongue|fluent|full\s+professional(?:\s+proficiency)?|"
    r"professional(?:\s+working)?(?:\s+proficiency)?|limited\s+working(?:\s+proficiency)?|proficient|advanced|upper[\s\-]intermediate|"
    r"intermediate|conversational|elementary|basic|beginner|read|write|speak|working\s+proficiency|C1|C2|B1|B2|A1|A2)\b")


def parse_languages(lines) -> list:
    out, seen = [], set()
    for ln in lines:
        text, _ = strip_bullet(ln.text)
        text = re.sub(r"(?i)^languages?(?:\s+known)?\s*[:\-–]\s*", "", text)
        for item in re.split(r"\s*[,;|•·]\s*(?![^()]*\))", text):
            item = item.strip()
            if not item:
                continue
            m = re.match(r"([A-Za-z]+(?:\s[A-Za-z]+)?)\s*(?:[\(\-–:]\s*(.+?)\)?)?$", item)
            if not m:
                continue
            name = m.group(1).strip()
            key = name.lower()
            prof = None
            if m.group(2):
                pm = PROFICIENCY.search(m.group(2))
                prof = m.group(2).strip(" )") if pm else None
            elif key.split()[0] in HUMAN_LANGUAGES and len(name.split()) > 1:
                first, rest = name.split(None, 1)
                if PROFICIENCY.search(rest):
                    name, key, prof = first, first.lower(), rest
            if key not in HUMAN_LANGUAGES:
                continue
            if key in seen:
                continue
            seen.add(key)
            conf = 0.9 if prof else 0.8
            out.append(LanguageEntry(name=HUMAN_LANGUAGES[key], proficiency=prof, **entry_meta([ln], conf)))
    return out


def human_language_items(text: str) -> bool:
    items = [i.strip() for i in re.split(r"[,;|]", text) if i.strip()]
    if not items:
        return False
    hits = sum(1 for i in items if re.split(r"[\s(\-–:]", i)[0].lower() in HUMAN_LANGUAGES)
    return hits >= max(1, len(items) // 2 + (len(items) % 2))
