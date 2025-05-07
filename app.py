import os
from datetime import datetime
from typing import Optional
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
from slack_oauth import handle_slack_oauth, get_login_url, verify_token, create_jwt
from slack_sdk.errors import SlackApiError

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
            'last_login': datetime.now().isoformat()
        }
        users.insert(user)
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
        # Check if user has exceeded limit
        if not check_usage_limit(user_id, team_id):
            logger.warning(f"⚠️ User {user_id} has exceeded their monthly limit")
            await say(
                thread_ts=event['ts'],
                text=f"You've hit your monthly limit of {MONTHLY_LIMIT} summaries. Upgrade to Pro to continue: {UPGRADE_LINK}"
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
            logger.info(f"📄 Processing file: {file['name']}")
            if file['filetype'] != 'pdf':
                logger.warning(f"⚠️ Non-PDF file received: {file['filetype']}")
                continue
            
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
                logger.info(f"⬇️ Downloading file from: {file_url}")
                try:
                    # Get file info first
                    file_info = client.files_info(file=file['id'])
                    if not file_info.get('ok'):
                        raise Exception(f"Failed to get file info: {file_info.get('error')}")
                    
                    # Download the file using the private URL
                    file_url = file_info['file']['url_private_download']
                    file_response = requests.get(
                        file_url,
                        headers={'Authorization': f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
                    )
                    
                    if file_response.status_code != 200:
                        raise Exception(f"Failed to download file: HTTP {file_response.status_code}")
                    
                    # Save the file temporarily
                    temp_file_path = f"temp_{file['id']}.pdf"
                    with open(temp_file_path, 'wb') as f:
                        f.write(file_response.content)
                    temp_files.append(temp_file_path)
                    logger.info(f"✅ File downloaded successfully. Size: {len(file_response.content)} bytes")
                except Exception as e:
                    logger.error(f"❌ Error downloading file: {str(e)}")
                    raise
                
                # Extract text and generate summary
                logger.info("📝 Starting text extraction from PDF")
                try:
                    pdf_text = extract_text_from_pdf(file_response.content)
                    logger.info(f"✅ Text extraction completed. Length: {len(pdf_text)} characters")
                except Exception as e:
                    logger.error(f"❌ Error extracting text from PDF: {str(e)}")
                    raise
                
                # Generate summary
                logger.info("🤖 Generating summary with OpenAI")
                try:
                    summary = generate_summary(pdf_text)
                    logger.info(f"✅ Summary generated successfully. Length: {len(summary)} characters")
                    logger.debug(f"Generated summary: {summary}")
                except Exception as e:
                    logger.error(f"❌ Error generating summary: {str(e)}")
                    raise
                
                # Record usage
                record_usage(user_id, team_id, file['name'])
                
                # Send summary
                logger.info("📤 Sending summary to Slack")
                await say(
                    thread_ts=event['ts'],
                    text=f"Here's the summary of {file['name']}:\n\n{summary}"
                )
                logger.info(f"✅ Successfully processed and summarized {file['name']}")
                
            except Exception as e:
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                logger.error("❌ Error processing file:")
                logger.error(json.dumps(error_details, indent=2))
                
                await say(
                    thread_ts=event['ts'],
                    text=f"Sorry, I encountered an error processing {file['name']}. Please try again."
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
    
    logger.info("="*80)

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
                    logger.info(f"📄 Processing file: {file.get('name')}")
                    if file.get('filetype') != 'pdf':
                        logger.info(f"⚠️ Non-PDF file received: {file.get('filetype')}")
                        continue
                    
                    try:
                        # Download file
                        response = slack_app.client.files_info(file=file['id'])
                        if not response.get('ok'):
                            logger.error(f"❌ Slack API error: {response.get('error')}")
                            raise Exception(f"Slack API error: {response.get('error')}")
                            
                        file_url = response['file']['url_private_download']
                        logger.info(f"⬇️ Downloading file from: {file_url}")
                        
                        # Download the file
                        logger.info(f"⬇️ Downloading file from: {file_url}")
                        try:
                            # Get file info first
                            file_info = slack_app.client.files_info(file=file['id'])
                            if not file_info.get('ok'):
                                raise Exception(f"Failed to get file info: {file_info.get('error')}")
                            
                            # Download the file using the private URL
                            file_url = file_info['file']['url_private_download']
                            file_response = requests.get(
                                file_url,
                                headers={'Authorization': f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
                            )
                            
                            if file_response.status_code != 200:
                                raise Exception(f"Failed to download file: HTTP {file_response.status_code}")
                            
                            # Save the file temporarily
                            temp_file_path = f"temp_{file['id']}.pdf"
                            with open(temp_file_path, 'wb') as f:
                                f.write(file_response.content)
                            logger.info(f"✅ File downloaded successfully. Size: {len(file_response.content)} bytes")
                        except Exception as e:
                            logger.error(f"❌ Error downloading file: {str(e)}")
                            raise
                        
                        # Extract text and generate summary
                        logger.info("📝 Starting text extraction from PDF")
                        try:
                            pdf_text = extract_text_from_pdf(file_response.content)
                            logger.info(f"✅ Text extraction completed. Length: {len(pdf_text)} characters")
                        except Exception as e:
                            logger.error(f"❌ Error extracting text from PDF: {str(e)}")
                            raise
                        
                        logger.info("🤖 Generating summary")
                        summary = generate_summary(pdf_text)
                        logger.info(f"✅ Summary generated successfully. Length: {len(summary)} characters")
                        
                        # Record usage
                        record_usage(body_json['event']['user'], body_json['event']['team'], file.get('name'))
                        
                        # Send summary
                        logger.info("📤 Sending summary to Slack")
                        slack_app.client.chat_postMessage(
                            channel=body_json['event']['channel'],
                            thread_ts=thread_ts,
                            text=f"Here's the summary of {file.get('name')}:\n\n{summary}"
                        )
                        logger.info(f"✅ Successfully processed and summarized {file.get('name')}")
                        
                    except Exception as e:
                        error_details = {
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "traceback": traceback.format_exc()
                        }
                        logger.error("❌ Error processing file:")
                        logger.error(json.dumps(error_details, indent=2))
                        
                        slack_app.client.chat_postMessage(
                            channel=body_json['event']['channel'],
                            thread_ts=thread_ts,
                            text=f"Sorry, I encountered an error processing {file.get('name')}. Please try again."
                        )
            
        return {"ok": True}
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")
    except Exception as e:
        logger.error(f"❌ Error handling request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    logger.info("="*80)

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
        
        # Get user status
        user = get_user_status(user_id, team_id=team_id)
        
        # Check if user is authenticated
        if user.get('email'):
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
                                "text": f"Your usage this month: {get_monthly_usage(user_id, team_id)}/10"
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
            )
        else:
            # Show unauthenticated view
            await client.views_publish(
                user_id=user_id,
                view={
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
            )
    except Exception as e:
        logger.error(f"Error handling app home opened: {str(e)}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug") 