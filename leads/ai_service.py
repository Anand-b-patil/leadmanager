import json
import re

from django.conf import settings


def _import_gemini():
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    return genai


def _get_model():
    genai = _import_gemini()
    if genai is None or not settings.GEMINI_API_KEY:
        return None

    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-2.5-flash")


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in response.")
    return json.loads(match.group(0))


def _heuristic_score_lead(lead):
    score = 50
    reasons = []

    if lead.company.strip():
        score += 8
        reasons.append("company identified")
    if lead.job_title.strip():
        score += 10
        reasons.append("decision-maker context available")
    if lead.website.strip():
        score += 8
        reasons.append("website provided")
    if lead.phone.strip():
        score += 5
        reasons.append("direct contact data present")
    if lead.notes_summary.strip():
        score += 7
        reasons.append("lead notes add context")

    industry = lead.industry.strip().lower()
    if industry in {"saas", "software", "technology", "finance", "healthcare", "manufacturing"}:
        score += 7
        reasons.append("clear business segment")
    elif industry:
        score += 3
        reasons.append("industry captured")

    priority_bonus = {
        "high": 10,
        "medium": 4,
        "low": -4,
    }
    score += priority_bonus.get(lead.priority, 0)

    if lead.source.strip():
        score += 5
        reasons.append("source recorded")
    if lead.email and "@" in lead.email and not any(domain in lead.email.lower() for domain in ("gmail.", "yahoo.", "hotmail.", "outlook.")):
        score += 8
        reasons.append("business email detected")

    score = max(0, min(100, score))
    reason = ", ".join(reasons[:3]) if reasons else "basic profile information available"
    return score, f"Heuristic score based on {reason}."


def score_lead(lead):
    model = _get_model()
    fallback_score, fallback_reason = _heuristic_score_lead(lead)

    if model is None:
        return fallback_score, fallback_reason

    prompt = f"""
You are a B2B sales assistant. Score the following lead from 0 to 100.
Respond with valid JSON only using this schema:
{{"score": <integer>, "reason": "<short explanation>"}}

Lead details:
- Name: {lead.name}
- Email: {lead.email}
- Company: {lead.company}
- Industry: {lead.industry}

Scoring guidance:
- Higher scores for clear business fit, professional context, and likely buying intent.
- Keep the reason under 45 words.
""".strip()

    try:
        response = model.generate_content(prompt)
        payload = _extract_json(response.text)
        score = max(0, min(100, int(payload.get("score", fallback_score))))
        reason = str(payload.get("reason", fallback_reason)).strip() or fallback_reason
        return score, reason
    except Exception:
        return fallback_score, fallback_reason


def generate_outreach_email(lead):
    model = _get_model()
    fallback_email = (
        f"Subject: Helping {lead.company} improve lead follow-up\n\n"
        f"Hi {lead.name},\n\n"
        f"I noticed your work in the {lead.industry} space and wanted to reach out. "
        f"Our platform helps teams like {lead.company} organize leads, prioritize follow-up, "
        "and turn more opportunities into conversations.\n\n"
        "If you're open to it, I'd be glad to share a short walkthrough.\n\n"
        "Best regards,\nYour Sales Team"
    )

    if model is None:
        return fallback_email

    prompt = f"""
You are an SDR writing a concise professional cold email.
Write a tailored outreach email for this lead.

Lead details:
- Name: {lead.name}
- Email: {lead.email}
- Company: {lead.company}
- Industry: {lead.industry}

Requirements:
- Include a compelling subject line.
- Keep the email under 180 words.
- Make it specific, polite, and conversion-focused.
- Return plain text only, no markdown fences.
""".strip()

    try:
        response = model.generate_content(prompt)
        generated_email = response.text.strip()
        return generated_email or fallback_email
    except Exception:
        return fallback_email
