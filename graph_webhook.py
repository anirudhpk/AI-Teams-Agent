from fastapi import FastAPI, Request, Response
from bs4 import BeautifulSoup
import logging
import base64
import requests
from owner_context import resolve_owner_context

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
from datetime import datetime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("graph_webhook")

init_db()
app = FastAPI()

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def clean_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text().strip()

def extract_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [a["href"] for a in soup.find_all("a", href=True)]

def is_access_request(text: str, html: str) -> bool:
    return "access" in text.lower() or bool(extract_links(html))

def already_processed(message_id: str) -> bool:
    with get_conn() as c:
        return c.execute(
            "SELECT 1 FROM processed_messages WHERE message_id=?",
            (message_id,)
        ).fetchone() is not None

def mark_processed(message_id: str):
    with get_conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO processed_messages VALUES (?)",
            (message_id,)
        )
        c.commit()

def get_bot_state(owner_id: str):
    with get_conn() as c:
        enabled = c.execute(
            "SELECT enabled FROM bot_state WHERE user_id=?",
            (owner_id,)
        ).fetchone()

        instruction = c.execute(
            "SELECT instruction FROM instructions WHERE user_id=?",
            (owner_id,)
        ).fetchone()

    return (
        enabled and enabled[0] == 1,
        instruction[0] if instruction else None
    )

def ensure_owner_context(owner_id: str, chat_id: str):
    """Stores owner DM chat safely if not already present"""
    with get_conn() as c:
        row = c.execute(
            "SELECT 1 FROM owner_context WHERE owner_id=?",
            (owner_id,)
        ).fetchone()

        if not row:
            c.execute(
                """
                INSERT INTO owner_context (owner_id, bot_chat_id)
                VALUES (?, ?)
                """,
                (owner_id, chat_id)
            )
            c.commit()
            log.info("✅ Owner context stored")

def sharepoint_url_to_drive_item(user_id: str, file_url: str):
    token = get_token(user_id)

    encoded = base64.b64encode(file_url.encode()).decode()
    encoded = encoded.rstrip("=").replace("+", "-").replace("/", "_")
    share_id = f"u!{encoded}"

    url = f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


# -------------------------------------------------
# Webhook
# -------------------------------------------------
@app.post("/graph/webhook")
async def webhook(req: Request):

    # 🔐 Graph validation
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

        try:
            chat_id = resource.split("/")[0].split("('")[1].split("')")[0]
        except Exception:
            continue

        # 🔐 Fetch full message using delegated token
        # (Owner ID resolved dynamically below)
        msg = None

        # TEMP fetch using ANY valid token – owner will be resolved after
        with get_conn() as c:
            row = c.execute("SELECT user_id FROM tokens LIMIT 1").fetchone()
        if not row:
            continue

        temp_user_id = row[0]
        msg = fetch_message(chat_id, message_id, temp_user_id)

        sender = msg.get("from", {}).get("user", {})
        sender_id = sender.get("id")
        sender_email = sender.get("userPrincipalName")

        body_html = msg.get("body", {}).get("content")
        if not sender_id or not body_html:
            continue

        text = clean_text(body_html)
        lower = text.lower()

        log.info(f"Message from {sender_id}: {text}")

        # -------------------------------------------------
        # OWNER RESOLUTION (DYNAMIC)
        # -------------------------------------------------
        owner_id = sender_id if lower.startswith(("bot on", "bot off", "instruction:", "summary", "schedule")) else None

        # If owner context already exists, trust DB
        with get_conn() as c:
            row = c.execute("SELECT owner_id FROM owner_context LIMIT 1").fetchone()
            if row:
                owner_id = row[0]

        if not owner_id:
            continue

        enabled, instruction = get_bot_state(owner_id)

        # -------------------------------------------------
        # OWNER COMMANDS
        # -------------------------------------------------
        if sender_id == owner_id:
            ensure_owner_context(owner_id, chat_id)
            resolve_owner_context(owner_id)

            if lower == "bot on":
                with get_conn() as c:
                    c.execute("INSERT OR REPLACE INTO bot_state VALUES (?,1)", (owner_id,))
                    c.commit()
                send_message(chat_id, owner_id, "🤖 Bot enabled")
                continue

            if lower == "bot off":
                with get_conn() as c:
                    c.execute("INSERT OR REPLACE INTO bot_state VALUES (?,0)", (owner_id,))
                    c.commit()
                send_message(chat_id, owner_id, "🛑 Bot disabled")
                continue

            if lower.startswith("instruction:"):
                with get_conn() as c:
                    c.execute(
                        "INSERT OR REPLACE INTO instructions VALUES (?,?)",
                        (owner_id, text[len("instruction:"):].strip())
                    )
                    c.commit()
                send_message(chat_id, owner_id, "✅ Instruction saved")
                continue

        # -------------------------------------------------
        # MEETING SCHEDULER
        # -------------------------------------------------
        if sender_id == owner_id and lower.startswith("schedule"):
            parsed = parse_meeting_intent(text) or {}

            missing = [
                k for k in ["subject", "attendees", "duration_minutes", "time_windows"]
                if not parsed.get(k)
            ]

            if missing:
                send_message(chat_id, owner_id, "Missing details:\n- " + "\n- ".join(missing))
                continue

            result = schedule_meeting(
                user_id=owner_id,
                attendees=parsed["attendees"],
                subject=parsed["subject"],
                duration_minutes=parsed["duration_minutes"],
                time_windows=parsed["time_windows"]
            )

            send_message(chat_id, owner_id, result)
            continue

        # -------------------------------------------------
        # EMAIL SUMMARY
        # -------------------------------------------------
        if sender_id == owner_id and lower == "summary":
            emails = fetch_unread_emails(owner_id, max_count=5)
            if not emails:
                send_message(chat_id, owner_id, "📭 No unread emails.")
                continue

            summary = summarize_emails(emails)
            reply = "<b>📌 Emails requiring action</b><br><br>"

            for e in summary.get("action_required", []):
                reply += f"🔹 {e.get('summary')}<br>"
                if e.get("action"):
                    reply += f"&nbsp;&nbsp;👉 <i>{e['action']}</i><br><br>"

            reply += "<br><b>📨 FYI emails</b><br><br>"
            for e in summary.get("fyi", []):
                reply += f"🔸 {e.get('summary')}<br><br>"

            send_message(chat_id, owner_id, reply)
            continue

        # -------------------------------------------------
        # FILE ACCESS REQUEST
        # -------------------------------------------------
        if sender_id != owner_id and is_access_request(text, body_html):
            links = extract_links(body_html)
            if not links:
                continue

            item = sharepoint_url_to_drive_item(owner_id, links[0])

            with get_conn() as c:
                row = c.execute(
                    """
                    SELECT permission FROM preapproved_files
                    WHERE owner_id=? AND drive_item_id=?
                    """,
                    (owner_id, item["id"])
                ).fetchone()

            if row and sender_email:
                grant_drive_item_access(
                    user_id=owner_id,
                    drive_id=item["parentReference"]["driveId"],
                    drive_item_id=item["id"],
                    target_email=sender_email,
                    role=row[0]
                )
                send_message(chat_id, owner_id, "✅ Access granted.")
            else:
                send_message(chat_id, owner_id, "❌ File not pre-approved.")
            continue

        # -------------------------------------------------
        # AUTO-REPLY (LAST RESORT)
        # -------------------------------------------------
        if enabled and instruction and sender_id != owner_id:
            reply = generate_reply(
                instruction + "\nAlways refer to Anirudh in third person.",
                text
            )
            send_message(
                chat_id,
                owner_id,
                f"From Anirudh’s AI assistant:<br><br>{reply}"
            )

    return Response(status_code=202)