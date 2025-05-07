import pytest
from fastapi.testclient import TestClient
from slack_oauth import app

client = TestClient(app)

def test_login_slack_redirect():
    response = client.get("/login/slack")
    # Should redirect to Slack's OAuth URL
    assert response.status_code == 307 or response.status_code == 302
    assert "slack.com/oauth/v2/authorize" in response.headers["location"]

def test_slack_oauth_callback_missing_code():
    # Simulate callback with no code param
    response = client.get("/slack/oauth/callback")
    assert response.status_code == 422  # FastAPI will return 422 for missing required query param

def test_get_me_invalid_session():
    # Simulate /me with an invalid session token
    response = client.get("/me?session_token=invalidtoken")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid session"

# You can add more tests for valid flows by mocking httpx.AsyncClient if needed.