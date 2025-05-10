import os
from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

class FeatureFlags:
    """Feature flag management system."""
    
    @staticmethod
    def is_enabled(flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return os.getenv(f"ENABLE_{flag_name.upper()}", "false").lower() == "true"
    
    @staticmethod
    def require_flag(flag_name: str):
        """Decorator to require a feature flag for a function."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                if not FeatureFlags.is_enabled(flag_name):
                    logger.warning(f"Feature {flag_name} is disabled. Skipping {func.__name__}")
                    return None
                return func(*args, **kwargs)
            return wrapper
        return decorator

# Feature flag names
SUBSCRIPTION_SYSTEM = "SUBSCRIPTION_SYSTEM"
TRIAL_PERIOD = "TRIAL_PERIOD"
USAGE_TRACKING = "USAGE_TRACKING"
SUBSCRIPTION_LIMITS = "SUBSCRIPTION_LIMITS"
SUBSCRIPTION_UPGRADE = "SUBSCRIPTION_UPGRADE"

# Helper functions
def is_subscription_enabled() -> bool:
    """Check if subscription system is enabled."""
    return FeatureFlags.is_enabled(SUBSCRIPTION_SYSTEM)

def is_trial_enabled() -> bool:
    """Check if trial period is enabled."""
    return is_subscription_enabled() and FeatureFlags.is_enabled(TRIAL_PERIOD)

def is_usage_tracking_enabled() -> bool:
    """Check if usage tracking is enabled."""
    return is_subscription_enabled() and FeatureFlags.is_enabled(USAGE_TRACKING)

def is_subscription_limits_enabled() -> bool:
    """Check if subscription limits are enabled."""
    return is_subscription_enabled() and FeatureFlags.is_enabled(SUBSCRIPTION_LIMITS)

def is_subscription_upgrade_enabled() -> bool:
    """Check if subscription upgrade is enabled."""
    return is_subscription_enabled() and FeatureFlags.is_enabled(SUBSCRIPTION_UPGRADE) 