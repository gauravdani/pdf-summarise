from tinydb import TinyDB, Query
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

def migrate_subscription_schema():
    """Migrate database to include subscription fields."""
    try:
        db = TinyDB('db.json')
        users = db.table('users')
        
        # Add subscription fields to existing users
        User = Query()
        for user in users.all():
            if 'subscription_status' not in user:
                users.update({
                    'subscription_status': 'trial' if not user.get('status') == 'pro' else 'active',
                    'subscription_tier': 'premium' if user.get('status') == 'pro' else 'standard',
                    'trial_start_date': datetime.now().isoformat(),
                    'subscription_start_date': None,
                    'subscription_end_date': None,
                    'payment_provider': None,
                    'payment_customer_id': None
                }, User.user_id == user['user_id'])
        
        logger.info("Successfully migrated subscription schema")
        return True
    except Exception as e:
        logger.error(f"Error migrating subscription schema: {str(e)}")
        return False

def initialize_trial_period(user_id: str, team_id: str) -> bool:
    """Initialize trial period for new users"""
    try:
        db = TinyDB('db.json')
        users = db.table('users')
        trial_end = datetime.now() + timedelta(days=int(os.getenv('TRIAL_PERIOD_DAYS', 7)))
        
        users.update({
            'subscription_status': 'trial',
            'subscription_tier': 'trial',
            'trial_start': datetime.now().isoformat(),
            'trial_end': trial_end.isoformat()
        }, (Query().user_id == user_id) & (Query().team_id == team_id))
        
        logger.info(f"Initialized trial period for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error initializing trial period: {str(e)}")
        return False

def check_trial_status(user_id: str, team_id: str) -> dict:
    """Check if user is in trial period and its status."""
    try:
        db = TinyDB('db.json')
        users = db.table('users')
        User = Query()
        
        user = users.get((User.user_id == user_id) & (User.team_id == team_id))
        if not user or user.get('subscription_status') != 'trial':
            return {'in_trial': False}
            
        trial_start = datetime.fromisoformat(user['trial_start_date'])
        trial_end = trial_start + timedelta(days=7)
        now = datetime.now()
        
        return {
            'in_trial': True,
            'days_remaining': (trial_end - now).days,
            'trial_end_date': trial_end.isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking trial status: {str(e)}")
        return {'in_trial': False}

def update_subscription(user_id: str, team_id: str, tier: str, status: str) -> bool:
    """Update user's subscription status and tier."""
    try:
        db = TinyDB('db.json')
        users = db.table('users')
        User = Query()
        
        users.update({
            'subscription_status': status,
            'subscription_tier': tier,
            'subscription_start_date': datetime.now().isoformat(),
            'subscription_end_date': (datetime.now() + timedelta(days=30)).isoformat()
        }, (User.user_id == user_id) & (User.team_id == team_id))
        
        logger.info(f"Updated subscription for user {user_id} to {tier}")
        return True
    except Exception as e:
        logger.error(f"Error updating subscription: {str(e)}")
        return False 