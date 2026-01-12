import json
import logging
from groq import Groq
from app.config import GROQ_API_KEY

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = Groq(api_key=GROQ_API_KEY)

# -------- DAILY MOTIVATION --------

def generate_daily_motivation(context: dict) -> str:
    """
    Generates a short daily motivational message based on user context.
    Always returns a string; returns fallback if AI fails.
    """
    prompt = f"""
You are a calm, supportive personal coach.

User context (last few days):
{context}

Rules:
- Never ask questions
- No clichés
- Be specific to the user's data
- Never give generic advice
- The message must be uplifting and motivating
- Never judge or criticize
- Never ask why
- No toxic positivity
- No medical advice
- Max 2 lines
- Be practical and human
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()


# -------- MONTHLY IN-DEPTH REVIEW --------

def generate_monthly_review(summary: dict) -> dict:
    """
    Generate a structured monthly AI review for a user.
    Always returns a dict, even if AI fails.

    Returns a dict:
    {
        "patterns": str,
        "root_causes": str,
        "recommendations": [str, str, str],
        "notable": str
    }
    """
    prompt = f"""
You are a behavioral analyst AI.

User monthly timeline:
{summary}

Tasks:
1. Identify behavior patterns across work, study, sleep, mood, and goals.
2. Explain likely root causes for strong or weak patterns.
3. Suggest 3 realistic, actionable improvements for next month.
4. Highlight streaks or irregularities.

Rules:
- Be concise but thorough
- Avoid generic advice
- Base your analysis strictly on the data
- Be practical and human
- Return the output strictly as JSON with this structure:

{{
    "patterns": "...",
    "root_causes": "...",
    "recommendations": ["...", "...", "..."],
    "notable": "..."
}}
"""

    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}]
        )

        ai_text = response.choices[0].message.content.strip()

        # Try to clean common JSON issues
        ai_text_clean = ai_text.replace("\n", "").replace("'", '"')
        ai_text_clean = ai_text_clean.split("```")[0]  # remove code blocks if AI added them

        # Parse JSON safely
        review_dict = json.loads(ai_text_clean)

        # Ensure all expected keys exist
        expected_keys = ["patterns", "root_causes", "recommendations", "notable"]
        for key in expected_keys:
            if key not in review_dict:
                review_dict[key] = "" if key != "recommendations" else []

        # Limit recommendations to 4
        if review_dict["recommendations"] and len(review_dict["recommendations"]) > 4:
            review_dict["recommendations"] = review_dict["recommendations"][:4]

        return review_dict

    except json.JSONDecodeError:
        logger.warning(f"[MONTHLY AI REVIEW] AI returned invalid JSON: {ai_text}")
    except Exception as e:
        logger.error(f"[MONTHLY AI REVIEW] AI generation failed: {e}")

    # Fallback safe dict
    return {
        "patterns": "No patterns detected.",
        "root_causes": "Unable to determine.",
        "recommendations": ["Keep tracking your activities."],
        "notable": ""
    }