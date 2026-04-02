import requests
from db import get_conn

from token_store import get_token

def fetch_message(chat_id, message_id, user_id):
    token = get_token(user_id)
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    return r.json()

def send_user_message(chat_id, user_id, text):
    token = get_token(user_id)
    requests.post(
        f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"body": {"contentType": "text", "content": text}}
    )

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

def get_token(user_id):
    with get_conn() as c:
        row = c.execute(
            "SELECT access_token FROM tokens WHERE user_id=?",
            (user_id,)
        ).fetchone()
    return row[0] if row else None


def fetch_message(chat_id, message_id, user_id):
    token = get_token(user_id)
    r = requests.get(
        f"{GRAPH_BASE}/chats/{chat_id}/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    return r.json()


def send_message(chat_id, user_id, text):
    token = get_token(user_id)
    requests.post(
        f"{GRAPH_BASE}/chats/{chat_id}/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "body": {
                "contentType": "html",
                "content": text
            }
        }
    )

def fetch_unread_emails(user_id, max_count=5):
    token = get_token(user_id)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url = (
        "https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages"
        "?$filter=isRead eq false"
        "&$top={}"
        "&$select=subject,from,bodyPreview,body,toRecipients"
    ).format(max_count)     

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    return r.json().get("value", [])