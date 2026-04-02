import requests
from graph_sender import get_token

def grant_drive_item_access(
    user_id: str,
    drive_id: str,
    drive_item_id: str,
    target_email: str,
    role: str
):
    token = get_token(user_id)

    # ✅ Normalize role
    role_map = {
        "view": "read",     # Teams language → Graph role
        "read": "read",
        "edit": "write",
        "write": "write"
    }

    graph_role = role_map.get(role.lower())
    if not graph_role:
        raise ValueError(f"Unsupported role: {role}")

    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{drive_item_id}/invite"

    payload = {
        "recipients": [
            {"email": target_email}
        ],
        "message": "Access granted by Anirudh’s AI assistant",
        "requireSignIn": True,
        "sendInvitation": True,
        "roles": [graph_role]
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, json=payload)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"{r.status_code} {r.text}")