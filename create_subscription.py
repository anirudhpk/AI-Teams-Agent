import requests
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("GRAPH_TENANT_ID")
CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
USER_OBJECT_ID = os.getenv("OWNER_AAD_OBJECT_ID")


TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0/subscriptions"

# 1. Get access token
token_resp = requests.post(
    TOKEN_URL,
    data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
)


token_data = token_resp.json()
access_token = token_data["access_token"]

# 2. Create subscription
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

expiration = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat() + "Z"
print(expiration)
payload = {
    "changeType": "created",
    "notificationUrl": "https://kasha-corporeal-terrell.ngrok-free.dev/graph/webhook",
    "lifecycleNotificationUrl": "https://kasha-corporeal-terrell.ngrok-free.dev/graph/webhook",
    "resource": f"/users/{USER_OBJECT_ID}/chats/getAllMessages",
    "expirationDateTime": expiration,
    "clientState": "secret123"
}

resp = requests.post(GRAPH_URL, headers=headers, json=payload)

print(resp.status_code)
print(resp.text)
