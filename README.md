# PDF Summarizer Slack Bot

A Slack bot that summarizes PDF files using OpenAI's GPT-4 API. Users can upload PDFs and get AI-generated summaries directly in Slack.

## Features

- PDF text extraction and summarization
- Usage tracking with monthly limits
- Free vs Pro user tiers
- Admin controls for user management
- In-memory PDF processing (no disk storage)
- Secure authentication via Slack OAuth
- User dashboard

## User Flow

1. User uploads a PDF in a Slack channel
2. User mentions the bot (e.g. "@pdf-summarizer-last-mile please summarize this")
3. Bot processes the PDF and generates a summary
4. Summary is posted as a reply in the thread

## Authentication & User Management

### Login Workflows

#### 1. Slack OAuth Flow
1. **Initial Login**
   - User visits `/login` endpoint
   - Redirected to Slack OAuth page
   - User authorizes the app
   - Redirected back to `/slack/oauth/callback`
   - JWT token created and stored in secure cookie
   - User redirected to dashboard

2. **Session Management**
   - JWT tokens valid for 24 hours
   - Secure, HTTP-only cookies
   - Automatic token refresh on dashboard access
   - Session invalidation on logout

3. **User Data Storage**
   - Slack User ID
   - Slack Workspace (Team) ID
   - User Email
   - Account Status (free/pro)
   - Creation Date
   - Last Login Timestamp

#### 2. User Identification
- **Primary Keys**:
  - `user_id`: Slack User ID
  - `team_id`: Slack Workspace ID
  - `email`: User's Email Address

- **User Status**:
  - `free`: Limited to 10 summaries/month
  - `pro`: Unlimited summaries
  - `admin`: Full access to admin features

#### 3. Usage Tracking
- **Per User**:
  - Monthly summary count
  - File names processed
  - Timestamps of usage
  - Status at time of usage

- **Per Workspace**:
  - Total workspace usage
  - Active users count
  - Pro vs Free user ratio

### Required Slack Scopes
```yaml
Bot Token Scopes:
  - app_mentions:read
  - channels:history
  - chat:write
  - files:read
  - users:read
  - users:read.email
  - im:write
  - im:read

User Token Scopes:
  - identity.basic
  - identity.email
  - identity.avatar
```

### Environment Variables
```env
# Slack Bot Configuration
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-signing-secret

# Slack OAuth Configuration
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret
SLACK_REDIRECT_URI=http://localhost:8000/slack/oauth/callback

# JWT Configuration
JWT_SECRET=your-jwt-secret

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
```

### Security Measures
1. **Authentication**:
   - JWT-based authentication
   - Secure, HTTP-only cookies
   - CSRF protection
   - Rate limiting on auth endpoints

2. **Data Protection**:
   - Encrypted JWT tokens
   - Secure cookie settings
   - HTTPS enforcement
   - Input validation

3. **Access Control**:
   - Role-based access (free/pro/admin)
   - Workspace-level permissions
   - Usage limits enforcement
   - Admin-only routes protection

### Testing Authentication
1. **Local Testing**:
   ```bash
   # Start the application
   uvicorn app:app --reload
   
   # Visit login page
   open http://localhost:8000/login
   ```

2. **Production Testing**:
   ```bash
   # Start ngrok for public URL
   ngrok http 8000
   
   # Update SLACK_REDIRECT_URI in .env
   SLACK_REDIRECT_URI=https://your-ngrok-url/slack/oauth/callback
   ```

3. **Test Cases**:
   - Login with new user
   - Login with existing user
   - Token expiration
   - Invalid token handling
   - Workspace switching
   - Admin access verification

### Common Issues & Solutions
1. **OAuth Errors**:
   - Check redirect URI matches exactly
   - Verify all required scopes are added
   - Ensure environment variables are set
   - Check Slack app configuration

2. **Token Issues**:
   - Verify JWT_SECRET is set
   - Check token expiration
   - Ensure secure cookie settings
   - Validate token format

3. **Workspace Issues**:
   - Verify team_id is being passed
   - Check workspace permissions
   - Validate workspace status
   - Ensure proper error handling

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
   SLACK_CLIENT_ID=your-client-id
   SLACK_CLIENT_SECRET=your-client-secret
   SLACK_REDIRECT_URI=https://your-domain/slack/oauth/callback
   JWT_SECRET=your-jwt-secret
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
       - `identity.basic`
       - `identity.email`
       - `identity.avatar`

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

   e. Authentication Flow:
   - Test login with valid Slack credentials
   - Test login with invalid credentials
   - Test session expiration
   - Test protected route access
   - Test logout functionality

5. **API Testing**
   Visit these endpoints in your browser:
   - `http://localhost:8000/` - Health check
   - `http://localhost:8000/health` - Detailed health check
   - `http://localhost:8000/docs` - API documentation
   - `http://localhost:8000/redoc` - Alternative API docs
   - `http://localhost:8000/login` - Login page
   - `http://localhost:8000/dashboard` - Protected dashboard

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
- JWT-based authentication
- OAuth token encryption
- HTTP-only cookies
- CSRF protection

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
Generating - JWT  - python3 -c "import secrets; print(secrets.token_hex(32))"

### Slack App Configuration
1. **Basic Information**
   - Set app name and description
   - Upload app icon
   - Set app URL to your domain

2. **App Home**
   - Enable "Home Tab"
   - Set "Messages Tab" to "Enabled"
   - Configure "App Home" view:
     ```json
     {
       "type": "home",
       "blocks": [
         {
           "type": "section",
           "text": {
             "type": "mrkdwn",
             "text": "Welcome to PDF Summarizer! Click below to get started."
           }
         },
         {
           "type": "actions",
           "elements": [
             {
               "type": "button",
               "text": {
                 "type": "plain_text",
                 "text": "Login with Slack"
               },
               "action_id": "login_button"
             }
           ]
         }
       ]
     }
     ```

3. **OAuth & Permissions**
   - Add required scopes (listed above)
   - Set redirect URL to your callback endpoint
   - Install app to workspace

4. **Event Subscriptions**
   - Enable events
   - Set request URL
   - Subscribe to events:
     - `app_home_opened`
     - `app_mention`
     - `message.im` (for direct messages)

### Login Flow
1. **App Home Access**
   - User clicks app in Slack sidebar
   - App home opens with login button
   - User clicks "Login with Slack"
   - OAuth flow initiates

2. **OAuth Process**
   - User authorizes app
   - Redirects back to app home
   - Updates app home view with dashboard
   - Stores session in secure cookie

3. **Session Management**
   - JWT token stored in secure cookie
   - App home view updates based on auth status
   - Automatic token refresh
   - Session invalidation on logout

### App Home Views
1. **Unauthenticated View**
   ```json
   {
     "type": "home",
     "blocks": [
       {
         "type": "section",
         "text": {
           "type": "mrkdwn",
           "text": "Welcome to PDF Summarizer!"
         }
       },
       {
         "type": "actions",
         "elements": [
           {
             "type": "button",
             "text": {
               "type": "plain_text",
               "text": "Login with Slack"
             },
             "action_id": "login_button"
           }
         ]
       }
     ]
   }
   ```

2. **Authenticated View**
   ```json
   {
     "type": "home",
     "blocks": [
       {
         "type": "section",
         "text": {
           "type": "mrkdwn",
           "text": "Welcome back, <@{user_id}>!"
         }
       },
       {
         "type": "section",
         "text": {
           "type": "mrkdwn",
           "text": "Your usage this month: {usage_count}/10"
         }
       },
       {
         "type": "actions",
         "elements": [
           {
             "type": "button",
             "text": {
               "type": "plain_text",
               "text": "Upgrade to Pro"
             },
             "action_id": "upgrade_button"
           }
         ]
       }
     ]
   }
   ```

### Testing App Home & Login Flows

1. **Setup Testing Environment**
   ```bash
   # Start the application
   uvicorn app:app --reload

   # In a new terminal, start ngrok
   ngrok http 8000

   # Update your .env with the new ngrok URL
   SLACK_REDIRECT_URI=https://your-ngrok-url/slack/oauth/callback
   ```

2. **Test App Home Views**
   a. **Unauthenticated View**
   - Click app in Slack sidebar
   - Verify welcome message appears
   - Check "Login with Slack" button is present
   - Click button to verify modal opens
   - Verify OAuth URL is correct in modal

   b. **Authenticated View**
   - Complete OAuth flow
   - Return to app home
   - Verify welcome back message with user mention
   - Check usage counter is displayed
   - Verify upgrade button is present

3. **Test Login Flow**
   a. **Initial Login**
   ```bash
   # 1. Click app in Slack sidebar
   # 2. Click "Login with Slack" button
   # 3. Authorize app in Slack
   # 4. Verify redirect to app home
   # 5. Check authenticated view appears
   ```

   b. **Session Management**
   ```bash
   # 1. Close and reopen app home
   # 2. Verify still logged in
   # 3. Check JWT token in cookies
   # 4. Test token expiration (24 hours)
   ```

4. **Test Error Scenarios**
   a. **OAuth Errors**
   - Test with invalid client ID
   - Test with incorrect redirect URI
   - Test with missing scopes
   - Verify error messages are clear

   b. **App Home Errors**
   - Test with network issues
   - Test with invalid user ID
   - Test with missing permissions
   - Check error handling in logs

5. **Verify Database Updates**
   ```bash
   # Check user record creation
   cat db.json | grep "user_id"

   # Verify email storage
   cat db.json | grep "email"

   # Check team_id storage
   cat db.json | grep "team_id"
   ```

6. **Test Workspace Features**
   a. **Multi-workspace Support**
   - Install app in different workspace
   - Verify separate user records
   - Check workspace-specific usage limits
   - Test cross-workspace isolation

   b. **Workspace Permissions**
   - Test with different user roles
   - Verify admin access
   - Check workspace-level settings
   - Test workspace-wide limits

7. **Monitor Logs**
   ```bash
   # Watch application logs
   tail -f app.log

   # Expected log entries:
   # - App home opened
   # - OAuth callback received
   # - User info retrieved
   # - View updates published
   ```

8. **Common Test Cases**
   ```bash
   # Test Case 1: New User Login
   1. Open app home
   2. Click login
   3. Complete OAuth
   4. Verify new user record
   5. Check welcome message

   # Test Case 2: Existing User Login
   1. Open app home
   2. Click login
   3. Complete OAuth
   4. Verify updated last_login
   5. Check usage stats

   # Test Case 3: Session Expiry
   1. Login successfully
   2. Wait for token expiry
   3. Try to access protected route
   4. Verify redirect to login
   5. Check new token generation
   ```

9. **Troubleshooting**
   ```bash
   # Check Slack API responses
   curl -X POST https://slack.com/api/apps.event.authorizations.list \
     -H "Authorization: Bearer $SLACK_BOT_TOKEN"

   # Verify OAuth configuration
   curl -X GET https://slack.com/api/oauth.v2.access \
     -H "Authorization: Bearer $SLACK_BOT_TOKEN"

   # Test app home publishing
   curl -X POST https://slack.com/api/views.publish \
     -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     -H "Content-type: application/json" \
     -d '{"user_id":"USER_ID","view":{"type":"home"}}'
   ```

10. **Security Testing**
    - Verify JWT token security
    - Test CSRF protection
    - Check cookie settings
    - Validate input sanitization
    - Test rate limiting
    - Verify HTTPS enforcement

Remember to:
- Test on different devices/browsers
- Verify mobile app compatibility
- Check accessibility features
- Test with different user roles
- Monitor performance metrics
- Document any issues found