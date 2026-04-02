from fastapi import FastAPI, Request, Response
from bs4 import BeautifulSoup
import logging
import base64
import requests
import re

from db import init_db, get_conn
from graph_sender import (
    fetch_message,
    send_message,
    fetch_unread_emails,
    get_token
)
from ai_engine import generate_reply, parse_meeting_intent, summarize_emails
from meeting_scheduler import schedule_meeting
from sharepoint_access import grant_drive_item_access

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("graph_webhook")

init_db()
app = FastAPI()

OWNER_ID = "e1a9186a-95f7-4c66-a310-3dc324c6086a"

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def clean_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text().strip()

def extract_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [a["href"] for a in soup.find_all("a", href=True)]

def is_access_request(text: str, html: str) -> bool:
    if "access" in text.lower():
        return True
    if extract_links(html):
        return True
    return False

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

def sharepoint_url_to_drive_item(user_id: str, file_url: str):
    token = get_token(user_id)

    encoded = base64.b64encode(file_url.encode("utf-8")).decode("utf-8")
    encoded = encoded.rstrip("=").replace("+", "-").replace("/", "_")
    share_id = f"u!{encoded}"

    url = f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

# -------------------------------------------------
# Webhook
# -------------------------------------------------
@app.post("/graph/webhook")
async def webhook(req: Request):

    validation_token = req.query_params.get("validationToken")
    if validation_token:
        return Response(content=validation_token, media_type="text/plain")

    data = await req.json()

    for n in data.get("value", []):

        resource = n.get("resource", "")
        message_id = n.get("resourceData", {}).get("id")

        if not resource or not message_id:
            continue

        if already_processed(message_id):
            continue

        mark_processed(message_id)

        chat_id = resource.split("/")[0].split("('")[1].split("')")[0]
        msg = fetch_message(chat_id, message_id, OWNER_ID)

        sender_id = msg.get("from", {}).get("user", {}).get("id")
        body = msg.get("body", {}).get("content")

        if not sender_id or not body:
            continue

        text = clean_text(body)
        lower = text.lower()
        enabled, instruction = get_bot_state()

        log.info(f"Message from {sender_id}: {text}")

        # -------------------------------------------------
        # OWNER COMMANDS
        # -------------------------------------------------
        if sender_id == OWNER_ID:

            if lower == "bot on":
                with get_conn() as c:
                    c.execute("INSERT OR REPLACE INTO bot_state VALUES (?,1)", (OWNER_ID,))
                    c.commit()
                send_message(chat_id, OWNER_ID, "🤖 Bot enabled")
                continue

            if lower == "bot off":
                with get_conn() as c:
                    c.execute("INSERT OR REPLACE INTO bot_state VALUES (?,0)", (OWNER_ID,))
                    c.commit()
                send_message(chat_id, OWNER_ID, "🛑 Bot disabled")
                continue

            if lower.startswith("instruction:"):
                with get_conn() as c:
                    c.execute(
                        "INSERT OR REPLACE INTO instructions VALUES (?,?)",
                        (OWNER_ID, text[len("instruction:"):].strip())
                    )
                    c.commit()
                send_message(chat_id, OWNER_ID, "✅ Instruction saved")
                continue

        # -------------------------------------------------
        # OWNER – MEETING SCHEDULER
        # -------------------------------------------------
        if sender_id == OWNER_ID and lower.startswith("schedule"):

            parsed = parse_meeting_intent(text) or {}

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
                    "To schedule the meeting, I still need:\n- " + "\n- ".join(missing)
                )
                continue

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
        # OWNER – EMAIL SUMMARY
        # -------------------------------------------------
        if sender_id == OWNER_ID and lower == "summary":

            emails = fetch_unread_emails(OWNER_ID, max_count=5)

            if not emails:
                send_message(chat_id, OWNER_ID, "📭 You have no unread emails.")
                continue

            summary = summarize_emails(emails)

            reply = "📌 <b>Emails requiring your action</b><br><br>"

            for e in summary.get("action_required", []):
                reply += f"🔹 {e.get('summary','')}<br>"
                if e.get("action"):
                    reply += f"&nbsp;&nbsp;👉 <i>{e.get('action')}</i><br>"
                reply += "<br>"

            reply += "<br>📨 <b>Other unread emails (FYI)</b><br><br>"

            for e in summary.get("fyi", []):
                reply += f"🔸 {e.get('summary','')}<br><br>"

            send_message(chat_id, OWNER_ID, reply)
            continue

        # -------------------------------------------------
        # NON-OWNER – ACCESS REQUEST (HIGH PRIORITY)
        # -------------------------------------------------
        if sender_id != OWNER_ID and is_access_request(text, body):

            links = extract_links(body)
            if not links:
                continue

            file_url = links[0]
            item = sharepoint_url_to_drive_item(OWNER_ID, file_url)

            with get_conn() as c:
                row = c.execute(
                    """
                    SELECT permission FROM preapproved_files
                    WHERE owner_id=? AND drive_item_id=?
                    """,
                    (OWNER_ID, item["id"])
                ).fetchone()

            if row:
                permission = row[0]
                grant_drive_item_access(
                    user_id=OWNER_ID,
                    drive_id=item["parentReference"]["driveId"],
                    drive_item_id=item["id"],
                    target_email="ramya@callaider.onmicrosoft.com",
                    role="read"
                )

                send_message(
                    chat_id,
                    OWNER_ID,
                    "🤖 <b>Anirudh’s AI assistant</b><br><br>"
                    "✅ You now have access to the requested file."
                )
            else:
                send_message(
                    chat_id,
                    OWNER_ID,
                    "❌ This file has not been pre-approved for sharing."
                )

            continue  # 🚨 prevents auto-reply

        # -------------------------------------------------
        # NON-OWNER – AUTO REPLY (FALLBACK ONLY)
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

    return Response(status_code=202)