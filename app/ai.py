import os
import re
import random
from typing import Dict, Any, List
import httpx

from app.models import Category, Urgency

# ---- Fallback keyword parsing (demo-safe) ----
def _guess_category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["insulin", "medicine", "meds", "prescription", "pharmacy", "antibiotic", "inhaler"]):
        return "meds"
    if any(k in t for k in ["grocer", "food", "rice", "milk", "bread", "eggs", "vegetable", "grocery"]):
        return "groceries"
    if any(k in t for k in ["shelter", "evac", "no place", "homeless", "housing"]):
        return "shelter"
    if any(k in t for k in ["ride", "pickup", "drive", "car", "transport", "uber"]):
        return "transport"
    return "other"

def _guess_urgency(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["asap", "urgent", "now", "immediately", "tonight"]):
        return "now"
    if any(k in t for k in ["today", "by end of day", "this evening"]):
        return "today"
    return "week"

def _guess_severity(category: str, text: str) -> int:
    t = text.lower()
    if category == "meds" and any(k in t for k in ["insulin", "oxygen", "dialysis", "heart", "seizure"]):
        return 5
    if category in ["shelter"] and any(k in t for k in ["evac", "unsafe", "flood", "fire"]):
        return 5
    if "baby" in t or "infant" in t:
        return 4
    if category == "meds":
        return 4
    return 2

def _extract_items(text: str, category: str) -> List[Dict[str, Any]]:
    # very light heuristic: split by commas after ":" or "need"
    t = text.strip()
    items = []
    m = re.split(r"[:\-]\s*", t, maxsplit=1)
    tail = m[1] if len(m) > 1 else t
    parts = [p.strip() for p in re.split(r",| and ", tail) if p.strip()]
    # limit to 6 items
    for p in parts[:6]:
        name = re.sub(r"[^a-zA-Z0-9\s]", "", p).strip()
        if not name:
            continue
        items.append({"name": name[:60], "qty": 1, "unit": "unit", "notes": ""})
    if not items:
        items = [{"name": category, "qty": 1, "unit": "unit", "notes": ""}]
    return items

def _random_reasonable_price(category: str, items: List[Dict[str, Any]]) -> float:
    # For hackathon: "reasonable random"
    base = {"meds": (20, 120), "groceries": (15, 80), "shelter": (0, 60), "transport": (10, 60), "other": (10, 70)}
    lo, hi = base.get(category, (10, 70))
    # scale by item count a bit
    scale = min(1.0 + 0.15 * max(0, len(items)-1), 1.6)
    val = random.uniform(lo, hi) * scale
    return round(max(5.0, min(250.0, val)), 2)

# ---- Optional OpenAI JSON mode (wire if you want) ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = """You are an intake parser for a crisis mutual-aid app.
Return ONLY JSON with this schema:
{
  "category": "meds|groceries|shelter|transport|other",
  "urgency_window": "now|today|week",
  "severity": 1-5,
  "items": [{"name": "...", "qty": number, "unit": "unit", "notes": ""}],
  "estimated_total": number
}
Rules:
- Be conservative and realistic.
- estimated_total must be between 5 and 250.
- If uncertain: category="other", urgency_window="today", severity=2, items=[...], estimated_total reasonable.
"""

async def ai_invoke(text: str) -> Dict[str, Any]:
    # If no key, use fallback
    if not OPENAI_API_KEY:
        cat = _guess_category(text)
        urg = _guess_urgency(text)
        sev = _guess_severity(cat, text)
        items = _extract_items(text, cat)
        price = _random_reasonable_price(cat, items)
        return {"draft": {
            "category": cat,
            "urgency_window": urg,
            "severity": sev,
            "items": items,
            "estimated_total": price,
            "notes": ""
        }, "confidence": 0.55}

    # OpenAI-style call (works with many compatible endpoints)
    # If you use another provider, keep the same JSON contract.
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]

    # Validate minimally + clamp
    import json
    raw = json.loads(content)

    cat = raw.get("category", "other")
    urg = raw.get("urgency_window", "today")
    sev = int(raw.get("severity", 2))
    items = raw.get("items", []) or []
    est = float(raw.get("estimated_total", 25))

    if cat not in ["meds", "groceries", "shelter", "transport", "other"]:
        cat = "other"
    if urg not in ["now", "today", "week"]:
        urg = "today"
    sev = max(1, min(5, sev))

    # sanitize items
    fixed_items = []
    for it in items[:6]:
        name = str(it.get("name", "")).strip()[:60]
        if not name:
            continue
        fixed_items.append({
            "name": name,
            "qty": float(it.get("qty", 1)),
            "unit": str(it.get("unit", "unit"))[:30],
            "notes": str(it.get("notes", ""))[:120]
        })
    if not fixed_items:
        fixed_items = [{"name": cat, "qty": 1, "unit": "unit", "notes": ""}]

    est = round(max(5.0, min(250.0, est)), 2)

    return {"draft": {
        "category": cat,
        "urgency_window": urg,
        "severity": sev,
        "items": fixed_items,
        "estimated_total": est,
        "notes": ""
    }, "confidence": 0.8}
