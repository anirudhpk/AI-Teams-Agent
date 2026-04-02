# graph_reader.py
import requests
from datetime import datetime
from graph_sender import get_token

GRAPH = "https://graph.microsoft.com/v1.0"


def get_one_on_one_chats(user_id):
    token = get_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(
        f"{GRAPH}/me/chats?$select=id,chatType",
        headers=headers
    )
    r.raise_for_status()

    return [
        c for c in r.json()["value"]
        if c.get("chatType") == "oneOnOne"
    ]


def get_recent_messages(chat_id, user_id, cutoff_dt):
    """
    Fetch messages in reverse chronological order
    Stop as soon as message is older than cutoff
    """
    token = get_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    url = (
        f"{GRAPH}/chats/{chat_id}/messages"
        "?$orderby=createdDateTime desc"
        "&$top=20"
    )

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    messages = []
    for m in r.json()["value"]:
        msg_time = datetime.fromisoformat(
            m["createdDateTime"].replace("Z", "+00:00")
        )

        if msg_time < cutoff_dt:
            break  # 🔥 EARLY EXIT

        messages.append(m)

    return messages