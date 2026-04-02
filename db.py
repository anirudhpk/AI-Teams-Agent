import sqlite3

DB = "app.db"

def get_conn():
    return sqlite3.connect(DB)

def init_db():
    print("init_db_called")
    with get_conn() as c:
        cur = c.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            user_id TEXT PRIMARY KEY,
            access_token TEXT,
            expires_at INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            user_id TEXT PRIMARY KEY,
            enabled INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS instructions (
            user_id TEXT PRIMARY KEY,
            instruction TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_messages (
        message_id TEXT PRIMARY KEY
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS preapproved_files (
        owner_id TEXT,
        drive_item_id TEXT,
        permission TEXT, -- "view" | "edit"
        PRIMARY KEY (owner_id, drive_item_id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_state (
        chat_id TEXT PRIMARY KEY,
        last_owner_reply_ts TEXT
        )
        """)
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS owner_context (
        owner_id TEXT PRIMARY KEY,
        bot_chat_id TEXT
        )
        """)



        

        c.commit()