import re

TERMINAL_OWNER_REPLIES = [
    "thanks", "thank you", "ok", "okay", "got it", "noted", "👍", "🙏"
]

IGNORE_MESSAGE_PATTERNS = [
    r"^thanks\b",
    r"^thank you\b",
    r"^ok\b",
    r"^welcome\b",
    r"^fyi\b",
    r"^noted\b",
]

ACTION_REQUIRED_PATTERNS = [
    r"\?",
    r"can you",
    r"please",
    r"status",
    r"update",
    r"eta",
    r"need",
    r"request",
    r"approve",
    r"share",
    r"when",
]

def is_terminal_owner_reply(text: str) -> bool:
    t = text.lower().strip()
    return t in TERMINAL_OWNER_REPLIES

def should_ignore_message(text: str) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t) for p in IGNORE_MESSAGE_PATTERNS)

def needs_action(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in ACTION_REQUIRED_PATTERNS)