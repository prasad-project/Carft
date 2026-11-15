import re
from dataclasses import dataclass, field

CATEGORIES = {
    "artificial-intelligence": "Artificial Intelligence", "machine-learning": "Machine Learning",
    "data-science": "Data Science", "generative-ai": "Generative AI", "programming": "Programming",
    "web-development": "Web Development", "mobile-development": "Mobile Development",
    "cybersecurity": "Cybersecurity", "cloud-computing": "Cloud Computing", "startups": "Startups",
    "technology-business": "Technology Business", "open-source": "Open Source", "research": "Research",
    "robotics": "Robotics", "developer-tools": "Developer Tools", "indian-technology": "Indian Technology",
}
_K = {
    "generative-ai": r"generative ai|genai|chatgpt|\bgpt-?\d|\bllms?\b|large language model|diffusion model|openai|anthropic|\bgemini\b|\bclaude\b|midjourney|copilot",
    "artificial-intelligence": r"artificial intelligence|\bai\b|\bagi\b|chatbot|ai agents?",
    "machine-learning": r"machine learning|deep learning|pytorch|tensorflow|transformers?\b|fine-?tun|reinforcement learning|neural net|hugging ?face|\bml\b",
    "data-science": r"data science|pandas|datasets?\b|analytics|data engineering|kaggle|big data",
    "programming": r"\bpython\b|\brust\b|\bgolang\b|javascript|typescript|compiler|programming language|c\+\+|\bkotlin\b|\bhaskell\b|algorithm",
    "web-development": r"\breact\b|next\.js|\bcss\b|frontend|web development|webassembly|node\.js|\bhtml\b|\bbrowsers?\b",
    "mobile-development": r"\bandroid\b|\bios\b|\bswift\b|flutter|react native|mobile app",
    "cybersecurity": r"security|vulnerabilit|ransomware|malware|\bbreach|\bcve-\d|exploit|zero-day|phishing|encryption",
    "cloud-computing": r"\bcloud\b|\baws\b|\bazure\b|\bgcp\b|kubernetes|docker|serverless|devops|terraform|data cent(er|re)",
    "startups": r"startups?|funding round|series [a-c]\b|raises \$|venture|seed round|unicorn|y combinator",
    "technology-business": r"acquisition|acquires|\bipo\b|antitrust|semiconductor|\bchips?\b|nvidia|layoffs|earnings",
    "open-source": r"open[- ]source|\bgithub\b|\bfoss\b|\blinux\b",
    "research": r"\bresearch|\bpaper\b|researchers|benchmark|\bstudy\b",
    "robotics": r"\brobot|\bdrones?\b|humanoid|autonomous",
    "developer-tools": r"developer tools?|\bsdk\b|\bapi\b|\bide\b|\bcli\b|framework|librar(y|ies)|vscode|devtools|debugger",
    "indian-technology": r"\bindia\b|\bindian\b|bengaluru|bangalore|\bisro\b|\bupi\b|\bjio\b|infosys|\btcs\b|flipkart",
}
_RX = {k: re.compile(v, re.I) for k, v in _K.items()}
# generic/geo categories don't prove "this is about tech" on their own
_NOT_RELEVANCE = {"indian-technology", "research"}
_CLICKBAIT = re.compile(r"you won'?t believe|shocking|this one weird|doctors hate|\bmiracle\b|!!+|(?i:guaranteed)", re.I)


@dataclass
class Categorized:
    category: str
    tags: list[str] = field(default_factory=list)
    relevance: float = 0.0
    flags: list[str] = field(default_factory=list)


def categorize(title: str, description: str | None, prior: float, default_category: str | None) -> Categorized:
    text = f"{title} {description or ''}"
    hits: dict[str, set[str]] = {}
    for cat, rx in _RX.items():
        found = {m.group(0).lower().strip() for m in rx.finditer(text)}
        if found:
            hits[cat] = found
    rel_hits = sum(len(v) for k, v in hits.items() if k not in _NOT_RELEVANCE)
    relevance = min(1.0, 0.25 * rel_hits + prior)
    ranked = sorted(hits, key=lambda c: (-len(hits[c]), list(_RX).index(c)))
    category = ranked[0] if ranked else (default_category or "technology-business")
    tags = []
    for c in ranked[:3]:
        tags += sorted(hits[c])[:2]
    flags = []
    letters = [c for c in title if c.isalpha()]
    if _CLICKBAIT.search(title):
        flags.append("clickbait_phrasing")
    if len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        flags.append("all_caps_title")
    return Categorized(category, tags, round(relevance, 3), flags)


def clean_tags(tags: list[str], limit: int = 8) -> list[tuple[str, str]]:
    out, seen = [], set()
    for t in tags:
        name = re.sub(r"\s+", " ", t).strip()[:40]
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if slug and slug not in seen:
            seen.add(slug)
            out.append((slug, name))
    return out[:limit]
