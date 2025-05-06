import pytest
from fastapi.testclient import TestClient
from app import app
import json

client = TestClient(app)

def test_slack_url_verification():
    """Test Slack URL verification challenge."""
    # Mock Slack challenge request
    challenge_data = {
        "token": "Jhj5dZrVaK7ZwHHjRyZWjbDl",
        "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P",
        "type": "url_verification"
    }
    
    # Send POST request to /slack/events
    response = client.post(
        "/slack/events",
        json=challenge_data
    )
    
    # Check response
    assert response.status_code == 200
    assert response.json() == {"challenge": challenge_data["challenge"]}

def test_slack_url_verification_invalid_json():
    """Test Slack URL verification with invalid JSON."""
    # Send invalid JSON
    response = client.post(
        "/slack/events",
        data="invalid json"
    )
    
    # Check response
    assert response.status_code == 400
    assert "Invalid request body" in response.json()["detail"]

def test_slack_url_verification_missing_challenge():
    """Test Slack URL verification with missing challenge."""
    # Mock Slack event without challenge
    event_data = {
        "token": "Jhj5dZrVaK7ZwHHjRyZWjbDl",
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "user": "U1234567890",
            "text": "Hello"
        }
    }
    
    # Send POST request to /slack/events
    response = client.post(
        "/slack/events",
        json=event_data
    )
    
    # Check response (should be handled by SlackRequestHandler)
    assert response.status_code == 200 