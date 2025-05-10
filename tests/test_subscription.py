import pytest
from datetime import datetime, timedelta
import os
from subscription_manager import (
    get_subscription_limits,
    check_usage_limit,
    get_usage_stats,
    handle_subscription_change,
    check_subscription_expiry,
    SUBSCRIPTION_LIMITS
)
from migrations import (
    migrate_subscription_schema,
    initialize_trial_period,
    check_trial_status,
    update_subscription
)

# Test data
TEST_USER_ID = "U1234567890"
TEST_TEAM_ID = "T1234567890"
TEST_EMAIL = "test@example.com"

@pytest.fixture
def setup_test_user():
    """Setup test user with trial period."""
    migrate_subscription_schema()
    initialize_trial_period(TEST_USER_ID, TEST_TEAM_ID)
    return True

def test_trial_period_initialization(setup_test_user):
    """Test trial period initialization and checking."""
    # Check trial status
    trial_status = check_trial_status(TEST_USER_ID, TEST_TEAM_ID)
    assert trial_status['in_trial'] == True
    assert trial_status['days_remaining'] <= 7
    
    # Get subscription limits during trial
    limits = get_subscription_limits(TEST_USER_ID, TEST_TEAM_ID)
    assert limits['limit'] == float('inf')
    assert limits['status'] == 'trial'

def test_subscription_limits(setup_test_user):
    """Test subscription limits for different tiers."""
    # Test standard tier
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'standard')
    limits = get_subscription_limits(TEST_USER_ID, TEST_TEAM_ID)
    assert limits['limit'] == SUBSCRIPTION_LIMITS['standard']
    assert limits['status'] == 'active'
    assert limits['tier'] == 'standard'
    
    # Test premium tier
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'premium')
    limits = get_subscription_limits(TEST_USER_ID, TEST_TEAM_ID)
    assert limits['limit'] == SUBSCRIPTION_LIMITS['premium']
    assert limits['status'] == 'active'
    assert limits['tier'] == 'premium'

def test_usage_tracking(setup_test_user):
    """Test usage tracking and limits."""
    # Check initial usage
    stats = get_usage_stats(TEST_USER_ID, TEST_TEAM_ID)
    assert stats['current_usage'] == 0
    assert stats['status'] == 'trial'
    assert stats['limit'] == float('inf')
    
    # Test usage limit check during trial
    assert check_usage_limit(TEST_USER_ID, TEST_TEAM_ID) == True
    
    # Switch to standard tier and test limits
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'standard')
    stats = get_usage_stats(TEST_USER_ID, TEST_TEAM_ID)
    assert stats['limit'] == SUBSCRIPTION_LIMITS['standard']
    assert stats['status'] == 'active'
    assert stats['tier'] == 'standard'

def test_subscription_expiry(setup_test_user):
    """Test subscription expiry checking."""
    # Set subscription to standard tier
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'standard')
    
    # Check expiry
    expiry_info = check_subscription_expiry(TEST_USER_ID, TEST_TEAM_ID)
    assert expiry_info is not None
    assert expiry_info['days_remaining'] <= 30
    assert expiry_info['tier'] == 'standard'

def test_invalid_subscription_tier():
    """Test handling of invalid subscription tier."""
    with pytest.raises(Exception):
        handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'invalid_tier')

def test_nonexistent_user():
    """Test handling of nonexistent user."""
    limits = get_subscription_limits('nonexistent', TEST_TEAM_ID)
    assert limits['status'] == 'free'
    assert limits['limit'] == SUBSCRIPTION_LIMITS['free']

def test_subscription_upgrade_downgrade(setup_test_user):
    """Test subscription upgrade and downgrade paths."""
    # Start with standard tier
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'standard')
    limits = get_subscription_limits(TEST_USER_ID, TEST_TEAM_ID)
    assert limits['tier'] == 'standard'
    assert limits['limit'] == SUBSCRIPTION_LIMITS['standard']
    
    # Upgrade to premium
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'premium')
    limits = get_subscription_limits(TEST_USER_ID, TEST_TEAM_ID)
    assert limits['tier'] == 'premium'
    assert limits['limit'] == SUBSCRIPTION_LIMITS['premium']
    
    # Downgrade back to standard
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'standard')
    limits = get_subscription_limits(TEST_USER_ID, TEST_TEAM_ID)
    assert limits['tier'] == 'standard'
    assert limits['limit'] == SUBSCRIPTION_LIMITS['standard']

def test_trial_to_paid_transition(setup_test_user):
    """Test transition from trial to paid subscription."""
    # Verify trial status
    trial_status = check_trial_status(TEST_USER_ID, TEST_TEAM_ID)
    assert trial_status['in_trial'] == True
    
    # Transition to paid subscription
    handle_subscription_change(TEST_USER_ID, TEST_TEAM_ID, 'standard')
    
    # Verify new status
    trial_status = check_trial_status(TEST_USER_ID, TEST_TEAM_ID)
    assert trial_status['in_trial'] == False
    
    limits = get_subscription_limits(TEST_USER_ID, TEST_TEAM_ID)
    assert limits['status'] == 'active'
    assert limits['tier'] == 'standard'
    assert limits['limit'] == SUBSCRIPTION_LIMITS['standard'] 