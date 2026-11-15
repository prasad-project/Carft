"""Optional AI layer: any OpenAI-compatible /chat/completions endpoint (e.g. local Ollama). Off by default.
Any failure returns None and the rule-based pipeline carries on."""
import json
import logging

import httpx

from app.services.categorize import CATEGORIES

log = logging.getLogger(__name__)
PROMPT = (
    "You classify technology news. Reply with JSON only: "
    '{"category": one of %s, "tags": [up to 5 short strings], "relevance": number 0-1 '
    '(is this genuinely about technology?), "summary": one original sentence under 40 words written by you, '
    '"flags": list from ["misleading","low_quality","opinion_as_news"] (empty if none)}'
)


def enhance(s, client: httpx.Client, title: str, description: str | None) -> dict | None:
    if not (s.ai_enabled and s.ai_base_url and s.ai_model):
        return None
    try:
        r = client.post(
            s.ai_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {s.ai_api_key}"} if s.ai_api_key else {},
            json={"model": s.ai_model, "temperature": 0,
                  "messages": [{"role": "system", "content": PROMPT % list(CATEGORIES)},
                               {"role": "user", "content": f"Title: {title}\nDescription: {description or ''}"}]},
        )
        r.raise_for_status()
        data = json.loads(r.json()["choices"][0]["message"]["content"].strip().strip("`").removeprefix("json").strip())
        if data.get("category") not in CATEGORIES:
            data.pop("category", None)
        data["relevance"] = min(1.0, max(0.0, float(data["relevance"]))) if "relevance" in data else None
        return data
    except Exception as e:  # noqa: BLE001 - AI is best-effort by design
        log.warning("ai_enhance_failed", extra={"error": str(e)})
        return None
