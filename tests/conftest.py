import pytest
import os
from dotenv import load_dotenv

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
    os.environ["SLACK_SIGNING_SECRET"] = "test-signing-secret"
    os.environ["OPENAI_API_KEY"] = "test-openai-key"
    load_dotenv()

@pytest.fixture
def test_db():
    """Create a test database."""
    from tinydb import TinyDB
    db = TinyDB("test_db.json")
    yield db
    # Cleanup
    if os.path.exists("test_db.json"):
        os.remove("test_db.json") 