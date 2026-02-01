import json
import logging
from groq import Groq
from app.config import GROQ_API_KEY
from app.database.database import SessionLocal
from app.database.models import AIBehaviorProfile
from app.aiEmbeddings.vector_search import semantic_search
from fastapi import HTTPException
from app.security.circuit_breaker import (
    is_circuit_open,
    record_failure,
    record_success,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = Groq(api_key=GROQ_API_KEY)

# -------- DAILY MOTIVATION --------
def generate_daily_motivation(context: dict, user_id: int) -> dict:
    """
    Returns explainable daily motivation.
    """

    # ---------- MEMORY ----------
    if is_circuit_open("jina"):
        logger.warning("[CIRCUIT OPEN] Vector search unavailable")
        memory_items = []
    else:
        try:
            memory_items = semantic_search(
                user_id,
                query="recent struggles and motivation",
                limit=3
            )
            record_success("jina")
        except Exception as e:
            record_failure("jina")
            logger.error(f"[JINA ERROR] {e}")
            memory_items = []

    memory_text = "\n".join(
        f"- {m}" for m in memory_items if len(m) < 300
    )

    # ---------- LOAD PROFILE ----------
    with SessionLocal() as db:
        profile = db.get(AIBehaviorProfile, user_id)

    # ---------- DEFAULTS (SAFE BASELINE) ----------
    tone = "calm and supportive"
    style = ""
    behavior_reasons = []
    avoidance_rules = []
    system_confidence = 0.4  # SAFE DEFAULT

    if profile:
        # ---------- PREFERENCE LEARNING ----------
        if profile.prefers_encouraging:
            tone = "warm, empathetic, and reassuring"
            behavior_reasons.append(
                "User historically responds better to encouraging language"
            )

        if profile.prefers_actionable:
            style = "Provide 1-2 concrete, simple actions."
            behavior_reasons.append(
                "User prefers actionable guidance based on past feedback"
            )

        # ---------- HARD AVOIDANCE ----------
        if profile.avoid_repeating_failed:
            avoidance_rules.append(
                "Do NOT repeat advice patterns that previously failed"
            )

        # ---------- OUTCOME-BASED CONFIDENCE ----------
        successful = profile.successful_advice or 0
        failed = profile.failed_advice or 0

        total = successful + failed
        if total >= 3:
            success_ratio = successful / max(total, 1)
            system_confidence = round(
                min(0.9, max(0.2, success_ratio)),
                2
            )

            # Outcome safety overrides preference tone
            if failed > successful:
                tone = "gentle, neutral, and low-pressure"
                behavior_reasons.append(
                    "Previous advice showed mixed or weak outcomes"
                )
            else:
                behavior_reasons.append(
                    "Previous advice showed positive outcomes"
                )

    # ---------- PROMPT ----------
    constraints_block = (
        "STRICT CONSTRAINTS:\n" +
        "\n".join("- " + r for r in avoidance_rules)
        if avoidance_rules else ""
    )

    prompt = f"""
You are a {tone} personal coach.
{style}

{constraints_block}

User memory:
{memory_text}

User context:
{context}

Return STRICT JSON ONLY:
{{
  "insight": "short motivational message (max 3 lines)",
  "explanation": {{
    "why": ["reason1", "reason2"],
    "data_used": ["metric1", "metric2"],
    "confidence": number_between_0_and_1,
    "what_would_change_this": ["condition1"]
  }}
}}

Rules:
- Never ask questions
- No clichés
- No generic advice
- Be human and practical
- JSON only
"""

    if is_circuit_open("groq"):
        logger.warning("[CIRCUIT OPEN] Groq AI unavailable")
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable. Please try again later."
        )
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        # Success → reset failure counter
        record_success("groq")

    except Exception as e:
        # Failure → record & fail fast
        record_failure("groq")
        logger.error(f"[GROQ ERROR] {e}")

        raise HTTPException(
            status_code=503,
            detail="AI service error. Please retry later."
        )

    raw = response.choices[0].message.content.strip()
    logger.info(f"[AI MEMORY USED] {memory_items}")

    # ---------- PARSING ----------
    try:
        ai_output = json.loads(raw)

        ai_output.setdefault("insight", "")
        ai_output.setdefault("explanation", {})

        explanation = ai_output["explanation"]
        explanation.setdefault("why", [])
        explanation.setdefault("data_used", list(context.keys()))
        explanation.setdefault("confidence", system_confidence)
        explanation.setdefault("what_would_change_this", [])

        # System-truth injection (NOT hallucinated)
        explanation["why"].extend(behavior_reasons)
        explanation["why"].append(
            "Advice adapted using learned user preferences and past outcomes"
        )

        explanation["confidence"] = round(
            min(1.0, max(0.0, explanation["confidence"])),
            2
        )

        return ai_output

    except Exception as e:
        logger.warning(f"[DAILY AI] JSON parse failed: {e}")

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

    # ---------- MEMORY ----------


    if is_circuit_open("jina"):
        logger.warning("[CIRCUIT OPEN] Vector search unavailable")
        memory_items = []
    else:
        try:
            memory_items = semantic_search(
                user_id=user_id,
                query="previous productivity patterns and improvements",
                limit=3
            )
            record_success("jina")
        except Exception as e:
            record_failure("jina")
            logger.error(f"[JINA ERROR] {e}")
            memory_items = []

    

    memory_text = "\n".join(
        f"- {m}" for m in memory_items if len(m) < 300
    )

    # ---------- LOAD PROFILE ----------
    with SessionLocal() as db:
        profile = db.get(AIBehaviorProfile, user_id)

    # ---------- SAFE DEFAULTS ----------
    tone = "analytical and balanced"
    style = ""
    behavior_reasons = []
    avoidance_rules = []
    system_confidence = 0.45  # Monthly = lower base confidence

    if profile:
        # ---------- PREFERENCE LEARNING ----------
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

        # ---------- HARD AVOIDANCE ----------
        if profile.avoid_repeating_failed:
            avoidance_rules.append(
                "Do NOT repeat advice patterns that previously failed"
            )

        # ---------- OUTCOME-BASED CONFIDENCE ----------
        total = profile.successful_advice + profile.failed_advice
        if total >= 3:
            success_ratio = profile.successful_advice / max(total, 1)
            system_confidence = round(
                min(0.85, max(0.3, success_ratio)),
                2
            )

            # Outcome safety overrides tone
            if profile.failed_advice > profile.successful_advice:
                tone = "cautious, neutral, and observational"
                behavior_reasons.append(
                    "Previous AI guidance showed mixed or weak outcomes"
                )
            else:
                behavior_reasons.append(
                    "Previous AI guidance showed positive behavioral outcomes"
                )

    # ---------- PROMPT ----------
    constraints_block = (
        "STRICT CONSTRAINTS:\n" +
        "\n".join("- " + r for r in avoidance_rules)
        if avoidance_rules else ""
    )

    prompt = f"""
You are a {tone} behavioral analyst.
{style}

{constraints_block}

Past insights:
{memory_text}

Monthly timeline data:
{summary}

Return STRICT JSON ONLY:
{{
  "insight": "concise but meaningful monthly summary",
  "explanation": {{
    "why": ["reason1", "reason2"],
    "data_used": ["metric1", "metric2"],
    "confidence": number_between_0_and_1,
    "what_would_change_this": ["condition1", "condition2"]
  }}
}}

Rules:
- No markdown
- No prose outside JSON
- Avoid generic advice
- Base claims ONLY on provided data
"""
    if is_circuit_open("groq"):
        logger.warning("[CIRCUIT OPEN] Groq AI unavailable")
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable. Please try again later."
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        record_success("groq")
        
    except Exception as e:
        record_failure("groq")
        logger.error(f"[GROQ ERROR] {e}")
        raise

    try:
        raw = response.choices[0].message.content.strip()
        review = json.loads(raw)

        # ---------- SCHEMA ENFORCEMENT ----------
        review.setdefault("insight", "")
        review.setdefault("explanation", {})

        explanation = review["explanation"]
        explanation.setdefault("why", [])
        explanation.setdefault("data_used", list(summary.keys()))
        explanation.setdefault("confidence", system_confidence)
        explanation.setdefault("what_would_change_this", [])

        # Inject system-truth reasoning (NOT hallucinated)
        explanation["why"].extend(behavior_reasons)
        explanation["why"].append(
            "Review adapted using learned user preferences and past outcomes"
        )

        explanation["confidence"] = round(
            min(1.0, max(0.0, explanation["confidence"])),
            2
        )

        return review

    except Exception as e:
        logger.error(
            f"[MONTHLY AI REVIEW] JSON parse failed for user {user_id}: {e}"
        )

        # ---------- SAFE FALLBACK ----------
        return {
            "insight": "This month showed mixed or inconsistent behavioral patterns.",
            "explanation": {
                "why": [
                    "Monthly data variability was high",
                    *behavior_reasons
                ],
                "data_used": list(summary.keys()) if isinstance(summary, dict) else [],
                "confidence": system_confidence,
                "what_would_change_this": [
                    "More consistent daily tracking",
                    "At least 10-15 active days in a month"
                ]
            }
        }
