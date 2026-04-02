from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import msal, time
from db import get_conn, init_db
import os
from dotenv import load_dotenv
from owner_context import resolve_owner_context

load_dotenv()
init_db()

app = FastAPI()

SCOPES = [
    "email",
    "User.Read",
    "Chat.Read",
    "Chat.ReadWrite"
]

msal_app = msal.ConfidentialClientApplication(
    os.getenv("CLIENT_ID"),
    authority=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}",
    client_credential=os.getenv("CLIENT_SECRET")
)

@app.get("/login")
def login():
    url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=os.getenv("REDIRECT_URI")
    )    
    return RedirectResponse(url)

@app.get("/auth/callback")
def callback(code: str):
    token = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=os.getenv("REDIRECT_URI")
    )

    user_id = token["id_token_claims"]["oid"]
    

    with get_conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO tokens VALUES (?,?,?)",
            (user_id, token["access_token"], int(time.time()) + token["expires_in"])
        )
        c.execute(
            "INSERT OR IGNORE INTO bot_state VALUES (?,1)",
            (user_id,)
        )
        c.commit()

    
    
    return {"status": "TOKEN STORED", "user": user_id}