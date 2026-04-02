# unreplied_scanner.py
from datetime import datetime, timedelta, timezone
from graph_reader import get_one_on_one_chats, get_recent_messages
from filters import should_ignore_message, needs_action


def scan_unreplied_messages(owner_id, hours):
    

    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)

    chats = get_one_on_one_chats(owner_id)
    actionable = []

    for chat in chats:
        chat_id = chat["id"]

        messages = get_recent_messages(chat_id, owner_id, cutoff_dt)

        if not messages:
            continue

        # Messages are newest → oldest
        owner_has_replied = False

        for m in messages:
            sender_id = m["from"]["user"]["id"]
            text = m["body"]["content"]

            if sender_id == owner_id:
                owner_has_replied = True
                break  # owner already replied → skip chat

            if should_ignore_message(text):
                continue

            if needs_action(text):
                actionable.append({
                    "chat_id": chat_id,
                    "from": m["from"]["user"]["displayName"],
                    "text": text,
                    "time": m["createdDateTime"]
                })
                break  # one actionable per chat is enough

        if owner_has_replied:
            continue

    return actionable