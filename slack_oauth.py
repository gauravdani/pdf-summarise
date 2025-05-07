# slack_oauth.py
import os
from fastapi import FastAPI, Request, HTTPException,Cookie
from fastapi.responses import RedirectResponse, HTMLResponse
from dotenv import load_dotenv
import httpx
from jose import jwt
from datetime import datetime, timedelta
from tinydb import TinyDB, Query
import os

load_dotenv()

app = FastAPI()

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI")
JWT_SECRET = os.getenv("SECRET_KEY")
JWT_ALGORITHM = "HS256"

db = TinyDB('users.json')
users_table = db.table('users')

def create_jwt(slack_id, email):
    payload = {
        "slack_id": slack_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=12)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

@app.get("/login/slack")
def login_slack():
    slack_auth_url = (
        "https://slack.com/oauth/v2/authorize"
        f"?client_id={SLACK_CLIENT_ID}"
        f"&scope=identity.basic,identity.email"
        f"&redirect_uri={SLACK_REDIRECT_URI}"
    )
    return RedirectResponse(slack_auth_url)

@app.get("/slack/oauth/callback")
async def slack_oauth_callback(code: str):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": SLACK_CLIENT_ID,
                "client_secret": SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": SLACK_REDIRECT_URI,
            },
        )
        token_data = token_resp.json()
        if not token_data.get("ok"):
            raise HTTPException(status_code=400, detail="Slack OAuth failed")

        access_token = token_data["authed_user"]["access_token"]

        user_resp = await client.get(
            "https://slack.com/api/users.identity",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_data = user_resp.json()
        if not user_data.get("ok"):
            raise HTTPException(status_code=400, detail="Failed to fetch user info")

        slack_id = user_data["user"]["id"]
        email = user_data["user"]["email"]
        name = user_data["user"]["name"]

        # Store or update user in TinyDB
        User = Query()
        if users_table.get(User.slack_id == slack_id):
            users_table.update({'email': email, 'name': name}, User.slack_id == slack_id)
        else:
            users_table.insert({'slack_id': slack_id, 'email': email, 'name': name})

        # Create JWT and set as cookie
        token = create_jwt(slack_id, email)
        response = RedirectResponse(url="/dashboard")
        response.set_cookie(key="session", value=token, httponly=True, secure=True)
        return response


