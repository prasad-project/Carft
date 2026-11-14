"""Email, phone (Indian + international), location and address detection."""
from __future__ import annotations

import re
from typing import Optional

from .url_parser import EMAIL_RE, URL_RE

PHONE_CAND = re.compile(r"(?<![\w/.@\-])(\(?\+?\d[\d\s().\-]{8,18}\d)(?![\w/@])")
_PHONE_LABEL = re.compile(r"(?i)\b(?:phone|mobile|mob|tel|contact|cell|ph)\b")

INDIAN_STATES = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
                 "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
                 "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
                 "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
                 "Delhi", "NCR", "Jammu and Kashmir", "Chandigarh", "Puducherry"]
US_STATES = ["California", "New York", "Texas", "Washington", "Massachusetts", "Illinois", "Florida", "Georgia",
             "Virginia", "New Jersey", "Colorado", "Pennsylvania", "Ohio", "North Carolina", "Arizona", "Oregon"]
COUNTRIES = ["India", "USA", "United States", "US", "UK", "United Kingdom", "Canada", "Germany", "France",
             "Australia", "Singapore", "UAE", "United Arab Emirates", "Netherlands", "Ireland", "Japan", "Remote"]
CITIES = ["Delhi", "New Delhi", "Mumbai", "Pune", "Bangalore", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
          "Ahmedabad", "Gurgaon", "Gurugram", "Noida", "Greater Noida", "Ghaziabad", "Faridabad", "Jaipur",
          "Lucknow", "Kanpur", "Nagpur", "Indore", "Bhopal", "Chandigarh", "Coimbatore", "Kochi",
          "Thiruvananthapuram", "Visakhapatnam", "Surat", "Vadodara", "Patna", "Ranchi", "Bhubaneswar",
          "Dehradun", "Mysore", "Mysuru", "Mangalore", "Nashik", "Thane", "Navi Mumbai", "Rajkot", "Ludhiana",
          "Amritsar", "Jodhpur", "Udaipur", "Guwahati", "Raipur", "London", "New York", "San Francisco", "Seattle",
          "Austin", "Boston", "Chicago", "Toronto", "Vancouver", "Berlin", "Paris", "Dubai", "Singapore", "Sydney",
          "Melbourne", "Amsterdam", "Dublin", "Tokyo", "Sunnyvale", "Mountain View", "San Jose", "Los Angeles",
          "Remote"]
_PLACES = {p.lower() for p in INDIAN_STATES + US_STATES + COUNTRIES + CITIES}
_ADDR_WORDS = re.compile(
    r"(?i)\b(?:street|st\.|road|rd\.?|nagar|sector|block|flat|house no|apartment|apt|floor|colony|lane|avenue|ave\.?|"
    r"phase|marg|vihar|enclave|society|tower|plot)\b")
_PIN = re.compile(r"\b[1-9]\d{5}\b")
_LOC_LABEL = re.compile(r"(?i)^(?:location|address|city|based in|current location|permanent address)\s*[:\-]\s*(.+)$")


def find_email(lines, links=()) -> Optional[tuple]:
    """Returns (email, line|None, rule_conf)."""
    for l in lines:
        m = EMAIL_RE.search(l.text)
        if m and ".." not in m.group(0):
            return m.group(0).rstrip(".").lower(), l, 0.99
    for u in links:
        if u.lower().startswith("mailto:"):
            e = u[7:].split("?")[0]
            if EMAIL_RE.fullmatch(e):
                return e.lower(), None, 0.97
    return None


def _format_phone(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip(" -.")


def find_phone(lines, links=()) -> Optional[tuple]:
    best = None
    for l in lines:
        text = EMAIL_RE.sub(" ", l.text)
        text = URL_RE.sub(" ", text)
        for m in PHONE_CAND.finditer(text):
            cand = m.group(1)
            digits = re.sub(r"\D", "", cand)
            if not 10 <= len(digits) <= 15:
                continue
            if re.search(r"(?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2}", cand):
                continue
            if cand.count(".") > 1 and "+" not in cand:
                continue
            if (cand.startswith("+91") or (len(digits) == 12 and digits.startswith("91"))) and re.fullmatch(r"91[6-9]\d{9}", digits):
                conf = 0.95
            elif len(digits) == 10 and digits[0] in "6789":
                conf = 0.93
            elif cand.startswith("+") and 10 <= len(digits) <= 15:
                conf = 0.9
            elif re.fullmatch(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", cand):
                conf = 0.85
            else:
                conf = 0.6
            if _PHONE_LABEL.search(l.text):
                conf = min(conf + 0.05, 0.99)
            if best is None or conf > best[2]:
                best = (_format_phone(cand), l, conf)
        if best and best[2] >= 0.9:
            break
    if best is None:
        for u in links:
            if u.lower().startswith("tel:"):
                d = re.sub(r"[^\d+]", "", u[4:])
                if 10 <= len(re.sub(r"\D", "", d)) <= 15:
                    return d, None, 0.9
    return best


def _is_place(token: str) -> bool:
    return token.strip().lower() in _PLACES


def find_location(lines) -> Optional[tuple]:
    """Returns (location, line, conf). Only known cities/states/countries count (no guessing)."""
    for l in lines:
        m = _LOC_LABEL.match(l.text)
        if m and not l.text.lower().startswith("address") and not _PIN.search(m.group(1)):
            return m.group(1).strip(), l, 0.9
    for l in lines:
        for seg in re.split(r"\s+\|\s+|\s*[•·]\s*|\s+[–—]\s+", l.text):
            seg = seg.strip(" ,")
            if not seg or "@" in seg or URL_RE.search(seg) or len(seg) > 60:
                continue
            seg = re.sub(r"(?i)^(?:location|based in|city)\s*[:\-]\s*", "", seg)
            parts = [p.strip() for p in seg.split(",") if p.strip()]
            if 1 <= len(parts) <= 4 and all(not re.search(r"\d{3,}", p) for p in parts):
                known = [p for p in parts if _is_place(p)]
                if known and len(known) >= max(1, len(parts) - 1):
                    return ", ".join(parts), l, 0.9 if len(parts) > 1 else 0.8
                if len(parts) == 2 and _is_place(parts[0]) and re.fullmatch(r"[A-Z]{2}", parts[1]):
                    return ", ".join(parts), l, 0.85
    return None


def find_address(lines) -> Optional[tuple]:
    for l in lines:
        m = re.match(r"(?i)^(?:address|permanent address|current address)\s*[:\-]\s*(.+)$", l.text)
        if m:
            return m.group(1).strip(), l, 0.9
    for l in lines:
        t = l.text
        if "@" in t or URL_RE.search(t):
            continue
        if _ADDR_WORDS.search(t) and (_PIN.search(t) or "," in t) and len(t) < 160:
            return t.strip(), l, 0.7
    return None
