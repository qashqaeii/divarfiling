"""ثابت‌های دستیار عمومی."""

FEATURE_PUBLIC_ASSISTANT = 'public_assistant'

MAX_USER_MESSAGE_LENGTH = 1200
MAX_HISTORY_MESSAGES = 8
MAX_RETRIEVAL_CHUNKS = 6
MIN_RETRIEVAL_SCORE = 2.5
CHUNK_MAX_CHARS = 900

DEFAULT_SUGGESTED_QUESTIONS = [
    'فایلینگ دیوار چه امکاناتی دارد؟',
    'چطور استخراج آگهی انجام دهم؟',
    'CRM چه کمکی به مشاور املاک می‌کند؟',
]

OFF_TOPIC_HINTS = (
    'پزشک',
    'دارو',
    'سیاست',
    'انتخابات',
    'برنامه‌نویسی پایتون',
    'کد نویسی',
    'weather',
    'bitcoin',
)
