import os
import json
from typing import Optional, Dict
from fastapi import HTTPException, Request
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from jose import jwt
from datetime import datetime, timedelta
import httpx

# Initialize Slack client
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

def get_login_url() -> str:
    """Generate the Slack OAuth login URL."""
    client_id = os.getenv("SLACK_CLIENT_ID")
    redirect_uri = os.getenv("SLACK_REDIRECT_URI")
    return f"https://slack.com/oauth/v2/authorize?client_id={client_id}&scope=identity.basic,identity.email,identity.avatar&redirect_uri={redirect_uri}"

async def handle_slack_oauth(code: str) -> Dict:
    """Handle the OAuth callback from Slack."""
    client_id = os.getenv("SLACK_CLIENT_ID")
    client_secret = os.getenv("SLACK_CLIENT_SECRET")
    redirect_uri = os.getenv("SLACK_REDIRECT_URI")

    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri
                }
            )
            data = response.json()

        if not data.get("ok"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info
        user_info = await get_user_info(data["authed_user"]["access_token"])
        
        # Create JWT token
        token = create_jwt(user_info)
        
        return {
            "access_token": token,
            "user": user_info
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def get_user_info(access_token: str) -> Dict:
    """Get user information from Slack."""
    try:
        async with httpx.AsyncClient() as client:
            # Get user identity
            identity_response = await client.get(
                "https://slack.com/api/users.identity",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            identity_data = identity_response.json()

            if not identity_data.get("ok"):
                raise HTTPException(status_code=400, detail="Failed to get user info")

            # Get team info
            team_response = await client.get(
                "https://slack.com/api/team.info",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            team_data = team_response.json()

            if not team_data.get("ok"):
                raise HTTPException(status_code=400, detail="Failed to get team info")

            return {
                "id": identity_data["user"]["id"],
                "email": identity_data["user"]["email"],
                "name": identity_data["user"]["name"],
                "team": {
                    "id": team_data["team"]["id"],
                    "name": team_data["team"]["name"],
                    "domain": team_data["team"]["domain"]
                }
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def create_jwt(user_info: Dict) -> str:
    """Create a JWT token for the user."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    payload = {
        "sub": user_info["id"],
        "email": user_info["email"],
        "name": user_info["name"],
        "exp": datetime.utcnow() + timedelta(days=1)
    }

    return jwt.encode(payload, secret, algorithm="HS256")

def verify_token(token: str) -> Dict:
    """Verify and decode a JWT token."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
