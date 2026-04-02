import os
import sqlite3
from aiohttp import web
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity, ActivityTypes
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("MICROSOFT_APP_ID")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD")
TENANT_ID = os.getenv("CROSOFT_TENANT_ID")
PORT = 3978

adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD, TENANT_ID)
)

DB = "messages.db"


def get_db():
    return sqlite3.connect(DB)


def set_bot_state(user_id, enabled=None, instruction=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO bot_state (user_id, enabled, instruction) VALUES (?, 0, '')",
        (user_id,)
    )

    if enabled is not None:
        cur.execute("UPDATE bot_state SET enabled=? WHERE user_id=?", (enabled, user_id))

    if instruction is not None:
        cur.execute("UPDATE bot_state SET instruction=? WHERE user_id=?", (instruction, user_id))

    conn.commit()
    conn.close()


async def messages(req):
    body = await req.json()
    activity = Activity().deserialize(body)
    auth = req.headers.get("Authorization", "")

    async def logic(ctx: TurnContext):
        if ctx.activity.type != ActivityTypes.message:
            return

        user_id = ctx.activity.from_property.id
        text = (ctx.activity.text or "").strip().lower()

        if text == "bot on":
            set_bot_state(user_id, enabled=1)
            await ctx.send_activity("🤖 Bot is ON. I will respond on your behalf.")
            return

        if text == "bot off":
            set_bot_state(user_id, enabled=0)
            await ctx.send_activity("🛑 Bot is OFF.")
            return

        # Any other message from YOU is instruction
        set_bot_state(user_id, instruction=ctx.activity.text)
        await ctx.send_activity("📝 Instruction saved. I will use this to reply to others.")

    await adapter.process_activity(activity, auth, logic)
    return web.Response(status=200)


app = web.Application()
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    web.run_app(app, port=PORT)