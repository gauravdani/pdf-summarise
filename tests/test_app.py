import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app import app, get_user_status, check_usage_limit, record_usage
from datetime import datetime
import json

client = TestClient(app)

# Mock data
MOCK_USER_ID = "U1234567890"
MOCK_FILE_ID = "F1234567890"
MOCK_PDF_CONTENT = b"%PDF-1.4\n%Test PDF content"
MOCK_SUMMARY = "This is a test summary"

@pytest.fixture
def mock_slack_event():
    return {
        "type": "app_mention",
        "user": MOCK_USER_ID,
        "ts": "1234567890.123456",
        "files": [
            {
                "id": MOCK_FILE_ID,
                "filetype": "pdf",
                "name": "test.pdf"
            }
        ]
    }

@pytest.fixture
def mock_slack_client():
    with patch("app.slack_app.client") as mock:
        mock.files_info.return_value = {
            "file": {
                "url_private_download": "https://example.com/file.pdf"
            }
        }
        mock.web_client.get.return_value.content = MOCK_PDF_CONTENT
        yield mock

@pytest.fixture
def mock_openai():
    with patch("app.openai.ChatCompletion.create") as mock:
        mock.return_value.choices = [
            Mock(message=Mock(content=MOCK_SUMMARY))
        ]
        yield mock

def test_get_user_status():
    """Test user status retrieval and creation."""
    user = get_user_status(MOCK_USER_ID)
    assert user["user_id"] == MOCK_USER_ID
    assert user["status"] == "free"
    assert "created_at" in user

def test_check_usage_limit():
    """Test usage limit checking."""
    # Test free user within limit
    assert check_usage_limit(MOCK_USER_ID) is True
    
    # Test pro user
    with patch("app.get_user_status") as mock:
        mock.return_value = {"user_id": MOCK_USER_ID, "status": "pro"}
        assert check_usage_limit(MOCK_USER_ID) is True

def test_record_usage():
    """Test usage recording."""
    record_usage(MOCK_USER_ID)
    # Verify usage was recorded (you might want to add more specific assertions)

@pytest.mark.asyncio
async def test_handle_mention_with_pdf(mock_slack_event, mock_slack_client, mock_openai):
    """Test handling of mention event with PDF attachment."""
    with patch("app.slack_app.say") as mock_say:
        # Simulate the event handler
        await app.slack_app.dispatch(mock_slack_event)
        
        # Verify the summary was sent
        mock_say.assert_called_once()
        call_args = mock_say.call_args[1]
        assert "Here's the summary of test.pdf" in call_args["text"]
        assert MOCK_SUMMARY in call_args["text"]

@pytest.mark.asyncio
async def test_handle_mention_without_pdf():
    """Test handling of mention event without PDF attachment."""
    event = {
        "type": "app_mention",
        "user": MOCK_USER_ID,
        "ts": "1234567890.123456"
    }
    
    with patch("app.slack_app.say") as mock_say:
        await app.slack_app.dispatch(event)
        mock_say.assert_called_once_with(
            thread_ts=event["ts"],
            text="Please upload a PDF file for summarization."
        )

@pytest.mark.asyncio
async def test_handle_mention_exceeded_limit():
    """Test handling of mention event when user has exceeded limit."""
    event = {
        "type": "app_mention",
        "user": MOCK_USER_ID,
        "ts": "1234567890.123456",
        "files": [{"filetype": "pdf"}]
    }
    
    with patch("app.check_usage_limit", return_value=False), \
         patch("app.slack_app.say") as mock_say:
        await app.slack_app.dispatch(event)
        mock_say.assert_called_once()
        assert "You've hit your monthly limit" in mock_say.call_args[1]["text"]

def test_reset_limits_command():
    """Test the reset_limits command."""
    command = {
        "user_id": "ADMIN_USER_ID",
        "text": ""
    }
    
    with patch("app.slack_app.say") as mock_say:
        app.slack_app.dispatch({
            "type": "command",
            "command": "/reset_limits",
            **command
        })
        mock_say.assert_called_once_with("Usage limits have been reset for all users.") 