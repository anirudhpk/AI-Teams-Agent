import os
import sqlite3
import requests
import msal

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv

# -------------------------
# ENV + APP SETUP
# -------------------------
load_dotenv()

CLIENT_ID = os.getenv("MICROSOFT_APP_ID")
CLIENT_SECRET = os.getenv("MICROSOFT_APP_PASSWORD")
TENANT_ID = os.getenv("MICROSOFT_TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")  # e.g. https://xxxx.ngrok-free.dev/auth/callback

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = [
    "User.Read",
    "Chat.Read",
    "Chat.ReadWrite",
]

app = FastAPI()

# -------------------------
# DATABASE
# -------------------------
DB_FILE = "delegated_tokens.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            user_upn TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


init_db()

# -------------------------
# MSAL CLIENT
# -------------------------
def build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
        token_cache=cache,
    )


# -------------------------
# ROUTES
# -------------------------

@app.get("/auth/login")
def login():
    """
    Step 1: Redirect user to Microsoft login
    """
    msal_app = build_msal_app()

    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        prompt="select_account",
    )

    return RedirectResponse(auth_url)


@app.get("/auth/callback")
def auth_callback(request: Request):
    """
    Step 2: OAuth callback
    - Exchange code for token
    - Call Graph /me to get UPN
    - Store token in DB
    """
    code = request.query_params.get("code")
    if not code:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing authorization code"},
        )

    msal_app = build_msal_app()

    token = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    if "access_token" not in token:
        return JSONResponse(
            status_code=400,
            content={"error": "Token acquisition failed", "details": token},
        )

    # -------------------------
    # 🔑 CORRECT FIX: CALL GRAPH /me
    # -------------------------
    headers = {
        "Authorization": f"Bearer {token['access_token']}"
    }

    me_resp = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers=headers,
    )

    if me_resp.status_code != 200:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Failed to fetch /me",
                "response": me_resp.text,
            },
        )

    me = me_resp.json()
    user_upn = me.get("userPrincipalName")

    if not user_upn:
        return JSONResponse(
            status_code=400,
            content={
                "error": "UPN_NOT_FOUND",
                "me_response": me,
            },
        )

    # -------------------------
    # STORE TOKEN
    # -------------------------
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO tokens
        (user_upn, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_upn,
            token["access_token"],
            token.get("refresh_token"),
            token.get("expires_on"),
        ),
    )

    conn.commit()
    conn.close()

    return JSONResponse(
        {
            "status": "TOKEN STORED",
            "user": user_upn,
            "expires_in": token.get("expires_in"),
        }
    )