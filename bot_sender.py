import os
import logging
from dotenv import load_dotenv

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity, ActivityTypes

load_dotenv()

settings = BotFrameworkAdapterSettings(
    app_id=os.getenv("BOT_APP_ID"),
    app_password=os.getenv("BOT_APP_PASSWORD")
)

adapter = BotFrameworkAdapter(settings)

async def send_bot_message(conversation_reference, text):
    async def logic(turn_context):
        await turn_context.send_activity(text)

    await adapter.continue_conversation(
        conversation_reference,
        logic,
        os.getenv("BOT_APP_ID")
    )

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ConversationReference,
)

load_dotenv()
logger = logging.getLogger(__name__)

APP_ID = os.getenv("MICROSOFT_APP_ID")
APP_PASSWORD = os.getenv("MICROSOFT_APP_PASSWORD")

settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
adapter = BotFrameworkAdapter(settings)


async def send_bot_message(conversation_reference: ConversationReference, text: str):
    """
    Send a proactive bot message using a ConversationReference
    """

    async def logic(turn_context: TurnContext):
        await turn_context.send_activity(text)

    try:
        await adapter.continue_conversation(
            conversation_reference,
            logic,
            APP_ID,   # REQUIRED
        )
        logger.info("BOT_REPLY_SENT")
    except Exception:
        logger.exception("BOT_REPLY_FAILED")