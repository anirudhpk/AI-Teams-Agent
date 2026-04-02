from fastapi import FastAPI, Request, Response
from bs4 import BeautifulSoup
import logging

from db import init_db, get_conn
from graph_sender import fetch_message, send_message, fetch_unread_emails
from ai_engine import generate_reply, parse_meeting_intent, summarize_emails
from meeting_scheduler import schedule_meeting

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("graph_webhook")

init_db()
app = FastAPI()

OWNER_ID = "e1a9186a-95f7-4c66-a310-3dc324c6086a"

def already_processed(message_id: str) -> bool:
    with get_conn() as c:
        row = c.execute(
            "SELECT 1 FROM processed_messages WHERE message_id=?",
            (message_id,)
        ).fetchone()
        return row is not None


def mark_processed(message_id: str):
    with get_conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO processed_messages VALUES (?)",
            (message_id,)
        )
        c.commit()

def clean_text(html):
    return BeautifulSoup(html, "html.parser").get_text().strip()


def get_bot_state():
    with get_conn() as c:
        enabled = c.execute(
            "SELECT enabled FROM bot_state WHERE user_id=?",
            (OWNER_ID,)
        ).fetchone()
        instruction = c.execute(
            "SELECT instruction FROM instructions WHERE user_id=?",
            (OWNER_ID,)
        ).fetchone()

    return (
        enabled and enabled[0] == 1,
        instruction[0] if instruction else None
    )


@app.post("/graph/webhook")
async def webhook(req: Request):

    # 🔹 Subscription validation
    validation_token = req.query_params.get("validationToken")
    if validation_token:
        return Response(content=validation_token, media_type="text/plain")

    data = await req.json()

    for n in data.get("value", []):

        resource = n.get("resource", "")
        message_id = n.get("resourceData", {}).get("id")

        if already_processed(message_id):
            log.info(f"Skipping duplicate message {message_id}")
            continue

        mark_processed(message_id)

        if not resource or not message_id:
            continue

        # ✅ extract chat_id
        chat_id = resource.split("/")[0].split("('")[1].split("')")[0]

        # ✅ FETCH FULL MESSAGE 
        msg = fetch_message(chat_id, message_id, OWNER_ID)

        sender_id = msg.get("from", {}).get("user", {}).get("id")
        body = msg.get("body", {}).get("content")

        if not sender_id or not body:
            continue

        text = clean_text(body)
        log.info(f"Message from {sender_id}: {text}")

        enabled, instruction = get_bot_state()

        # -------------------------------------------------
        # OWNER COMMANDS
        # -------------------------------------------------
        if sender_id == OWNER_ID:
            lower = text.lower()

            if lower == "bot on":
                with get_conn() as c:
                    c.execute(
                        "INSERT OR REPLACE INTO bot_state VALUES (?,1)",
                        (OWNER_ID,)
                    )
                    c.commit()
                log.info("BOT ENABLED")
                continue

            if lower == "bot off":
                with get_conn() as c:
                    c.execute(
                        "INSERT OR REPLACE INTO bot_state VALUES (?,0)",
                        (OWNER_ID,)
                    )
                    c.commit()
                log.info("BOT DISABLED")
                continue

            if lower.startswith("instruction:"):
                with get_conn() as c:
                    c.execute(
                        "INSERT OR REPLACE INTO instructions VALUES (?,?)",
                        (OWNER_ID, text[len("instruction:"):].strip())
                    )
                    c.commit()
                log.info("Instruction stored")
                continue

        # -------------------------------------------------
        # OWNER – NLP MEETING FLOW
        # -------------------------------------------------
        
        if sender_id == OWNER_ID and lower.startswith("schedule"):

            parsed = parse_meeting_intent(text) or {}

            print(parsed)

            missing = []
            required = {
                "subject": parsed.get("subject"),
                "attendees": parsed.get("attendees"),
                "duration_minutes": parsed.get("duration_minutes"),
                "time_windows": parsed.get("time_windows"),
            }

            missing = [k for k, v in required.items() if not v]

            if missing:
                send_message(
                chat_id,
                OWNER_ID,
                "To schedule the meeting, I still need:\n- "
                + "\n- ".join(missing)
                )
                continue

            # All info present → create draft
            
            result = schedule_meeting(
                user_id=OWNER_ID,
                attendees=parsed["attendees"],
                subject=parsed["subject"],
                duration_minutes=parsed["duration_minutes"],
                time_windows=parsed["time_windows"]
            )

            send_message(chat_id, OWNER_ID, result)
            continue

        # -------------------------------------------------
        # AUTO REPLY (NON-OWNER)
        # -------------------------------------------------
        if enabled and instruction and sender_id != OWNER_ID:
            reply = generate_reply(
                instruction + "\nAlways refer to Anirudh in third person.",
                text
            )
            send_message(
                chat_id,
                OWNER_ID,
                f"From Anirudh’s AI assistant:\n\n{reply}"
            )
        # -------------------------------------------------
        # EMAIL SUMMARY
        # -------------------------------------------------
        if sender_id == OWNER_ID and lower == "summary":
            emails = fetch_unread_emails(OWNER_ID, max_count=10)

            if not emails:
                send_message(
                    chat_id,
                    OWNER_ID,
                    "📭 You have no unread emails."
                )
                continue

            summary = summarize_emails(emails)

            reply = "📌 **Emails requiring your action**\n\n"
            
            for e in summary.get("action_required", []):
                reply += f"• {e.get('summary', '')}\n"
                if e.get("action"):
                    reply += f"  👉 Action: {e.get('action')}\n"
            
            for e in summary.get("fyi", []):
                reply += f"• {e.get('summary', '')}\n"

            reply += "\n📨 **Other unread emails (FYI)**\n\n"
            for e in summary.get("fyi", []):
                reply += f"• **{e['subject']}** – {e['summary']}\n"

            send_message(chat_id, OWNER_ID, reply)
            continue

    return Response(status_code=202)