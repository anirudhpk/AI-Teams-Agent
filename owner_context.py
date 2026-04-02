from db import get_conn
from graph_identity import get_owner_profile, get_owner_self_chat_id

def resolve_owner_context(user_id):
    profile = get_owner_profile(user_id)
    owner_id = profile["id"]

    chat_id = get_owner_self_chat_id(user_id)
    if not chat_id:
        raise RuntimeError("Could not find owner self chat")

    with get_conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO owner_context
            (owner_id, bot_chat_id)
            VALUES (?, ?)
        """, (owner_id, chat_id))
        c.commit()

    return owner_id, chat_id

def get_owner_context():
    with get_conn() as c:
        row = c.execute(
            "SELECT owner_id, bot_chat_id FROM owner_context LIMIT 1"
        ).fetchone()

    if not row:
        return None, None

    return row