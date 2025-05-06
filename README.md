# PDF Summarizer Slack Bot

A Slack bot that summarizes PDF files using OpenAI's GPT-4 API. Users can upload PDFs and get AI-generated summaries directly in Slack.

## Features

- PDF text extraction and summarization
- Usage tracking with monthly limits
- Free vs Pro user tiers
- Admin controls for user management
- In-memory PDF processing (no disk storage)

## User Flow

1. User uploads a PDF in a Slack channel
2. User mentions the bot (e.g. "@pdf-summarizer-last-mile please summarize this")
3. Bot processes the PDF and generates a summary
4. Summary is posted as a reply in the thread

## Usage Limits

- Free users: 10 summaries per month
- Pro users: Unlimited summaries
- Usage is tracked per user (Slack user_id)

## Tech Stack

- Python
- FastAPI
- Slack Bolt SDK
- OpenAI GPT-4 API
- PyMuPDF for PDF parsing
- TinyDB for usage tracking
- A virtual environment managed using the command python -m venv .venv
- brew install ngrok, we need ngrok
- ngrok config add-authtoken $YOUR_AUTHTOKEN

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the following variables:
   ```
   SLACK_BOT_TOKEN=xoxb-your-token
   SLACK_SIGNING_SECRET=your-signing-secret
   OPENAI_API_KEY=your-openai-api-key
   ```
4. Run the application:
   ```bash
   uvicorn app:app --reload
   ```

## Testing

### Automated Tests

1. Install testing dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the test suite:
   ```bash
   pytest tests/ --cov=app --cov-report=term-missing
   ```

The test suite includes:
- Unit tests for core functions
- Integration tests for Slack events
- Mock fixtures for external services
- Database testing
- API endpoint testing

### Manual Testing

1. **Local Development Setup**
   ```bash
   # Start the FastAPI server
   uvicorn app:app --reload
   ```

2. **Install and Configure Ngrok**
   - Sign up at https://ngrok.com/
   - Install ngrok:
     ```bash
     brew install ngrok
     ```
   - Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
   - Configure ngrok:
     ```bash
     ngrok config add-authtoken YOUR_AUTH_TOKEN
     ```
   - Start ngrok in a new terminal:
     ```bash
     ngrok http 8000
     ```

3. **Configure Slack App**
   - Go to https://api.slack.com/apps
   - Select your app
   - Under "Event Subscriptions":
     - Enable events
     - Set Request URL to your ngrok URL + `/slack/events`
     - Subscribe to bot events: `app_mention`
   - Under "Slash Commands":
     - Add `/reset_limits` command
   - Under "OAuth & Permissions":
     - Add bot scopes:
       - `files:read`
       - `chat:write`
       - `commands`

4. **Test Scenarios**

   a. Basic PDF Summarization:
   - Upload a PDF to a Slack channel
   - Mention the bot: "@pdf-summarizer-last-mile please summarize this"
   - Verify the summary appears in the thread

   b. Usage Limits:
   - Make multiple summary requests
   - Verify the limit message appears after 10 requests
   - Test with a pro user account

   c. Error Handling:
   - Upload a non-PDF file
   - Upload a corrupted PDF
   - Test with missing file attachments

   d. Admin Commands:
   - Try `/reset_limits` as non-admin
   - Try `/reset_limits` as admin
   - Verify usage limits are reset

5. **API Testing**
   Visit these endpoints in your browser:
   - `http://localhost:8000/` - Health check
   - `http://localhost:8000/health` - Detailed health check
   - `http://localhost:8000/docs` - API documentation
   - `http://localhost:8000/redoc` - Alternative API docs
   - 'https://cff9-2a02-2455-313-6e00-e9f7-69a1-c0d0-bc4a.ngrok-free.app/slack/events/' -

6. **Monitoring**
   - Check ngrok web interface: `http://127.0.0.1:4040`
   - Monitor FastAPI logs
   - Check Slack app logs in the Slack API dashboard

### Test Data

Sample PDFs for testing:
- Small text document (1-2 pages)
- Large document (10+ pages)
- Document with images
- Document with tables
- Document with special characters

#### Recommended Test File
For consistent testing, you can use this OpenAI guide:
- URL: https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- Type: Technical document
- Pages: Multiple
- Content: Text, diagrams, and technical content
- Good for testing: Text extraction, formatting preservation, and summary quality

To test with this file:
1. Download the PDF from the URL
2. Upload it to your Slack channel
3. Mention the bot: "@pdf-summarizer-last-mile please summarize this"
4. Verify the summary includes key points about building agents

## Environment Variables

- `SLACK_BOT_TOKEN`: Your Slack bot token
- `SLACK_SIGNING_SECRET`: Your Slack app signing secret
- `OPENAI_API_KEY`: Your OpenAI API key

## Admin Commands

- `/reset_limits`: Reset monthly usage limits (admin only)

## Monetization

- Free tier: 10 summaries per month
- Pro tier: Unlimited summaries
- Upgrade link: https://yoursite.com/upgrade

## Security

- PDFs are processed in-memory only
- No files are stored on disk
- Secure API key handling
- Admin-only commands for user management

## Development

The bot uses FastAPI for webhook endpoints and Slack Bolt for Slack interactions. PDF processing is done in-memory using PyMuPDF, and user data is stored in a TinyDB database.

## License

MIT License 

## How to test

Start the application again:
Apply to README.md
Run
uvicorn app:app --reload
Visit these endpoints in your browser:
http://localhost:8000/ - Basic health check
http://localhost:8000/health - Detailed health check
http://localhost:8000/docs - Interactive API documentation (Swagger UI)
http://localhost:8000/redoc - Alternative API documentation
The health check endpoints will help you verify that:
The application is running
Environment variables are properly loaded
Database connection is working