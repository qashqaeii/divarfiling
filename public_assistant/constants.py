"""ثابت‌های دستیار عمومی."""

FEATURE_PUBLIC_ASSISTANT = 'public_assistant'

MAX_USER_MESSAGE_LENGTH = 1200
MAX_HISTORY_MESSAGES = 8
MAX_RETRIEVAL_CHUNKS = 6
MIN_RETRIEVAL_SCORE = 2.5
CHUNK_MAX_CHARS = 900

DEFAULT_SUGGESTED_QUESTIONS = [
    'فایلینگ دیوار چیست و با دیوار معمولی چه تفاوتی دارد؟',
    'تفاوت CRM، فایلینگ و استخراج آگهی چیست؟',
    'چطور لایسنس فعال کنم و هدیه ۷ روزه چطور کار می‌کند؟',
    'استخراج تکی و گروهی — شماره تماس هم می‌آید؟',
    'چطور مخاطب CRM ثبت کنم و فایل را با مشتری تطبیق بدهم؟',
    'امکانات هوش مصنوعی میزکار و محدودیت‌هایش چیست؟',
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
