"""ثابت‌های دستیار عمومی."""

FEATURE_PUBLIC_ASSISTANT = 'public_assistant'

MAX_USER_MESSAGE_LENGTH = 1200
MAX_HISTORY_MESSAGES = 8
MAX_RETRIEVAL_CHUNKS = 6
CHUNK_MAX_CHARS = 900

DEFAULT_SUGGESTED_QUESTIONS = [
    'فایلینگ دیوار چیست و برای چه کسانی مناسب است؟',
    'چطور ثبت‌نام کنم و به میزکار دسترسی بگیرم؟',
    'تفاوت CRM، فایلینگ و استخراج آگهی چیست؟',
    'هدیه آزمایشی هفت‌روزه بعد از ثبت‌نام چطور فعال می‌شود؟',
    'استخراج آگهی با اندروید و ویندوز چه تفاوتی دارد؟',
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
