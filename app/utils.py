import json
import re
import logging

logger = logging.getLogger(__name__)


def extract_json(text: str) -> str:
    """
    Safely extract JSON from AI output (handles markdown fences).
    """
    if not text:
        return ""

    text = text.strip()

    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                return part
        return ""

    return text


def normalize_numbers(text: str) -> str:
    """
    Convert fractions like 1/2 → 0.5 (JSON-safe)
    """

    def frac_to_float(match):
        a, b = match.group(1), match.group(2)
        try:
            return str(round(float(a) / float(b), 3))
        except Exception:
            return match.group(0)

    return re.sub(r'(\d+)\s*/\s*(\d+)', frac_to_float, text)


def safe_json_load(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"[AI JSON] Failed to parse JSON: {e}")
        return {}
