import os
from datetime import datetime
from typing import Optional, Set
import fitz  # PyMuPDF
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from dotenv import load_dotenv
from tinydb import TinyDB, Query
import openai
from io import BytesIO
import logging
import json
from pydantic import BaseModel
import requests
import traceback
import hashlib
from collections import deque
from threading import Lock
from slack_oauth import handle_slack_oauth, get_login_url, verify_token, create_jwt
from slack_sdk.errors import SlackApiError
from migrations import migrate_subscription_schema, initialize_trial_period
from subscription_manager import (
    get_subscription_limits,
    check_usage_limit,
    get_usage_stats,
    handle_subscription_change,
    check_subscription_expiry
)

# Configure logging with more detail and better formatting
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app with metadata
app = FastAPI(
    title="PDF Summarizer Bot",
    description="A Slack bot that summarizes PDF files using OpenAI's GPT-4 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize Slack app
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize TinyDB
db = TinyDB('db.json')
users = db.table('users')
usage = db.table('usage')

# Initialize OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Constants
MONTHLY_LIMIT = 10
UPGRADE_LINK = "https://yoursite.com/upgrade"

# Add new environment variables
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI")

# Initialize message queue and processed events set
processed_events: Set[str] = set()
message_queue = deque(maxlen=1000)  # Keep last 1000 events
queue_lock = Lock()

class PDFRequest(BaseModel):
    pdf_url: str

@app.get("/")
async def root():
    """Health check endpoint."""
    logger.debug("Health check endpoint called")
    return {
        "status": "healthy",
        "service": "PDF Summarizer Bot",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    logger.debug("Health check endpoint called")
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "slack": bool(os.environ.get("SLACK_BOT_TOKEN")),
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "database": bool(db)
        }
    }

def get_user_status(user_id: str, email: str = None, team_id: str = None) -> dict:
    """Get or create user status."""
    User = Query()
    user = users.get((User.user_id == user_id) & (User.team_id == team_id))
    if not user:
        user = {
            'user_id': user_id,
            'team_id': team_id,
            'email': email,
            'status': 'free',
            'created_at': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat(),
            'subscription_status': 'trial',
            'subscription_tier': 'standard',
            'trial_start_date': datetime.now().isoformat(),
            'subscription_start_date': None,
            'subscription_end_date': None,
            'payment_provider': None,
            'payment_customer_id': None
        }
        users.insert(user)
        initialize_trial_period(user_id, team_id)
    elif email and user.get('email') != email:
        # Update email if it has changed
        users.update({
            'email': email,
            'last_login': datetime.now().isoformat()
        }, (User.user_id == user_id) & (User.team_id == team_id))
        user['email'] = email
    return user

def check_usage_limit(user_id: str, team_id: str) -> bool:
    """Check if user has exceeded monthly limit."""
    User = Query()
    user = get_user_status(user_id, team_id=team_id)
    
    if user['status'] == 'pro':
        return True
        
    current_month = datetime.now().strftime('%Y-%m')
    Usage = Query()
    monthly_usage = usage.count(
        (Usage.user_id == user_id) & 
        (Usage.team_id == team_id) &
        (Usage.month == current_month)
    )
    
    return monthly_usage < MONTHLY_LIMIT

def record_usage(user_id: str, team_id: str, file_name: str = None):
    """Record a usage instance."""
    user = get_user_status(user_id, team_id=team_id)
    usage.insert({
        'user_id': user_id,
        'team_id': team_id,
        'email': user.get('email'),
        'month': datetime.now().strftime('%Y-%m'),
        'timestamp': datetime.now().isoformat(),
        'file_name': file_name,
        'user_status': user['status']
    })

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        logger.info(f"📄 Starting PDF text extraction. Input size: {len(pdf_bytes)} bytes")
        
        # Create a BytesIO object from the bytes
        pdf_stream = BytesIO(pdf_bytes)
        logger.debug("✅ Created BytesIO stream from PDF bytes")
        
        # Open the PDF using PyMuPDF
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        logger.info(f"📚 Opened PDF document. Number of pages: {len(doc)}")
        
        text = ""
        # Extract text from each page using a different method
        for i, page in enumerate(doc):
            # Try different text extraction methods
            page_text = page.get_text("text")  # Try explicit text mode
            if not page_text:
                # If text mode fails, try blocks mode and join the blocks
                blocks = page.get_text("blocks")
                if blocks:
                    # Filter out image blocks and join text blocks
                    text_blocks = [block[4] for block in blocks if isinstance(block[4], str)]
                    page_text = "\n".join(text_blocks)
            
            logger.debug(f"📃 Page {i+1}: Extracted {len(page_text)} characters")
            if page_text:
                logger.debug(f"Sample from page {i+1}: {page_text[:100]}")
            text += page_text
        
        # Close the document
        doc.close()
        logger.debug("✅ Closed PDF document")
        
        if not text.strip():
            logger.warning("⚠️ No text extracted from PDF. The file might be scanned or contain only images.")
            raise Exception("No text could be extracted from the PDF. The file might be scanned or contain only images.")
        
        logger.info(f"✅ Successfully extracted {len(text)} characters of text")
        logger.debug(f"First 200 characters of extracted text: {text[:200]}")
        return text
    except Exception as e:
        logger.error(f"❌ Error extracting text from PDF: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {str(e)}")
        raise

def generate_summary(text: str) -> str:
    """Generate summary using OpenAI GPT-4."""
    try:
        logger.info("🤖 Initializing OpenAI client")
        client = openai.OpenAI()
        
        logger.info("📤 Sending request to OpenAI API")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes PDF documents. Provide a concise but comprehensive summary."},
                {"role": "user", "content": f"Please summarize the following text:\n\n{text}"}
            ],
            max_tokens=500
        )
        
        logger.info("✅ Received response from OpenAI API")
        summary = response.choices[0].message.content
        logger.debug(f"OpenAI response: {summary}")
        
        return summary
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        raise

@slack_app.event("app_mention")
async def handle_mention(event, say, client):
    """Handle app mention events."""
    logger.info("="*80)
    logger.info("📥 Received new app mention event")
    logger.info(f"👤 From user: {event.get('user')}")
    logger.info(f"🏢 In workspace: {event.get('team')}")
    
    user_id = event['user']
    team_id = event['team']
    temp_files = []  # Keep track of temporary files to clean up
    
    try:
        # Check subscription and usage limits
        if not check_usage_limit(user_id, team_id):
            usage_stats = get_usage_stats(user_id, team_id)
            logger.warning(f"⚠️ User {user_id} has exceeded their limit")
            await say(
                thread_ts=event['ts'],
                text=f"You've hit your monthly limit of {usage_stats['limit']} summaries. "
                     f"Current usage: {usage_stats['current_usage']}. "
                     f"Upgrade your subscription to continue: {UPGRADE_LINK}"
            )
            return
        
        # Check for file attachments
        if 'files' not in event:
            logger.warning("⚠️ No files attached in mention")
            await say(
                thread_ts=event['ts'],
                text="Please upload a PDF file for summarization."
            )
            return
        
        # Process each PDF file
        for file in event['files']:
            await process_pdf_file(file, user_id, team_id, event['ts'], say, client)
            
    except Exception as e:
        logger.error(f"Error in handle_mention: {str(e)}")
        await say(
            thread_ts=event['ts'],
            text="Sorry, I encountered an error processing your request. Please try again."
        )
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"🧹 Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.error(f"❌ Error cleaning up temporary file {temp_file}: {str(e)}")

def get_event_hash(event: dict) -> str:
    """Generate a unique hash for an event."""
    event_str = json.dumps(event, sort_keys=True)
    return hashlib.md5(event_str.encode()).hexdigest()

def is_event_processed(event_hash: str) -> bool:
    """Check if an event has been processed."""
    with queue_lock:
        return event_hash in processed_events

def mark_event_processed(event_hash: str):
    """Mark an event as processed."""
    with queue_lock:
        processed_events.add(event_hash)
        if len(processed_events) > 1000:  # Prevent unbounded growth
            processed_events.clear()

@app.post("/slack/events")
async def endpoint(request: Request):
    """Handle Slack events."""
    logger.info("="*80)
    logger.info("📥 Received Slack event")
    
    # Get the request body
    body = await request.body()
    body_str = body.decode('utf-8')
    logger.debug(f"Request body: {body_str}")
    
    try:
        # Parse the request body
        body_json = json.loads(body_str)
        
        # Handle URL verification challenge
        if "challenge" in body_json:
            logger.info(f"✅ Received challenge: {body_json['challenge']}")
            return {"challenge": body_json["challenge"]}
            
        # Check if event has been processed
        event_hash = get_event_hash(body_json)
        if is_event_processed(event_hash):
            logger.info("⚠️ Event already processed, skipping")
            return {"ok": True}
            
        # Log event type
        if "event" in body_json:
            event_type = body_json['event'].get('type')
            logger.info(f"📝 Received event type: {event_type}")
            
            # For app_mention events, we need to check if there are files
            if event_type == "app_mention":
                # Get the thread_ts if it exists
                thread_ts = body_json['event'].get('thread_ts') or body_json['event'].get('ts')
                
                # Check if there are files in the event
                if 'files' not in body_json['event']:
                    logger.info("⚠️ No files in the event")
                    return {"ok": True}
                
                # Process the files
                for file in body_json['event']['files']:
                    await process_pdf_file(
                        file,
                        body_json['event']['user'],
                        body_json['event'].get('team', body_json.get('team_id')),
                        thread_ts,
                        slack_app.client.chat_postMessage,
                        slack_app.client
                    )
                
                # Mark event as processed
                mark_event_processed(event_hash)
            
        return {"ok": True}
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")
    except Exception as e:
        logger.error(f"❌ Error handling request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    logger.info("="*80)

async def process_pdf_file(file, user_id, team_id, thread_ts, say, client):
    """Process a single PDF file and generate summary."""
    logger.info(f"📄 Processing file: {file['name']}")
    if file['filetype'] != 'pdf':
        logger.warning(f"⚠️ Non-PDF file received: {file['filetype']}")
        return
    
    try:
        # Download file
        logger.info(f"🔍 Getting file info for: {file['id']}")
        response = client.files_info(file=file['id'])
        
        if not response.get('ok'):
            error_msg = f"❌ Slack API error: {response.get('error')}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        file_url = response['file']['url_private_download']
        logger.info(f"⬇️ Downloading file from: {file_url}")
        
        # Download the file
        file_response = requests.get(
            file_url,
            headers={'Authorization': f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
        )
        
        if file_response.status_code != 200:
            raise Exception(f"Failed to download file: HTTP {file_response.status_code}")
        
        # Extract text and generate summary
        logger.info("📝 Starting text extraction from PDF")
        pdf_text = extract_text_from_pdf(file_response.content)
        logger.info(f"✅ Text extraction completed. Length: {len(pdf_text)} characters")
        
        # Check text length and chunk if necessary
        if len(pdf_text) > 4000:  # Approximate token limit
            logger.warning("⚠️ PDF text too long, chunking...")
            chunks = [pdf_text[i:i+4000] for i in range(0, len(pdf_text), 4000)]
            summaries = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{len(chunks)}")
                chunk_summary = generate_summary(chunk)
                summaries.append(chunk_summary)
            summary = "\n\n".join(summaries)
        else:
            # Generate summary
            logger.info("🤖 Generating summary with OpenAI")
            summary = generate_summary(pdf_text)
        
        logger.info(f"✅ Summary generated successfully. Length: {len(summary)} characters")
        
        # Record usage for subscription tracking
        try:
            record_usage(user_id, team_id, file['name'])
        except Exception as e:
            logger.error(f"Error recording usage: {str(e)}")
        
        # Get the channel from the file or use the user's DM channel
        channel = file.get('channels', [None])[0] or file.get('groups', [None])[0] or file.get('ims', [None])[0]
        if not channel:
            # If no channel found, try to open a DM with the user
            try:
                dm_response = client.conversations_open(users=[user_id])
                if dm_response.get('ok'):
                    channel = dm_response['channel']['id']
                else:
                    raise Exception("Could not open DM channel")
            except Exception as e:
                logger.error(f"Failed to get channel: {str(e)}")
                raise Exception("Could not determine where to send the message")
        
        # Send summary
        logger.info(f"📤 Sending summary to Slack channel: {channel}")
        try:
            await say(
                channel=channel,
                thread_ts=thread_ts,
                text=f"Here's the summary of {file['name']}:\n\n{summary}"
            )
            logger.info(f"✅ Successfully processed and summarized {file['name']}")
        except Exception as e:
            logger.error(f"Failed to send message to channel {channel}: {str(e)}")
            # Try sending to user's DM as fallback
            try:
                dm_response = client.conversations_open(users=[user_id])
                if dm_response.get('ok'):
                    fallback_channel = dm_response['channel']['id']
                    await say(
                        channel=fallback_channel,
                        text=f"I couldn't send the summary to the original channel. Here's the summary of {file['name']}:\n\n{summary}"
                    )
                    logger.info(f"✅ Sent summary to fallback DM channel")
                else:
                    raise Exception("Could not open DM channel")
            except Exception as dm_error:
                logger.error(f"Failed to send to fallback channel: {str(dm_error)}")
                raise Exception("Could not send the summary to any channel")
        
    except Exception as e:
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }
        logger.error("❌ Error processing file:")
        logger.error(json.dumps(error_details, indent=2))
        
        # Try to send error message to user's DM
        try:
            dm_response = client.conversations_open(users=[user_id])
            if dm_response.get('ok'):
                error_channel = dm_response['channel']['id']
                await say(
                    channel=error_channel,
                    text=f"Sorry, I encountered an error processing {file['name']}. Please try again."
                )
                logger.info("✅ Sent error message to user's DM")
            else:
                logger.error("Could not send error message to user's DM")
        except Exception as dm_error:
            logger.error(f"Failed to send error message: {str(dm_error)}")
        
        # Re-raise the original exception for the main error handler
        raise

@slack_app.command("/reset_limits")
async def reset_limits(ack, command, say):
    """Reset monthly usage limits (admin only)."""
    # Check if user is admin (you should implement proper admin check)
    if command['user_id'] not in ['ADMIN_USER_ID']:  # Replace with actual admin check
        await say("This command is only available to administrators.")
        return
    
    usage.truncate()
    await say("Usage limits have been reset for all users.")

# Create FastAPI handler
handler = SlackRequestHandler(slack_app)

@app.get("/login")
async def login():
    """Redirect to Slack OAuth login."""
    return RedirectResponse(get_login_url())

@app.get("/slack/oauth/callback")
async def slack_oauth_callback(code: str):
    """Handle Slack OAuth callback."""
    try:
        # Handle OAuth callback
        result = await handle_slack_oauth(code)
        
        # Store user info in database
        user_info = result['user']
        user = get_user_status(user_info['id'], user_info['email'], user_info['team']['id'])
        
        # Create response with token
        response = RedirectResponse(url="/dashboard")
        response.set_cookie(
            key="access_token",
            value=result['access_token'],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400  # 1 day
        )
        return response
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# Add authentication dependency
async def get_current_user(request: Request):
    """Get current user from session token."""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        user_info = verify_token(token)
        return user_info
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid session")

# Add protected dashboard endpoint
@app.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    """Protected dashboard endpoint."""
    return {
        "user": {
            "slack_id": user["slack_id"],
            "email": user["email"]
        },
        "status": "authenticated"
    }

@app.post("/process-pdf")
async def process_pdf(request: PDFRequest, user: dict = Depends(get_current_user)):
    """Process a PDF from a URL and return its summary."""
    try:
        # Download the PDF
        response = requests.get(request.pdf_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF")
        
        # Extract text and generate summary
        pdf_text = extract_text_from_pdf(response.content)
        summary = generate_summary(pdf_text)
        
        return {
            "status": "success",
            "summary": summary,
            "user": user["slack_id"]
        }
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def init_db():
    """Initialize database with proper schema."""
    # Ensure users table has required fields
    User = Query()
    if not users.get(User.user_id.exists()):
        users.insert({
            'user_id': 'admin',
            'team_id': 'admin_workspace',
            'email': 'admin@example.com',
            'status': 'pro',
            'created_at': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat()
        })
    
    # Ensure usage table has required fields
    Usage = Query()
    if not usage.get(Usage.user_id.exists()):
        usage.insert({
            'user_id': 'admin',
            'team_id': 'admin_workspace',
            'month': datetime.now().strftime('%Y-%m'),
            'timestamp': datetime.now().isoformat(),
            'file_name': 'test.pdf'
        })

# Initialize database schema
init_db()

@slack_app.event("app_home_opened")
async def handle_app_home_opened(event, say, client):
    """Handle app home opened event."""
    try:
        user_id = event["user"]
        team_id = event["team_id"]
        
        # Get user status and subscription info
        user = get_user_status(user_id, team_id=team_id)
        usage_stats = get_usage_stats(user_id, team_id)
        
        # Check for subscription expiry
        expiry_info = check_subscription_expiry(user_id, team_id)
        
        # Show authenticated view
        await client.views_publish(
            user_id=user_id,
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Welcome back, <@{user_id}>!"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Subscription Status:* {usage_stats['status'].title()}\n"
                                f"*Current Tier:* {usage_stats['tier'].title()}\n"
                                f"*Usage:* {usage_stats['current_usage']}/{usage_stats['limit']} summaries this month"
                            )
                        }
                    }
                ]
            }
        )
        
        # Add expiry warning if needed
        if expiry_info:
            await client.chat_postMessage(
                channel=user_id,
                text=f"⚠️ Your {expiry_info['tier']} subscription will expire in {expiry_info['days_remaining']} days. "
                     f"Renew now to maintain your benefits: {UPGRADE_LINK}"
            )
            
    except Exception as e:
        logger.error(f"Error in app home opened: {str(e)}")
        raise

@slack_app.action("login_button")
async def handle_login_button(ack, body, client):
    """Handle login button click."""
    try:
        # Acknowledge the action
        await ack()
        
        # Get the login URL
        login_url = get_login_url()
        
        # Open the OAuth URL in a new window
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "title": {
                    "type": "plain_text",
                    "text": "Login to PDF Summarizer"
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Click below to login with Slack:"
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
                                "url": login_url
                            }
                        ]
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error handling login button: {str(e)}")
        raise

def get_monthly_usage(user_id: str, team_id: str) -> int:
    """Get user's monthly usage count."""
    current_month = datetime.now().strftime('%Y-%m')
    Usage = Query()
    return usage.count(
        (Usage.user_id == user_id) & 
        (Usage.team_id == team_id) &
        (Usage.month == current_month)
    )

# Add new subscription endpoints
@app.post("/subscription/upgrade")
async def upgrade_subscription(
    tier: str,
    user: dict = Depends(get_current_user)
):
    """Handle subscription upgrade."""
    try:
        if tier not in ['standard', 'premium']:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")
            
        success = handle_subscription_change(
            user['slack_id'],
            user['team_id'],
            tier
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update subscription")
            
        return {"status": "success", "message": f"Upgraded to {tier} tier"}
    except Exception as e:
        logger.error(f"Error upgrading subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/subscription/status")
async def get_subscription_status(user: dict = Depends(get_current_user)):
    """Get current subscription status."""
    try:
        stats = get_usage_stats(user['slack_id'], user['team_id'])
        return stats
    except Exception as e:
        logger.error(f"Error getting subscription status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug") 