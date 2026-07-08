"""ثابت‌های سیستم تیکت پشتیبانی."""

TICKET_STATUS_OPEN = 'open'
TICKET_STATUS_IN_REVIEW = 'in_review'
TICKET_STATUS_ANSWERED = 'answered'
TICKET_STATUS_WAITING_USER = 'waiting_user'
TICKET_STATUS_CLOSED = 'closed'

TICKET_STATUS_CHOICES = [
    (TICKET_STATUS_OPEN, 'باز'),
    (TICKET_STATUS_IN_REVIEW, 'در حال بررسی'),
    (TICKET_STATUS_ANSWERED, 'پاسخ داده شده'),
    (TICKET_STATUS_WAITING_USER, 'منتظر پاسخ کاربر'),
    (TICKET_STATUS_CLOSED, 'بسته شده'),
]

TICKET_OPEN_STATUSES = {
    TICKET_STATUS_OPEN,
    TICKET_STATUS_IN_REVIEW,
    TICKET_STATUS_ANSWERED,
    TICKET_STATUS_WAITING_USER,
}

TICKET_PRIORITY_LOW = 'low'
TICKET_PRIORITY_NORMAL = 'normal'
TICKET_PRIORITY_HIGH = 'high'
TICKET_PRIORITY_URGENT = 'urgent'

TICKET_PRIORITY_CHOICES = [
    (TICKET_PRIORITY_LOW, 'کم'),
    (TICKET_PRIORITY_NORMAL, 'معمولی'),
    (TICKET_PRIORITY_HIGH, 'مهم'),
    (TICKET_PRIORITY_URGENT, 'فوری'),
]

TICKET_CATEGORY_ACCOUNT = 'account'
TICKET_CATEGORY_PAYMENT = 'payment'
TICKET_CATEGORY_LICENSE = 'license'
TICKET_CATEGORY_SCRAPER = 'scraper'
TICKET_CATEGORY_UPLOAD = 'upload'
TICKET_CATEGORY_FILING = 'filing'
TICKET_CATEGORY_CRM = 'crm'
TICKET_CATEGORY_FEATURE = 'feature'
TICKET_CATEGORY_OTHER = 'other'

TICKET_CATEGORY_CHOICES = [
    (TICKET_CATEGORY_ACCOUNT, 'مشکل ورود یا حساب کاربری'),
    (TICKET_CATEGORY_PAYMENT, 'مشکل پرداخت یا اشتراک'),
    (TICKET_CATEGORY_LICENSE, 'مشکل لایسنس ربات'),
    (TICKET_CATEGORY_SCRAPER, 'مشکل ربات استخراج آگهی'),
    (TICKET_CATEGORY_UPLOAD, 'مشکل آپلود فایل'),
    (TICKET_CATEGORY_FILING, 'مشکل فایلینگ و مجموعه‌ها'),
    (TICKET_CATEGORY_CRM, 'مشکل CRM و مشتریان'),
    (TICKET_CATEGORY_FEATURE, 'پیشنهاد یا درخواست قابلیت جدید'),
    (TICKET_CATEGORY_OTHER, 'سایر موارد'),
]

TICKET_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
TICKET_ATTACHMENT_ALLOWED_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.zip',
})

TICKET_STATUS_BADGE_CLASS = {
    TICKET_STATUS_OPEN: 'sup-badge--open',
    TICKET_STATUS_IN_REVIEW: 'sup-badge--review',
    TICKET_STATUS_ANSWERED: 'sup-badge--answered',
    TICKET_STATUS_WAITING_USER: 'sup-badge--waiting',
    TICKET_STATUS_CLOSED: 'sup-badge--closed',
}

TICKET_PRIORITY_BADGE_CLASS = {
    TICKET_PRIORITY_LOW: 'sup-priority--low',
    TICKET_PRIORITY_NORMAL: 'sup-priority--normal',
    TICKET_PRIORITY_HIGH: 'sup-priority--high',
    TICKET_PRIORITY_URGENT: 'sup-priority--urgent',
}
