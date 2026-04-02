import os
import json
import sqlite3
import logging
from dotenv import load_dotenv

from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity, ActivityTypes

# ------------------ SETUP ------------------

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

APP_ID = os.getenv("MICROSOFT_APP_ID")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD")
PORT = int(os.getenv("PORT", 3978))

settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
adapter = BotFrameworkAdapter(settings)

DB_FILE = "bot.db"

# ------------------ DATABASE ------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            user_id TEXT PRIMARY KEY,
            conversation_reference TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            user_id TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS instructions (
            user_id TEXT PRIMARY KEY,
            instruction TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_conversation_reference(user_id, reference):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO conversations VALUES (?, ?)",
        (user_id, json.dumps(reference)),
    )
    conn.commit()
    conn.close()


def get_conversation_reference(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT conversation_reference FROM conversations WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def set_bot_state(user_id, enabled: bool):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bot_state VALUES (?, ?)",
        (user_id, int(enabled)),
    )
    conn.commit()
    conn.close()


def is_bot_enabled(user_id) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT enabled FROM bot_state WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


def save_instruction(user_id, instruction: str):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO instructions VALUES (?, ?)",
        (user_id, instruction),
    )
    conn.commit()
    conn.close()


def get_instruction(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT instruction FROM instructions WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# ------------------ BOT LOGIC ------------------

async def handle_message(turn_context: TurnContext):
    activity = turn_context.activity
    user_id = activity.from_property.id
    text = (activity.text or "").strip().lower()

    # Save conversation reference
    reference = TurnContext.get_conversation_reference(activity)
    save_conversation_reference(user_id, reference)

    if text == "bot on":
        set_bot_state(user_id, True)
        await turn_context.send_activity("🤖 Bot mode is ON.")
        return

    if text == "bot off":
        set_bot_state(user_id, False)
        await turn_context.send_activity("🛑 Bot mode is OFF.")
        return

    if text.startswith("instruction:"):
        instruction = text.replace("instruction:", "").strip()
        save_instruction(user_id, instruction)
        await turn_context.send_activity("📌 Instruction saved.")
        return

    # Auto-reply logic
    if is_bot_enabled(user_id):
        instruction = get_instruction(user_id)
        if instruction:
            await turn_context.send_activity(f"🤖 Auto-reply:\n{instruction}")
        else:
            await turn_context.send_activity("🤖 Bot is ON but no instruction is set.")

# ------------------ HTTP HANDLER ------------------

async def messages(req: web.Request) -> web.Response:
    if "application/json" not in req.headers.get("Content-Type", ""):
        return web.Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def logic(turn_context: TurnContext):
        if turn_context.activity.type == ActivityTypes.message:
            await handle_message(turn_context)

    try:
        await adapter.process_activity(activity, auth_header, logic)
        return web.Response(status=200)
    except Exception as e:
        logger.exception("Processing error")
        return web.Response(status=500, text=str(e))

# ------------------ START APP ------------------

init_db()
app = web.Application()
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    logger.info("Starting bot...")
    web.run_app(app, port=PORT)