import requests
from token_store import get_token

def get_chat_members(chat_id, user_id):
    token = get_token(user_id)
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/chats/{chat_id}/members",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    return r.json()["value"]