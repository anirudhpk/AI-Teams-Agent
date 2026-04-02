import requests
from graph_sender import get_token

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

def get_owner_profile(user_id):
    token = get_token(user_id)
    r = requests.get(
        f"{GRAPH_BASE}/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    return r.json()

def get_owner_self_chat_id(user_id):
    token = get_token(user_id)

    r = requests.get(
        f"{GRAPH_BASE}/me/chats",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()

    chats = r.json().get("value", [])

    for chat in chats:
        if chat.get("chatType") != "oneOnOne":
            continue

        members = chat.get("members", [])
        member_ids = [m["userId"] for m in members if "userId" in m]

        # self chat → only one unique user id
        if len(set(member_ids)) == 1:
            return chat["id"]

    return None