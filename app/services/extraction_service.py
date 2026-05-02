"""
REFLECTA — Extraction Service
Silently parses free-form journal text into structured JSON
using GROQ (Llama 3.1). This is the "Silent AI" layer.
"""

import json
import logging

from groq import Groq
from sqlalchemy.orm import Session

from app.config import GROQ_API_KEY
from app.security.circuit_breaker import is_circuit_open, record_failure, record_success

logger = logging.getLogger(__name__)
client = Groq(api_key=GROQ_API_KEY)

EXTRACTION_PROMPT = """
Extract structured data from this personal journal entry.
Return ONLY valid JSON, no markdown, no explanation.

Input text: "{user_text}"

Return this exact JSON structure:
{{
  "mood": "one word emotional state",
  "energy_level": 1-10,
  "stressors": ["list of things causing stress"],
  "wins": ["list of positive things mentioned"],
  "excuse_phrases": ["any reasons given for not doing something"],
  "intent_score": 1-10,
  "concerning_phrases": ["any negative self-talk or worrying language"],
  "life_areas_mentioned": ["health/career/relationships/finance/mindset/purpose"]
}}
"""

# Default fallback when AI extraction fails
EXTRACTION_FALLBACK = {
    "mood": "unknown",
    "energy_level": 5,
    "stressors": [],
    "wins": [],
    "excuse_phrases": [],
    "intent_score": 5,
    "concerning_phrases": [],
    "life_areas_mentioned": [],
}


def extract_journal_data(user_text: str) -> dict:
    """
    Calls GROQ to extract structured data from free-form journal text.
    Returns a dict with mood, energy, stressors, wins, excuse patterns, etc.
    Falls back to safe defaults if AI is unavailable.
    """
    if not user_text or not user_text.strip():
        return EXTRACTION_FALLBACK.copy()

    if is_circuit_open("groq"):
        logger.warning("[EXTRACTION] Circuit open — using fallback")
        return EXTRACTION_FALLBACK.copy()

    prompt = EXTRACTION_PROMPT.format(user_text=user_text.strip())

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Low temp for structured extraction
        )
        record_success("groq")

        raw = response.choices[0].message.content.strip()
        extracted = json.loads(raw)

        # Schema enforcement — fill missing keys with defaults
        for key, default_val in EXTRACTION_FALLBACK.items():
            extracted.setdefault(key, default_val)

        # Clamp numeric values
        extracted["energy_level"] = max(1, min(10, int(extracted.get("energy_level", 5))))
        extracted["intent_score"] = max(1, min(10, int(extracted.get("intent_score", 5))))

        logger.info(f"[EXTRACTION] Success — mood={extracted['mood']}, energy={extracted['energy_level']}")
        return extracted

    except json.JSONDecodeError as e:
        logger.warning(f"[EXTRACTION] JSON parse failed: {e}")
        return EXTRACTION_FALLBACK.copy()

    except Exception as e:
        record_failure("groq")
        logger.error(f"[EXTRACTION] GROQ error: {e}")
        return EXTRACTION_FALLBACK.copy()
