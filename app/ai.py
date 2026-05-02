"""
REFLECTA — AI Advice Engine
"The AI that knows you better than you know yourself"

Generates daily coaching advice and monthly narrative reports
using the Reflecta persona with tone-adaptive prompts.
"""

import json
import logging

from groq import Groq
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import GROQ_API_KEY
from app.database.database import SessionLocal
from app.database.models import PersonModel
from app.services.rag_service import semantic_recall
from app.security.circuit_breaker import is_circuit_open, record_failure, record_success

logger = logging.getLogger(__name__)
client = Groq(api_key=GROQ_API_KEY)


# ─── TONE MAP ────────────────────────────────────────────────────
TONE_MAP = {
    "blunt": "brutally direct — no sugarcoating, call out patterns, name the hard truth",
    "balanced": "honest but warm — firm coaching with empathy",
    "push": "aggressive accountability — no excuses accepted, challenge every weakness",
}


# ─── DAILY ADVICE ────────────────────────────────────────────────
def generate_daily_advice(
    user_name: str,
    coach_tone: str,
    days_active: int,
    onboarding_data: dict,
    person_model_data: dict,
    completion_summary: str,
    mood_trend: str,
    stressors: list,
    excuses: list,
    morning_score: int | None,
    morning_text: str | None,
    evening_text: str | None,
    goals_completed: int,
    goals_total: int,
    user_id: int,
) -> str:
    """
    Generates Reflecta daily coaching advice using the full
    user context and persona-driven tone.
    """

    # ── Memory recall via RAG ──
    rag_context = _get_rag_context(user_id, "recent struggles, patterns, and goals")

    tone_instruction = TONE_MAP.get(coach_tone, TONE_MAP["balanced"])

    prompt = f"""
You are Reflecta, a brutally honest AI life coach.
Your tone is: {coach_tone} — {tone_instruction}

USER PROFILE:
Name: {user_name}
Days active: {days_active}
Onboarding data: {json.dumps(onboarding_data, default=str)}
Person model: {json.dumps(person_model_data, default=str)}

LAST 7 DAYS DATA:
Goal completion: {completion_summary}
Mood trend: {mood_trend}
Top mentioned stressors: {stressors}
Excuse patterns detected: {excuses}

RECENT JOURNAL CONTEXT (from memory):
{rag_context}

TODAY:
Morning feeling: {morning_score}/10
Morning entry: {morning_text or 'Not submitted'}
Evening entry: {evening_text or 'Not submitted'}
Goals completed today: {goals_completed}/{goals_total}

YOUR TASK:
Write daily coaching advice in 3-5 sentences.
- Reference specific patterns you've noticed
- Connect mood data to performance data
- Give ONE clear actionable instruction for tomorrow
- If concerning phrases detected, address wellbeing first
- Do NOT give generic motivation
- Sound like a coach who actually knows this person

Output only the advice text, no labels or headers.
"""

    return _call_groq(prompt, user_id, "daily_advice")


# ─── MONTHLY REPORT ─────────────────────────────────────────────
def generate_monthly_report(
    user_name: str,
    coach_tone: str,
    month_name: str,
    active_days: int,
    completion_rate: float,
    best_category: str,
    best_rate: float,
    worst_category: str,
    worst_rate: float,
    emotion_summary: dict,
    top_excuse: str,
    biggest_win: str,
    mood_direction: str,
    advice_effectiveness: float,
    model_delta: dict,
    user_id: int,
) -> str:
    """
    Generates a monthly narrative growth story — a letter
    from a coach who has watched them all month.
    """

    tone_instruction = TONE_MAP.get(coach_tone, TONE_MAP["balanced"])

    prompt = f"""
You are Reflecta. Write a personal monthly growth
story for {user_name}. This should feel like a
letter from a coach who has watched them all month.

DATA FOR {month_name}:
Total active days: {active_days}
Goal completion rate: {completion_rate}%
Best category: {best_category} ({best_rate}%)
Weakest category: {worst_category} ({worst_rate}%)
Dominant emotions: {json.dumps(emotion_summary, default=str)}
Top excuse this month: {top_excuse}
Biggest win: {biggest_win}
Mood trend: {mood_direction}
Advice effectiveness: {advice_effectiveness}%
Person model changes: {json.dumps(model_delta, default=str)}

WRITE IN THIS STRUCTURE:
1. WHO YOU WERE THIS MONTH (2-3 sentences, emotional)
2. WHAT YOU ACTUALLY DID (facts, honest)
3. WHAT I NOTICED (patterns they may not see)
4. THE HONEST TRUTH (the hard thing they need to hear)
5. NEXT MONTH'S MISSION (one focused directive)

Tone: {coach_tone} — {tone_instruction}
Be specific. Reference real data.
Make them feel seen, not processed.
Max 300 words.
"""

    return _call_groq(prompt, user_id, "monthly_report")


# ─── EXCUSE PATTERN ANALYSIS ────────────────────────────────────
def analyze_excuse_patterns(user_name: str, excuse_list: list, user_id: int) -> dict:
    """
    Analyzes excuse phrases collected over 30 days
    and identifies root causes and confrontation statements.
    """

    prompt = f"""
Analyze these excuse phrases collected over 30 days
from {user_name}'s journal entries:

Excuses: {json.dumps(excuse_list)}

Identify:
1. Top 3 recurring excuse themes
2. What root cause each theme suggests
3. One honest confrontation statement per theme

Return JSON ONLY:
{{
  "patterns": [
    {{
      "theme": "theme name",
      "frequency": number,
      "root_cause": "what this really means",
      "confrontation": "what coach should say"
    }}
  ]
}}
"""

    raw = _call_groq(prompt, user_id, "excuse_analysis")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"patterns": []}


# ─── WEEKLY PERSONA CARD ────────────────────────────────────────
def generate_weekly_persona(
    user_name: str,
    week_summary: dict,
    user_id: int,
) -> dict:
    """
    Generate a weekly persona card with an AI-assigned persona name.
    """

    prompt = f"""
Based on this week's data for {user_name}, generate a weekly persona card.

Week data: {json.dumps(week_summary, default=str)}

Return JSON ONLY:
{{
  "persona_name": "A creative 2-3 word persona title based on behavior",
  "coach_says": "One motivational line from the coach"
}}

Persona name examples:
- "The Determined Grinder" (high effort, some misses)
- "The Silent Warrior" (low mood but kept going)
- "The Comeback Kid" (recovered from bad start)
- "The Flow State" (everything clicked)
- "The Honest Rester" (low output but self-aware)
"""

    raw = _call_groq(prompt, user_id, "weekly_persona")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"persona_name": "The Evolving Self", "coach_says": "Keep showing up."}


# ─── PRIVATE HELPERS ─────────────────────────────────────────────
def _get_rag_context(user_id: int, query: str) -> str:
    """Fetch relevant memories via semantic search."""
    if is_circuit_open("jina"):
        logger.warning("[CIRCUIT OPEN] Vector search unavailable")
        return "No memory context available."

    try:
        with SessionLocal() as db:
            memories = semantic_recall(db, user_id, query, limit=3)
        record_success("jina")
        return "\n".join(f"- {m}" for m in memories) if memories else "No relevant memories found."
    except Exception as e:
        record_failure("jina")
        logger.error(f"[JINA ERROR] {e}")
        return "Memory retrieval failed."


def _call_groq(prompt: str, user_id: int, context: str) -> str:
    """Shared GROQ call with circuit breaker and error handling."""
    if is_circuit_open("groq"):
        logger.warning(f"[CIRCUIT OPEN] Groq unavailable for {context}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable.")

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        record_success("groq")
        raw = response.choices[0].message.content.strip()
        logger.info(f"[REFLECTA AI] {context} generated for user {user_id}")
        return raw

    except Exception as e:
        record_failure("groq")
        logger.error(f"[GROQ ERROR] {context}: {e}")
        raise HTTPException(status_code=503, detail="AI service error. Please retry later.")
