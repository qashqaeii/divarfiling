"""ثابت‌های دستیار عمومی."""

FEATURE_PUBLIC_ASSISTANT = 'public_assistant'

MAX_USER_MESSAGE_LENGTH = 1200
MAX_HISTORY_MESSAGES = 8
MAX_RETRIEVAL_CHUNKS = 8
MIN_RETRIEVAL_SCORE = 2.5
CHUNK_MAX_CHARS = 900

DEFAULT_SUGGESTED_QUESTIONS = [
    'چطور استخراج آگهی را شروع کنم؟',
    'چطور فایل‌ها را در زونکن مرتب کنم؟',
    'چرا برای مشتری فایل پیشنهاد نمی‌شود؟',
    'چطور یادآوری تماس بسازم؟',
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
