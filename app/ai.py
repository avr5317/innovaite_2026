import os
import re
import random
from typing import Dict, Any, List
import httpx
import json

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

# ---- Gemini configuration ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
Return JSON only. No markdown. No extra text.
"""

def _clamp_and_sanitize(raw: dict) -> Dict[str, Any]:
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

    return {
        "category": cat,
        "urgency_window": urg,
        "severity": sev,
        "items": fixed_items,
        "estimated_total": est,
        "notes": ""
    }

def _extract_json_object(text: str) -> dict:
    """
    Gemini sometimes returns extra text. This pulls the first top-level {...} block.
    """
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output")
    candidate = text[start:end+1]
    return json.loads(candidate)

async def ai_invoke(text: str) -> Dict[str, Any]:
    # If no key, use fallback
    if not GEMINI_API_KEY:
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    # Put system+user into one user prompt (simple + reliable for hackathon)
    prompt = f"{SYSTEM_PROMPT}\n\nUser text:\n{text}\n\nReturn ONLY the JSON object."

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

    # Gemini text lives here:
    # candidates[0].content.parts[0].text
    try:
        content_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        # If Gemini returns something unexpected, fall back
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
        }, "confidence": 0.45}

    # Parse JSON (with robust extraction)
    try:
        raw = _extract_json_object(content_text)
    except Exception:
        # fallback if parsing fails
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
        }, "confidence": 0.45}

    draft = _clamp_and_sanitize(raw)
    return {"draft": draft, "confidence": 0.8}
