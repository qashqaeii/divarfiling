"""Management AI Analytics for Admin Panel."""
from accounts.services.management_ai.service import (
    generate_analysis,
    get_latest_analysis,
    is_management_ai_enabled,
)

__all__ = [
    'generate_analysis',
    'get_latest_analysis',
    'is_management_ai_enabled',
]
