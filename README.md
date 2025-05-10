# PDF Summarizer Slack Bot

A Slack bot that summarizes PDF files using OpenAI's GPT-4 API. The bot provides both free and pro user tiers with different usage limits.

## Features

- PDF text extraction and summarization
- Slack integration with app home view
- User authentication via Slack OAuth
- Usage tracking and limits
- Pro user upgrade option
- Multi-workspace support

## User Workflows

### 1. Authentication Flow
- **Initial Login**:
  - User visits `/login` endpoint or clicks app home login button
  - Redirected to Slack OAuth page
  - User authorizes the app
  - Redirected back to `/slack/oauth/callback`
  - JWT token created and stored in secure cookie
  - User redirected to dashboard

- **Session Management**:
  - JWT tokens valid for 24 hours
  - Secure, HTTP-only cookies
  - Automatic token refresh on dashboard access
  - Session invalidation on logout

### 2. PDF Processing Flow
- **Basic Usage**:
  1. User uploads PDF to Slack channel
  2. User mentions bot: "@PDF Summarizer"
  3. Bot processes PDF and generates summary
  4. Summary posted as reply in thread

- **Usage Limits**:
  - Free users: 10 summaries per month
  - Pro users: Unlimited summaries
  - Usage tracked per user and workspace
  - Monthly reset of usage counters

### 3. App Home Interaction
- **Unauthenticated View**:
  - Welcome message
  - Login button
  - Basic app information

- **Authenticated View**:
  - Personalized welcome
  - Current usage statistics
  - Upgrade option for free users
  - Quick access to recent summaries

### 4. User Management
- **User Data**:
  - Slack User ID
  - Workspace (Team) ID
  - Email address
  - Account status (free/pro)
  - Creation date
  - Last login timestamp

- **Workspace Management**:
  - Multi-workspace support
  - Workspace-specific usage limits
  - Team-level statistics
  - Admin controls per workspace

## Prerequisites

- Python 3.8+
- Slack workspace with admin access
- OpenAI API key
- ngrok (for local development)

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/pdf-summarizer.git
   cd pdf-summarizer
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables in `.env`:
   ```
   # Slack Configuration
   SLACK_CLIENT_ID=your_client_id_here
   SLACK_CLIENT_SECRET=your_client_secret_here
   SLACK_REDIRECT_URI=https://your-domain.com/slack/oauth/callback
   SLACK_BOT_TOKEN=xoxb-your-bot-token-here
   SLACK_SIGNING_SECRET=your_signing_secret_here

   # JWT Configuration
   JWT_SECRET=your_jwt_secret_here

   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key_here

   # Feature Flags
   ENABLE_SUBSCRIPTION_SYSTEM=false
   ENABLE_TRIAL_PERIOD=false
   ENABLE_USAGE_TRACKING=false
   ENABLE_SUBSCRIPTION_LIMITS=false
   ENABLE_SUBSCRIPTION_UPGRADE=false
   ```

## Slack App Configuration

1. Go to https://api.slack.com/apps
2. Create a new app or select your existing app
3. Under "OAuth & Permissions", add the following scopes:
   - Bot Token Scopes:
     - `chat:write`
     - `im:write`
     - `im:read`
     - `users:read`
     - `users:read.email`
     - `files:read`
     - `app_mentions:read`
   - User Token Scopes:
     - `identity.basic`
     - `identity.email`
     - `identity.avatar`
4. Set the Redirect URL to your callback URL
5. Install the app to your workspace
6. Copy the Bot User OAuth Token and Signing Secret to your `.env` file

## Running the Application

1. Start ngrok for local development:
   ```bash
   ngrok http 8000
   ```

2. Update your Slack app's Redirect URL with the new ngrok URL

3. Start the application:
   ```bash
   uvicorn app:app --reload
   ```

## Testing the Application

### 1. Testing Login Flow

1. **Direct Login**:
   - Visit `http://localhost:8000/login`
   - You should be redirected to Slack OAuth
   - After authorizing, you'll be redirected back to the dashboard

2. **App Home Login**:
   - Open your Slack workspace
   - Click on the PDF Summarizer app
   - Click the "Login with Slack" button
   - Complete the OAuth flow
   - Verify the app home updates with your usage stats

3. **Session Management**:
   - After logging in, check that the JWT token is set in cookies
   - Visit `/dashboard` to verify authentication
   - Try accessing `/dashboard` without the token to verify protection

### 2. Testing PDF Summarization

1. **Basic Usage**:
   - Upload a PDF file to a Slack channel
   - Mention the bot: `@PDF Summarizer`
   - Verify the summary is generated and posted

2. **Usage Limits**:
   - Test with a free user (10 summaries per month)
   - Verify the limit message appears after exceeding quota
   - Test with a pro user (unlimited summaries)

3. **Error Handling**:
   - Test with non-PDF files
   - Test with empty PDFs
   - Test with corrupted PDFs
   - Verify appropriate error messages

### 3. Testing App Home Features

1. **View Updates**:
   - Open app home as unauthenticated user
   - Verify login button is visible
   - Login and verify usage stats appear
   - Check upgrade button functionality

2. **Usage Statistics**:
   - Generate some summaries
   - Verify usage count updates in app home
   - Check monthly reset functionality

## API Endpoints

- `GET /`: Health check
- `GET /health`: Detailed health check
- `GET /login`: OAuth login redirect
- `GET /slack/oauth/callback`: OAuth callback handler
- `GET /dashboard`: Protected user dashboard
- `POST /process-pdf`: Process PDF from URL
- `POST /slack/events`: Slack events handler

## Security Features

- JWT-based authentication
- Secure cookie handling
- HTTPS enforcement
- Rate limiting
- Input validation
- Error handling

## Database Schema

### Users Table
- `user_id`: Slack user ID
- `team_id`: Slack workspace ID
- `email`: User's email
- `status`: User tier (free/pro)
- `created_at`: Account creation timestamp
- `last_login`: Last login timestamp

### Usage Table
- `user_id`: Slack user ID
- `team_id`: Slack workspace ID
- `email`: User's email
- `month`: Usage month (YYYY-MM)
- `timestamp`: Usage timestamp
- `file_name`: Processed file name
- `user_status`: User tier at time of use

## Subscription Management

### Subscription Tiers

1. **Trial Tier**
   - 7-day unlimited access
   - All premium features
   - Automatic conversion to free tier after trial
   - Price: Free

2. **Standard Tier**
   - 100 summaries per month
   - Priority processing
   - Email support
   - Price: €5.99/month

3. **Premium Tier**
   - 1000 summaries per month
   - Priority processing
   - Priority support
   - Advanced analytics
   - Price: €8.99/month

### Subscription States

1. **Trial State**
   - Automatically assigned to new users
   - Tracks trial start date
   - Sends reminder emails at 5 days and 1 day before expiry
   - Converts to free tier after 7 days if no subscription chosen

2. **Active Subscription**
   - Monthly recurring billing
   - Usage tracking against monthly limit
   - Automatic renewal
   - Grace period for failed payments

3. **Expired/Cancelled**
   - Access to free tier features
   - Usage limited to 10 summaries per month
   - Option to resubscribe
   - Data retention for 30 days

### Implementation Details

1. **Database Updates**
   ```sql
   -- Add to Users Table
   subscription_status: ENUM('trial', 'active', 'expired')
   subscription_tier: ENUM('standard', 'premium')
   trial_start_date: DATETIME
   subscription_start_date: DATETIME
   subscription_end_date: DATETIME
   payment_provider: STRING
   payment_customer_id: STRING
   ```

2. **Payment Integration**
   - Stripe integration for recurring payments
   - Webhook handling for payment events
   - Automatic invoice generation
   - Failed payment handling

3. **Subscription Flow**
   ```
   New User → Trial (7 days) → Choose Plan → Subscription Active
                                    ↓
                              Free Tier (10/month)
   ```

4. **Usage Tracking**
   - Track usage against subscription limits
   - Reset counters monthly
   - Pro-rate usage for mid-month upgrades
   - Usage alerts at 80% and 100% of limit

5. **Notification System**
   - Trial expiration reminders
   - Usage limit alerts
   - Payment failure notifications
   - Subscription renewal reminders

### Upgrade/Downgrade Process

1. **Upgrading**
   - Immediate access to new tier
   - Pro-rated billing
   - Usage limits updated instantly
   - Confirmation email

2. **Downgrading**
   - Continues until end of billing period
   - Usage limits adjusted at next billing cycle
   - Option to cancel downgrade
   - Confirmation email

### Cancellation Process

1. **User Initiated**
   - Access until end of billing period
   - Option to reactivate
   - Data retention policy
   - Exit survey

2. **Payment Failure**
   - 3-day grace period
   - Multiple payment attempts
   - Automatic downgrade to free tier
   - Reactivation process

## Troubleshooting

### Common Issues

1. **OAuth Flow Issues**:
   - Verify Redirect URL matches exactly
   - Check all required scopes are added
   - Ensure environment variables are set correctly

2. **PDF Processing Issues**:
   - Check file size limits
   - Verify PDF is not password protected
   - Ensure PDF contains extractable text

3. **Authentication Issues**:
   - Verify JWT secret is set
   - Check cookie settings
   - Ensure HTTPS is used in production

### Logging

- Application logs are available in the console
- Debug level logging is enabled by default
- Check logs for detailed error information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.


## Do not remove  - Reference material
https://reviewnudgebot.com/blog/checklist-build-and-monetize-slack-bot-in-2024/


## how to run the server

 uvicorn app:app --reload

 To test locally
 http://127.0.0.1:4040/inspect/http

