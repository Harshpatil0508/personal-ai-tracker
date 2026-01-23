import json
import logging
from groq import Groq
from app.config import GROQ_API_KEY
from app.database.database import SessionLocal
from app.database.models import AIBehaviorProfile
from app.utils import extract_json, normalize_numbers, safe_json_load
from app.aiEmbeddings.vector_search import semantic_search

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = Groq(api_key=GROQ_API_KEY)

# -------- DAILY MOTIVATION --------
def generate_daily_motivation(context: dict, user_id: int) -> dict:
    """
    Returns explainable daily motivation.
    Output format:
    {
        "insight": str,
        "explanation": {
            "why": list[str],
            "data_used": list[str],
            "confidence": float,
            "what_would_change_this": list[str]
        }
    }
    """

    # ---- Retrieve memory ----
    memory_items = semantic_search(
        user_id,
        query="recent struggles and motivation"
    )

    memory_text = "\n".join(memory_items)

    # ---- Load behavior profile ----
    with SessionLocal() as db:
        profile = db.get(AIBehaviorProfile, user_id)

    tone = "calm and supportive"
    style = ""
    behavior_reasons = []

    if profile:
        if profile.prefers_encouraging:
            tone = "warm, empathetic, and reassuring"
            behavior_reasons.append(
                "User previously responded positively to encouraging messages"
            )

        if profile.prefers_actionable:
            style = "Provide 1–2 concrete, simple actions."
            behavior_reasons.append(
                "User prefers actionable advice based on past feedback"
            )

    # ---- Build Explainable AI prompt ----
    prompt = f"""
You are a {tone} personal coach.
{style}

User memory:
{memory_text}

User context:
{context}

Return STRICT JSON ONLY with this structure:
{{
  "insight": "short motivational message (max 3 lines)",
  "explanation": {{
    "why": ["reason1", "reason2"],
    "data_used": ["metric1", "metric2"],
    "confidence": number_between_0_and_1,
    "what_would_change_this": ["condition1", "condition2"]
  }}
}}

Rules:
- Never ask questions
- No clichés
- No generic advice
- Be human and practical
- JSON only, no markdown
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()

    logger.info(f"[AI MEMORY USED] {memory_items}")

    # ---- Parse safely ----
    try:
        ai_output = json.loads(raw)

        # Inject system-known behavior reasoning
        if behavior_reasons:
            ai_output["explanation"]["why"].extend(behavior_reasons)

        return ai_output

    except Exception as e:
        logger.warning(f"[DAILY AI] JSON parse failed: {e}")

        # ---- Fallback (system-safe) ----
        return {
            "insight": raw[:200],
            "explanation": {
                "why": [
                    "Generated using recent user context",
                    *behavior_reasons
                ],
                "data_used": list(context.keys()),
                "confidence": 0.3,
                "what_would_change_this": [
                    "More consistent daily logs",
                    "User feedback on this advice"
                ]
            }
        }


# -------- MONTHLY IN-DEPTH REVIEW --------

def generate_monthly_review(summary: dict, user_id: int) -> dict:
    """
    Returns explainable monthly AI review.

    Output:
    {
      "insight": str,
      "explanation": {
        "why": list[str],
        "data_used": list[str],
        "confidence": float,
        "what_would_change_this": list[str]
      }
    }
    """

    memory = semantic_search(
        user_id=user_id,
        query="previous productivity patterns and improvements"
    )

    prompt = f"""
You are a behavioral analyst AI.

STRICT RULES:
- Return ONLY valid JSON
- No markdown
- No prose outside JSON
- Use decimals only
- Follow schema EXACTLY

SCHEMA:
{{
  "insight": "concise but meaningful monthly summary",
  "explanation": {{
    "why": ["reason1", "reason2"],
    "data_used": ["metric1", "metric2"],
    "confidence": 0.0,
    "what_would_change_this": ["condition1", "condition2"]
  }}
}}

Past insights:
{memory}

User monthly timeline:
{summary}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()

        # ---- Strict JSON handling (reuse your utilities) ----
        cleaned = extract_json(raw)
        cleaned = normalize_numbers(cleaned)

        review = safe_json_load(cleaned)

        if not review:
            raise ValueError("Empty or invalid AI JSON")

        # ---- Schema enforcement ----
        review.setdefault("insight", "")
        review.setdefault("explanation", {})

        explanation = review["explanation"]
        explanation.setdefault("why", [])
        explanation.setdefault("data_used", [])
        explanation.setdefault("confidence", 0.0)
        explanation.setdefault("what_would_change_this", [])

        # ---- Hard guards ----
        if not isinstance(explanation["why"], list):
            explanation["why"] = []

        if not isinstance(explanation["data_used"], list):
            explanation["data_used"] = []

        if not isinstance(explanation["what_would_change_this"], list):
            explanation["what_would_change_this"] = []

        explanation["confidence"] = float(
            min(max(explanation.get("confidence", 0.0), 0.0), 1.0)
        )

        return {
            "insight": review["insight"],
            "explanation": explanation
        }

    except Exception as e:
        logger.error(
            f"[MONTHLY AI REVIEW] Explainable generation failed for user {user_id}: {e}"
        )

    # ---- SAFE FALLBACK (Explainable) ----
    return {
        "insight": "This month did not show strong or consistent behavioral patterns.",
        "explanation": {
            "why": ["Insufficient or inconsistent monthly data"],
            "data_used": [],
            "confidence": 0.25,
            "what_would_change_this": [
                "More consistent daily logs",
                "At least 10-15 active days in a month"
            ]
        }
    }
