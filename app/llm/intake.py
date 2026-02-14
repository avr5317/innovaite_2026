from typing import Dict, Any

from app.llm.client import get_api_key, call_gemini
from app.llm.parsers import fallback_parse
from app.llm.validators import clamp_and_sanitize

async def ai_invoke(text: str) -> Dict[str, Any]:
    """
    Main AI intake function.
    
    Uses Gemini API if available, falls back to keyword parsing otherwise.
    
    Returns:
        {
            "draft": {
                "category": str,
                "urgency_window": str,
                "severity": int,
                "items": List[Dict],
                "estimated_total": float,
                "notes": str
            },
            "confidence": float
        }
    """
    # Check if API key is available
    if not get_api_key():
        return fallback_parse(text)

    # Try Gemini API
    try:
        raw = await call_gemini(text)
        draft = clamp_and_sanitize(raw)
        return {"draft": draft, "confidence": 0.8}
    except Exception:
        # If Gemini fails for any reason, use fallback
        return fallback_parse(text)
