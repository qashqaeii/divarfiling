"""ثابت‌های دستیار عمومی."""

FEATURE_PUBLIC_ASSISTANT = 'public_assistant'

MAX_USER_MESSAGE_LENGTH = 1200
MAX_HISTORY_MESSAGES = 8
MAX_RETRIEVAL_CHUNKS = 8
MIN_RETRIEVAL_SCORE = 2.5
CHUNK_MAX_CHARS = 900

DEFAULT_SUGGESTED_QUESTIONS = [
    'کدام پلن برای من مناسب‌تر است؟',
    'قیمت پلن‌های شخصی چقدر است؟',
    'پلن آژانس برای چند مشاور چطور حساب می‌شود؟',
    'فرق هدیه ۷ روزه با پلن آزمایشی چیست؟',
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
