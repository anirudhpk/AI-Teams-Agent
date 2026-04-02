import sqlite3
import time

DB_FILE = "app.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            user_upn TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at INTEGER
        )
    """)
    conn.commit()
    conn.close()


def save_token(user_upn, access_token, refresh_token, expires_in):
    expires_at = int(time.time()) + int(expires_in) - 60  # safety buffer
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO tokens VALUES (?, ?, ?, ?)",
        (user_upn, access_token, refresh_token, expires_at),
    )
    conn.commit()
    conn.close()


def get_token(user_upn):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT access_token, expires_at FROM tokens WHERE user_id=?",
        (user_upn,),
    )
    row = cur.fetchone()
    conn.close()
    return row