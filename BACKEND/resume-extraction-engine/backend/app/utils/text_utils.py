from __future__ import annotations

import re
import unicodedata

BULLET_CHARS = "•●▪■◦○◆▶►➢➤✓✔‣⁃·*"
_PUA = re.compile(r"[\ue000-\uf8ff]")
_ZW = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_BULLET_START = re.compile(rf"^\s*(?:[{re.escape(BULLET_CHARS)}]|[-–—](?=\s))\s*")
_BULLET_PIPE = re.compile(rf"^([{re.escape(BULLET_CHARS)}])\s*\|\s*")
_STOP = {"and", "of", "the", "in", "for", "at", "to", "a", "an", "with", "on", "by", "or"}


def normalize_line(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = _ZW.sub("", s).replace("\xa0", " ").replace("\t", " ")
    if _PUA.match(s.lstrip()):
        s = "• " + _PUA.sub(" ", s.lstrip(), count=1)
    s = _PUA.sub(" ", s)
    s = re.sub(r"[ ]{2,}", " ", s).strip()
    s = _BULLET_PIPE.sub(r"\1 ", s)
    return s


def strip_bullet(text: str):
    m = _BULLET_START.match(text)
    if m:
        return text[m.end():].strip(), True
    return text.strip(), False


def is_bullet(text: str) -> bool:
    return bool(_BULLET_START.match(text))


def title_ratio(text: str) -> float:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'.\-/+#]*", text) if w.lower() not in _STOP]
    if not words:
        return 0.0
    return sum(1 for w in words if w[0].isupper()) / len(words)


def clean_sep(s: str) -> str:
    return s.strip(" \t,;:|-–—•·")


def dedupe(items):
    seen, out = set(), []
    for i in items:
        k = i.lower() if isinstance(i, str) else i
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def join_wrapped(parts) -> str:
    return re.sub(r"\s+", " ", " ".join(p.strip() for p in parts if p.strip())).strip()
