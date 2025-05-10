from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
from tinydb import TinyDB, Query
from migrations import check_trial_status, update_subscription
from feature_flags import (
    is_subscription_enabled,
    is_trial_enabled,
    is_usage_tracking_enabled,
    is_subscription_limits_enabled,
    is_subscription_upgrade_enabled,
    FeatureFlags
)

logger = logging.getLogger(__name__)

# Initialize database
db = TinyDB('db.json')
users = db.table('users')
usage = db.table('usage')

# Subscription limits
SUBSCRIPTION_LIMITS = {
    'trial': float('inf'),  # Unlimited during trial
    'standard': 100,        # 100 summaries per month
    'premium': 1000,        # 1000 summaries per month
    'free': 10             # 10 summaries per month
}

@FeatureFlags.require_flag('SUBSCRIPTION_SYSTEM')
def get_subscription_limits(user_id: str, team_id: str) -> Dict:
    """Get user's subscription limits and status."""
    try:
        User = Query()
        user = users.get((User.user_id == user_id) & (User.team_id == team_id))
        
        if not user:
            return {'limit': SUBSCRIPTION_LIMITS['free'], 'status': 'free'}
            
        # Check trial status first if trial is enabled
        if is_trial_enabled():
            trial_status = check_trial_status(user_id, team_id)
            if trial_status['in_trial']:
                return {
                    'limit': SUBSCRIPTION_LIMITS['trial'],
                    'status': 'trial',
                    'days_remaining': trial_status['days_remaining']
                }
            
        # Check subscription status
        subscription_status = user.get('subscription_status', 'free')
        subscription_tier = user.get('subscription_tier', 'standard')
        
        return {
            'limit': SUBSCRIPTION_LIMITS[subscription_tier],
            'status': subscription_status,
            'tier': subscription_tier
        }
    except Exception as e:
        logger.error(f"Error getting subscription limits: {str(e)}")
        return {'limit': SUBSCRIPTION_LIMITS['free'], 'status': 'free'}

@FeatureFlags.require_flag('SUBSCRIPTION_LIMITS')
def check_usage_limit(user_id: str, team_id: str) -> bool:
    """Check if user has exceeded their subscription limit."""
    try:
        if not is_subscription_enabled():
            return True
            
        limits = get_subscription_limits(user_id, team_id)
        if limits['limit'] == float('inf'):  # Trial period
            return True
            
        current_month = datetime.now().strftime('%Y-%m')
        Usage = Query()
        monthly_usage = usage.count(
            (Usage.user_id == user_id) & 
            (Usage.team_id == team_id) &
            (Usage.month == current_month)
        )
        
        return monthly_usage < limits['limit']
    except Exception as e:
        logger.error(f"Error checking usage limit: {str(e)}")
        return False

@FeatureFlags.require_flag('USAGE_TRACKING')
def get_usage_stats(user_id: str, team_id: str) -> Dict:
    """Get user's usage statistics."""
    try:
        if not is_subscription_enabled():
            return {
                'current_usage': 0,
                'limit': float('inf'),
                'status': 'unlimited'
            }
            
        limits = get_subscription_limits(user_id, team_id)
        current_month = datetime.now().strftime('%Y-%m')
        Usage = Query()
        
        monthly_usage = usage.count(
            (Usage.user_id == user_id) & 
            (Usage.team_id == team_id) &
            (Usage.month == current_month)
        )
        
        return {
            'current_usage': monthly_usage,
            'limit': limits['limit'],
            'status': limits['status'],
            'tier': limits.get('tier', 'free'),
            'days_remaining': limits.get('days_remaining', None)
        }
    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}")
        return {
            'current_usage': 0,
            'limit': SUBSCRIPTION_LIMITS['free'],
            'status': 'free'
        }

@FeatureFlags.require_flag('SUBSCRIPTION_UPGRADE')
def handle_subscription_change(user_id: str, team_id: str, new_tier: str) -> bool:
    """Handle subscription tier change."""
    try:
        if not is_subscription_enabled():
            return False
        return update_subscription(user_id, team_id, new_tier, 'active')
    except Exception as e:
        logger.error(f"Error handling subscription change: {str(e)}")
        return False

@FeatureFlags.require_flag('SUBSCRIPTION_SYSTEM')
def check_subscription_expiry(user_id: str, team_id: str) -> Optional[Dict]:
    """Check if subscription is about to expire."""
    try:
        if not is_subscription_enabled():
            return None
            
        User = Query()
        user = users.get((User.user_id == user_id) & (User.team_id == team_id))
        
        if not user or user.get('subscription_status') != 'active':
            return None
            
        end_date = datetime.fromisoformat(user['subscription_end_date'])
        days_remaining = (end_date - datetime.now()).days
        
        if days_remaining <= 3:  # Notify if 3 days or less remaining
            return {
                'days_remaining': days_remaining,
                'tier': user.get('subscription_tier'),
                'end_date': end_date.isoformat()
            }
            
        return None
    except Exception as e:
        logger.error(f"Error checking subscription expiry: {str(e)}")
        return None 