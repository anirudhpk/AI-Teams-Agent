import sqlite3
import re

DB = "messages.db"

def get_conn():
    return sqlite3.connect(DB)

# ---------- BOT MODE ----------
def set_bot_mode(user_id: str, enabled: bool):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_mode (
            user_id TEXT PRIMARY KEY,
            enabled INTEGER
        )
    """)
    cur.execute("""
        INSERT INTO bot_mode (user_id, enabled)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled
    """, (user_id, int(enabled)))
    conn.commit()
    conn.close()

def is_bot_enabled(user_id: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT enabled FROM bot_mode WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

# ---------- INSTRUCTIONS ----------
def save_instruction(user_id: str, pattern: str, response: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS instructions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            pattern TEXT,
            response TEXT
        )
    """)
    cur.execute("""
        INSERT INTO instructions (user_id, pattern, response)
        VALUES (?, ?, ?)
    """, (user_id, pattern.lower(), response))
    conn.commit()
    conn.close()

def match_instruction(user_id: str, incoming_text: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT pattern, response
        FROM instructions
        WHERE user_id=?
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    text = incoming_text.lower()
    for pattern, response in rows:
        if re.search(pattern, text):
            return response
    return None