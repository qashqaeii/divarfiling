"""Schema constants for Management AI snapshots and responses."""
from __future__ import annotations

SNAPSHOT_SCHEMA_VERSION = '1.0'

PHASE1_SECTIONS = frozenset({'users', 'sales', 'licenses', 'crm', 'executive'})

SECTION_LABELS_FA = {
    'users': 'کاربران',
    'sales': 'فروش',
    'licenses': 'لایسنس',
    'crm': 'CRM',
    'executive': 'مدیریت کلان',
}

MAX_SUMMARY_SENTENCES = 4
MAX_INSIGHTS = 5
MAX_ACTIONS = 5
MAX_RISKS = 3
MAX_OPPORTUNITIES = 3

PII_KEY_PATTERNS = (
    'phone',
    'email',
    'password',
    'token',
    'cookie',
    'session',
    'api_key',
    'secret',
    'full_name',
    'first_name',
    'last_name',
    'address',
    'ticket_body',
    'notes',
    'message_body',
)
