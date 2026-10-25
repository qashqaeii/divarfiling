"""ثابت‌های تالار گفتگو."""
from django.conf import settings

RETENTION_DAYS = getattr(settings, 'COMMUNITY_FORUM_RETENTION_DAYS', 30)
MAX_BODY_LENGTH = getattr(settings, 'COMMUNITY_FORUM_MAX_BODY_LENGTH', 2000)
MIN_SEND_INTERVAL_SECONDS = getattr(settings, 'COMMUNITY_FORUM_MIN_SEND_INTERVAL', 3)
MAX_MESSAGES_PER_MINUTE = getattr(settings, 'COMMUNITY_FORUM_MAX_PER_MINUTE', 10)
MAX_MESSAGES_PER_HOUR = getattr(settings, 'COMMUNITY_FORUM_MAX_PER_HOUR', 60)
EDIT_WINDOW_MINUTES = 5

ALLOWED_REACTIONS = frozenset({'👍', '❤️', '👏', '😂', '🙏'})

REPORT_REASONS = (
    ('spam', 'تبلیغات و اسپم'),
    ('inappropriate', 'محتوای نامناسب'),
    ('pii', 'انتشار اطلاعات شخصی'),
    ('fraud', 'کلاهبرداری یا جعل هویت'),
    ('other', 'سایر موارد'),
)

RESERVED_DISPLAY_NAMES = frozenset({
    'پشتیبانی',
    'مدیر',
    'مدیریت',
    'فایلینگ دیوار',
    'divar filing',
    'admin',
    'support',
    'moderator',
})

INITIAL_PAGE_SIZE = 30
