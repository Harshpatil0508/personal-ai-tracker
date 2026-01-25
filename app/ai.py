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

    # ---------- MEMORY (vector recall) ----------
    memory_items = semantic_search(
        user_id,
        query="recent struggles and motivation"
    )
    memory_text = "\n".join(memory_items)

    # ---------- LOAD BEHAVIOR PROFILE ----------
    with SessionLocal() as db:
        profile = db.get(AIBehaviorProfile, user_id)

    tone = "calm and supportive"
    style = ""
    behavior_reasons = []
    system_confidence = 0.5  # base confidence

    if profile:
        # ---- Preference learning----
        if profile.prefers_encouraging:
            tone = "warm, empathetic, and reassuring"
            behavior_reasons.append(
                "User historically responds better to encouraging language"
            )

        if profile.prefers_actionable:
            style = "Provide 1–2 concrete, simple actions."
            behavior_reasons.append(
                "User prefers actionable guidance based on past feedback"
            )

        # ---- Outcome learning----
        total = profile.successful_advice + profile.failed_advice
        if total >= 3:
            success_ratio = profile.successful_advice / max(total, 1)
            system_confidence = round(min(0.9, max(0.2, success_ratio)), 2)

            if profile.failed_advice > profile.successful_advice:
                tone = "gentle, neutral, and low-pressure"
                behavior_reasons.append(
                    "Previous advice was less effective, so tone is softened"
                )
            else:
                behavior_reasons.append(
                    "Previous advice showed positive outcomes"
                )

    # ---------- BUILD EXPLAINABLE PROMPT ----------
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

    # ---------- SAFE PARSING + SYSTEM INJECTION ----------
    try:
        ai_output = json.loads(raw)

        # Ensure required keys exist
        ai_output.setdefault("insight", "")
        ai_output.setdefault("explanation", {})
        ai_output["explanation"].setdefault("why", [])
        ai_output["explanation"].setdefault("data_used", list(context.keys()))
        ai_output["explanation"].setdefault("confidence", system_confidence)
        ai_output["explanation"].setdefault("what_would_change_this", [])

        # Inject system-known reasoning 
        ai_output["explanation"]["why"].extend(behavior_reasons)

        # Clamp confidence safely
        ai_output["explanation"]["confidence"] = round(
            min(1.0, max(0.0, ai_output["explanation"]["confidence"])),
            2
        )

        return ai_output

    except Exception as e:
        logger.warning(f"[DAILY AI] JSON parse failed: {e}")

        # ---------- SYSTEM-SAFE FALLBACK ----------
        return {
            "insight": raw[:200],
            "explanation": {
                "why": [
                    "Generated using recent user context",
                    *behavior_reasons
                ],
                "data_used": list(context.keys()),
                "confidence": system_confidence,
                "what_would_change_this": [
                    "More consistent daily logs",
                    "Explicit user feedback on this advice"
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

    # ---------- MEMORY (vector recall) ----------
    memory_items = semantic_search(
        user_id=user_id,
        query="previous productivity patterns and improvements"
    )
    memory_text = "\n".join(memory_items)

    # ---------- LOAD BEHAVIOR PROFILE ----------
    with SessionLocal() as db:
        profile = db.get(AIBehaviorProfile, user_id)

    tone = "analytical and balanced"
    style = ""
    behavior_reasons = []
    system_confidence = 0.45  # base monthly confidence

    if profile:
        # ---- Preference learning ----
        if profile.prefers_encouraging:
            tone = "supportive but analytical"
            behavior_reasons.append(
                "User responds better to supportive explanations"
            )

        if profile.prefers_actionable:
            style = "End with clear, realistic improvement suggestions."
            behavior_reasons.append(
                "User prefers actionable takeaways in long-term reviews"
            )

        # ---- Outcome learning----
        total = profile.successful_advice + profile.failed_advice
        if total >= 3:
            success_ratio = profile.successful_advice / max(total, 1)
            system_confidence = round(min(0.9, max(0.3, success_ratio)), 2)

            if profile.failed_advice > profile.successful_advice:
                tone = "cautious, neutral, and observational"
                behavior_reasons.append(
                    "Previous AI guidance showed mixed or weak outcomes"
                )
            else:
                behavior_reasons.append(
                    "Previous AI guidance showed positive behavioral outcomes"
                )

    # ---------- BUILD EXPLAINABLE PROMPT ----------
    prompt = f"""
You are a {tone} behavioral analyst AI.
{style}

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
    "confidence": number_between_0_and_1,
    "what_would_change_this": ["condition1", "condition2"]
  }}
}}

Past insights:
{memory_text}

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

        # ---------- JSON HANDLING ----------
        cleaned = extract_json(raw)
        cleaned = normalize_numbers(cleaned)
        review = safe_json_load(cleaned)

        if not review:
            raise ValueError("Empty or invalid AI JSON")

        # ---------- SCHEMA ENFORCEMENT ----------
        review.setdefault("insight", "")
        review.setdefault("explanation", {})

        explanation = review["explanation"]
        explanation.setdefault("why", [])
        explanation.setdefault("data_used", [])
        explanation.setdefault("confidence", system_confidence)
        explanation.setdefault("what_would_change_this", [])

        if not isinstance(explanation["why"], list):
            explanation["why"] = []

        if not isinstance(explanation["data_used"], list):
            explanation["data_used"] = []

        if not isinstance(explanation["what_would_change_this"], list):
            explanation["what_would_change_this"] = []

        # Inject system-known reasoning (truthful, not hallucinated)
        explanation["why"].extend(behavior_reasons)

        # Clamp confidence safely
        explanation["confidence"] = round(
            min(1.0, max(0.0, explanation.get("confidence", system_confidence))),
            2
        )

        return {
            "insight": review["insight"],
            "explanation": explanation
        }

    except Exception as e:
        logger.error(
            f"[MONTHLY AI REVIEW] Explainable generation failed for user {user_id}: {e}"
        )

    # ---------- SAFE FALLBACK ----------
    return {
        "insight": "This month did not show strong or consistent behavioral patterns.",
        "explanation": {
            "why": [
                "Monthly data was insufficient or inconsistent",
                *behavior_reasons
            ],
            "data_used": list(summary.keys()) if isinstance(summary, dict) else [],
            "confidence": system_confidence,
            "what_would_change_this": [
                "More consistent daily logs",
                "At least 10–15 active days in a month"
            ]
        }
    }

