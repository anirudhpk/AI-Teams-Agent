import os
import logging

from aiohttp import web
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity, ActivityTypes
from dotenv import load_dotenv

from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

APP_ID = os.getenv("MICROSOFT_APP_ID", "")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD", "")
PORT = int(os.getenv("PORT", 3978))
CROSOFT_TENANT_ID = os.getenv("CROSOFT_TENANT_ID")

if not APP_ID or not APP_PASSWORD:
    logger.warning("MICROSOFT_APP_ID or MICROSOFT_APP_PASSWORD not set in environment!")

# OpenAI client (for openai>=1.0.0)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Bot Framework adapter
settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD,CROSOFT_TENANT_ID)
adapter = BotFrameworkAdapter(settings)


async def call_openai(user_text: str) -> str:
    """Call OpenAI to generate a reply."""
    if not client:
        return "OpenAI API key not configured."

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # or another model you have access to
            messages=[
                {"role": "system", "content": "You are a helpful assistant in Microsoft Teams."},
                {"role": "user", "content": user_text},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("OpenAI error:")
        return "Sorry, I had trouble contacting the AI service."


async def messages(request: web.Request) -> web.Response:
    """Main Handler for /api/messages – MUST return a web.Response."""
    if "application/json" not in request.headers.get("Content-Type", ""):
        return web.Response(status=415, text="Content-Type must be application/json")

    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def logic(turn_context: TurnContext):
        if turn_context.activity.type == ActivityTypes.message:
            user_text = (turn_context.activity.text or "").strip()
            if not user_text:
                await turn_context.send_activity("I didn't receive any text.")
                return

            # Call OpenAI and send reply
            reply_text = await call_openai(user_text)
            await turn_context.send_activity(reply_text)
        else:
            # Handle non-message activities if needed
            await turn_context.send_activity(f"Activity of type {turn_context.activity.type} received.")

    try:
        # IMPORTANT: we await this AND then return an explicit web.Response
        await adapter.process_activity(activity, auth_header, logic)
        return web.Response(status=200)
    except Exception as e:
        logger.exception("Error processing activity:")
        return web.Response(status=500, text=str(e))


app = web.Application()
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    logger.info(f"Starting app on port {PORT} with APP_ID={APP_ID}")
    web.run_app(app, port=PORT)
