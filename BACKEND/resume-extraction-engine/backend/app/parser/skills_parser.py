"""Skill extraction. A skill is CONFIRMED only when listed in a skills section. Mentions elsewhere
(experience/projects) are returned separately as `inferred` and never counted as confirmed."""
from __future__ import annotations

import re

from ..schemas.resume_schema import Skills
from ..utils.text_utils import dedupe, strip_bullet
from .common import split_list
from .skill_dictionary import ALIASES, AMBIGUOUS, SKILLS

CATEGORIES = list(SKILLS.keys())
_CANON: dict = {}          # lower -> (canonical, category)
for _cat, _names in SKILLS.items():
    for _n in _names:
        _CANON.setdefault(_n.lower(), (_n, _cat))
for _a, _c in ALIASES.items():
    if _c.lower() in _CANON:
        _CANON.setdefault(_a.lower(), _CANON[_c.lower()])
    else:
        _CANON.setdefault(_a.lower(), (_c, "other"))
_CANON.setdefault("microsoft office", ("Microsoft Office", "other"))

_B_L, _B_R = r"(?<![A-Za-z0-9+#_])", r"(?![A-Za-z0-9+#_&])"


def _build(names, flags=0):
    names = sorted({re.escape(n) for n in names}, key=len, reverse=True)
    return re.compile(_B_L + "(?:" + "|".join(names) + ")" + _B_R, flags) if names else None


_ALL_KEYS = [k for k in _CANON if _CANON[k][0] not in AMBIGUOUS and k not in ALIASES or k in ALIASES and
             len(k) > 3 and _CANON[k][0] not in AMBIGUOUS]
_SAFE_RE = _build([k for k in _ALL_KEYS if k not in {"node", "vue", "rest", "ml", "dl", "py", "tf", "js", "ts"}],
                  re.I)
_STRICT_RE = _build([n for n in AMBIGUOUS if n in {c[0] for c in _CANON.values()}])
_SOFT = {c[0] for c in _CANON.values() if c[1] == "soft_skills"}


def lookup(item: str):
    """Exact (normalised) dictionary lookup for a skills-section item."""
    k = re.sub(r"\s+", " ", item.strip().strip(".").lower())
    return _CANON.get(k)


def find_skills(text: str, strict_context: bool = True) -> list:
    """Find dictionary skills inside free text. In non-skills context, ambiguous names, soft skills and
    spreadsheet-ish words are excluded to avoid false matches. Returns [(canonical, category)]."""
    found = []
    for m in _SAFE_RE.finditer(text):
        c = _CANON.get(m.group(0).lower())
        if c and not (strict_context and (c[1] == "soft_skills" or c[0] in AMBIGUOUS)):
            found.append(c)
    if not strict_context and _STRICT_RE:
        for m in _STRICT_RE.finditer(text):
            c = _CANON.get(m.group(0).lower())
            if c:
                found.append(c)
    seen, out = set(), []
    for c in found:
        if c[0] not in seen:
            seen.add(c[0])
            out.append(c)
    return out


_LABEL_MAP = [
    (r"programming|languages?|coding", "programming_languages"),
    (r"framework", "frameworks"), (r"librar", "libraries"),
    (r"database|\bdb\b|data ?store", "databases"),
    (r"cloud", "cloud"),
    (r"\bai\b|\bml\b|machine learning|deep learning|data science|generative", "ai_ml"),
    (r"analytic|visuali|\bbi\b|business intelligence", "data_analytics"),
    (r"operating system|\bos\b", "operating_systems"),
    (r"soft|interpersonal|personal skills", "soft_skills"),
    (r"tool|devops|platform|version control|ide", "developer_tools"),
]
_LABEL_RE = re.compile(r"^([A-Za-z&/ +\-()]{2,45}?)\s*[:\-–]\s*(.+)$")


def _label_cat(label: str):
    l = label.lower()
    for pat, cat in _LABEL_MAP:
        if re.search(pat, l):
            return cat
    return None


def _items(text: str) -> list:
    # expand "Python (Pandas, NumPy)" -> Python, Pandas, NumPy
    text = re.sub(r"\(([^)]*)\)", lambda m: "," + m.group(1) + ",", text)
    return split_list(text)


def parse_skills(lines, human_languages: set | None = None):
    """Returns Skills (confirmed, from skills sections only)."""
    buckets = {c: [] for c in CATEGORIES}
    for ln in lines:
        text, _ = strip_bullet(ln.text)
        label_cat, body = None, text
        m = _LABEL_RE.match(text)
        if m and len(m.group(1).split()) <= 5:
            label_cat, body = _label_cat(m.group(1)), m.group(2)
        for it in _items(body):
            if len(it.split()) > 5 or len(it) > 40 or not re.search(r"[A-Za-z]", it):
                continue
            hit = lookup(it)
            if hit:
                buckets[hit[1]].append(hit[0])
            else:
                if not re.fullmatch(r"[A-Za-z0-9 .+#/&'\-]+", it):
                    continue
                buckets[label_cat or "other"].append(it)
    return Skills(**{c: dedupe(v) for c, v in buckets.items()})


def inferred_from_context(lines, confirmed: Skills) -> list:
    have = {s.lower() for c in CATEGORIES for s in getattr(confirmed, c)}
    out = []
    for ln in lines:
        for name, _ in find_skills(ln.text, strict_context=True):
            if name.lower() not in have:
                out.append(name)
    return dedupe(out)
