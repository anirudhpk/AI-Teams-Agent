import re
import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from openai import APIConnectionError, RateLimitError, OpenAIError

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# -------------------------------------------------
# CORE SAFE LLM CALL
# -------------------------------------------------
def generate_reply(instruction: str, user_message: str) -> str:
    """
    Centralized, safe OpenAI call with retries + graceful failure.
    """

    prompt = f"""
System instruction:
{instruction}

User message:
{user_message}

Reply as instructed.
"""

    max_retries = 3
    base_delay = 1.5

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                timeout=30,
            )
            return resp.choices[0].message.content.strip()

        except (APIConnectionError, RateLimitError):
            if attempt == max_retries:
                return "⚠️ Temporary AI service issue. Please try again shortly."
            time.sleep(base_delay * attempt)

        except OpenAIError:
            return "⚠️ AI processing error. Please rephrase and try again."

        except Exception:
            return "⚠️ Unexpected error while generating response."


# -------------------------------------------------
# NLP: MEETING INTENT PARSER
# -------------------------------------------------
def parse_meeting_intent(text: str) -> dict:
    """
    Extract meeting intent.
    Returns PARTIAL results if info is missing.
    """

    prompt = f"""
Extract meeting details from the text below.

Return STRICT JSON with keys:
- attendees: list of email strings or null
- subject: string or null
- duration_minutes: integer or null
- time_windows: list of strings or empty list

Text:
{text}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You extract structured meeting intent."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        timeout=30,
    )

    raw = resp.choices[0].message.content.strip()
    return extract_json(raw)


# -------------------------------------------------
# EMAIL SUMMARIZATION (TOKEN-SAFE)
# -------------------------------------------------
def summarize_emails(emails: list[dict]) -> dict:
    """
    Summarize unread emails safely:
    - One-by-one summarization
    - Final aggregation
    - Prevents token overflow
    """

    individual_summaries = []

    for e in emails[:5]:  # HARD LIMIT
        email_text = f"""
Subject: {e.get("subject")}
From: {e.get("from", {}).get("emailAddress", {}).get("address")}
To: {[r["emailAddress"]["address"] for r in e.get("toRecipients", [])]}

Body:
{shrink(e.get("body", {}).get("content", ""))}
"""

        summary = generate_reply(
            instruction="""
You are an executive email assistant.

Summarize the email in 1–2 lines.
If action is required, clearly mention it.
""",
            user_message=email_text,
        )

        individual_summaries.append(summary)

    # Final grouping (small payload)
    final = generate_reply(
        instruction="""
Group the following summaries into:
1) action_required
2) fyi

Return STRICT JSON:
{
  "action_required": [
    { "summary": "...", "action": "..." }
  ],
  "fyi": [
    { "summary": "..." }
  ]
}
""",
        user_message="\n\n".join(individual_summaries),
    )

    return extract_json(final)


# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def extract_json(raw: str) -> dict:
    """
    Robust JSON extraction from LLM output.
    """

    if not raw:
        return {}

    # Remove ```json``` wrappers
    cleaned = re.sub(r"```(?:json)?", "", raw)
    cleaned = cleaned.strip("`\n ")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def shrink(text: str, limit: int = 800) -> str:
    return text[:limit] if text else ""

##--------------------------------------------------
## AI SUMMARY FOR TEAMS CHAT
##--------------------------------------------------
def summarize_messages(messages):
    combined = "\n".join(
        f"{m['from']}: {m['text']}" for m in messages
    )

    raw = generate_reply(
        "Summarize the following messages into short bullet points.",
        combined
    )

    # ✅ Convert AI output into bullet list safely
    bullets = [
        line.strip("•- ").strip()
        for line in raw.split("\n")
        if line.strip()
    ]

    return {
        "actionable": bullets,
        "fyi": []
    }