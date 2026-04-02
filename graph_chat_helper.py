import requests
from graph_sender import get_token
import os

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
BOT_APP_ID = os.getenv("BOT_APP_ID")

def get_owner_bot_dm_chat_id(owner_id):
    token = get_token(owner_id)

    r = requests.get(
        f"{GRAPH_BASE}/me/chats",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()

    chats = r.json().get("value", [])

    for chat in chats:
        if chat.get("chatType") != "oneOnOne":
            continue

        chat_id = chat["id"]

        # inspect members
        members = requests.get(
            f"{GRAPH_BASE}/chats/{chat_id}/members",
            headers={"Authorization": f"Bearer {token}"}
        ).json().get("value", [])

        for m in members:
            app = m.get("application")
            if app and app.get("id") == BOT_APP_ID:
                return chat_id

    return None