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

def generate_daily_motivation(context: dict, user_id: int) -> str:
    memory = semantic_search(
        user_id,
        query="recent struggles and motivation"
    )

    with SessionLocal() as db:
        profile = db.get(AIBehaviorProfile, user_id)

    tone = "calm and supportive"
    style = ""

    if profile:
        if profile.prefers_encouraging:
            tone = "warm, empathetic, and reassuring"
        if profile.prefers_actionable:
            style = "Provide 1-2 concrete, simple actions."

    prompt = f"""
You are a {tone} personal coach.
{style}

User memory:
{memory}

User context:
{context}

Rules:
- Never ask questions
- No clichés
- No generic advice
- Max 3 lines
- Be human and practical
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    logger.info(f"[AI MEMORY] {memory}")

    return response.choices[0].message.content.strip()


# -------- MONTHLY IN-DEPTH REVIEW --------

def generate_monthly_review(summary: dict, user_id: int) -> dict:
    memory = semantic_search(
        user_id=user_id,
        query="previous productivity patterns and improvements"
    )

    prompt = f"""
You are a behavioral analyst AI.

STRICT RULES:
- Return ONLY valid JSON
- No markdown
- No explanations
- No fractions (use decimals only)
- Follow schema exactly

SCHEMA:
{{
  "patterns": "string",
  "root_causes": "string",
  "recommendations": ["string", "string", "string"],
  "notable": "string"
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
            temperature=0.3
        )

        ai_text = response.choices[0].message.content

        cleaned = extract_json(ai_text)
        cleaned = normalize_numbers(cleaned)

        review_dict = safe_json_load(cleaned)

        if not review_dict:
            raise ValueError("Empty or invalid AI JSON")

        # ---- Schema enforcement ----
        review_dict.setdefault("patterns", "")
        review_dict.setdefault("root_causes", "")
        review_dict.setdefault("notable", "")
        review_dict.setdefault("recommendations", [])

        if not isinstance(review_dict["recommendations"], list):
            review_dict["recommendations"] = []

        review_dict["recommendations"] = review_dict["recommendations"][:3]

        return review_dict

    except Exception as e:
        logger.error(
            f"[MONTHLY AI REVIEW] Generation failed for user {user_id}: {e}"
        )

    # ---- SAFE FALLBACK ----
    return {
        "patterns": "Insufficient data to detect strong patterns.",
        "root_causes": "Monthly data volume or consistency was too low.",
        "recommendations": ["Continue tracking activities consistently next month."],
        "notable": ""
    }