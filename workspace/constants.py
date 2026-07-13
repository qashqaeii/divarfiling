"""ثابت‌های workspace — هماهنگ با app_crm_links.py در Tkinter."""

CRM_TYPES = [
    'خریدار', 'فروشنده', 'سازنده', 'مالک', 'مستاجر', 'موجر',
    'سرمایه‌گذار', 'سرنخ', 'متقاضی خرید', 'متقاضی اجاره',
    'فروشنده ملک', 'اشخاص حقوقی',
]
CRM_STATUSES = ['جدید', 'در حال پیگیری', 'بازدید انجام شد', 'قرارداد', 'بایگانی']
CRM_PRIORITIES = ['بالا', 'متوسط', 'پایین']
CRM_PROPERTIES = ['آپارتمان', 'ویلا', 'کلنگی', 'اداری', 'مغازه', 'زمین', 'سایر']
PROPERTY_ADVERTISER_TYPES = ['شخصی', 'مشاور', 'مشاور املاک', 'business', 'مالک']
CRM_SOURCES = ['دیوار', 'معرف', 'ورود به املاک', 'تماس ورودی', 'اینستاگرام', 'سایت', 'تلگرام', 'موبایل', 'سایر']
ACTIVITY_TYPES = [
    'تماس', 'پیامک', 'واتساپ', 'پیام', 'بازدید', 'جلسه', 'پیگیری',
    'یادداشت', 'وظیفه', 'یادآور', 'تغییر وضعیت', 'املاک', 'ایمیل',
]
LISTING_ROLES = [
    'مالک', 'فروشنده', 'خریدار', 'سازنده', 'مستاجر', 'موجر',
    'سرمایه‌گذار', 'سرنخ', 'پیشنهادی', 'متقاضی خرید', 'متقاضی اجاره',
]
DEAL_TYPES = ['فروش', 'خرید', 'رهن و اجاره', 'رهن کامل', 'اجاره', 'پیش‌فروش', 'سرمایه‌گذاری', 'سایر']

PROPERTY_DEAL_MODES = ['فروش', 'رهن و اجاره', 'اجاره', 'پیش‌فروش']
PROPERTY_TX_STATUSES = ['فعال', 'در مذاکره', 'قرارداد', 'فروخته‌شده', 'اجاره‌رفته', 'بایگانی']

PROPERTY_TX_COLORS = {
    'فعال': ('#ecfdf5', '#047857', '#10b981'),
    'در مذاکره': ('#fffbeb', '#b45309', '#f59e0b'),
    'قرارداد': ('#f5f3ff', '#6d28d9', '#8b5cf6'),
    'فروخته‌شده': ('#eff6ff', '#1d4ed8', '#2563eb'),
    'اجاره‌رفته': ('#ecfeff', '#0e7490', '#06b6d4'),
    'بایگانی': ('#f8fafc', '#64748b', '#94a3b8'),
}

CRM_FILTER_SCOPES = ['contacts', 'properties', 'deals']

CRM_FILTER_PARAMS = {
    'contacts': {'q', 'customer_type', 'status', 'priority', 'due', 'sort', 'tag'},
    'properties': {
        'q', 'deal_mode', 'transaction_status', 'property_type', 'publish_status', 'city', 'sort',
        'parking', 'storage', 'elevator', 'rooms',
        'area_min', 'area_max', 'price_min', 'price_max',
        'year_min', 'year_max', 'age_max',
    },
    'deals': {'q', 'stage', 'bucket', 'sort'},
}
PROPERTY_PUBLISH_STATUSES = ['پیش‌نویس', 'منتشرشده', 'مخفی', 'بایگانی']
INTEREST_LEVELS = ['بالا', 'متوسط', 'پایین']

LISTING_TAGS = ['تماس', 'بازدید', 'علاقه‌مند', 'رد', '']

# ستون‌های ویژگی/امکانات خروجی ربات — هماهنگ با export_divar_items.FEATURE_EXCEL_COLUMNS
LISTING_FEATURE_COLUMNS = [
    'تعداد واحد در طبقه',
    'تعداد کل طبقات ساختمان',
    'جهت ساختمان',
    'حیوان خانگی مجاز',
    'نوع آشپزخانه',
    'مناسب برای',
    'جنس کابینت',
    'بازسازی شده',
    'وضعیت واحد',
    'حداقل مدت قرارداد',
    'جنس کف',
    'بالکن',
    'سرویس بهداشتی',
    'سرمایش',
    'گرمایش',
    'تأمین‌کننده آب گرم',
    'تعداد حمام',
    'تعداد سرویس بهداشتی',
    'تعداد پارکینگ',
    'جکوزی',
    'سند',
    'سونا',
    'عرض ملک',
    'قابل معاوضه',
    'مجوز ساخت',
    'نمای ساختمان',
    'وضعیت سند',
    'وضعیت سکونت',
]

LISTING_FEATURE_COMBINED_KEYS = ('ویژگی‌ها و امکانات', 'ویژگی_ها_و_امکانات')

LISTING_FEATURE_GROUPS = (
    {
        'id': 'building',
        'title': 'ویژگی‌های ساختمان',
        'icon': 'fa-building',
        'accent': 'sky',
        'keys': (
            'تعداد واحد در طبقه', 'تعداد کل طبقات ساختمان', 'جهت ساختمان',
            'وضعیت واحد', 'بازسازی شده',
        ),
    },
    {
        'id': 'comfort',
        'title': 'امکانات رفاهی',
        'icon': 'fa-couch',
        'accent': 'violet',
        'keys': (
            'جنس کف', 'بالکن', 'سرویس بهداشتی', 'سرمایش', 'گرمایش',
            'تأمین‌کننده آب گرم', 'نوع آشپزخانه', 'جنس کابینت',
        ),
    },
    {
        'id': 'lifestyle',
        'title': 'شرایط سکونت',
        'icon': 'fa-users',
        'accent': 'emerald',
        'keys': ('حیوان خانگی مجاز', 'مناسب برای', 'حداقل مدت قرارداد', 'وضعیت سکونت'),
    },
    {
        'id': 'legal',
        'title': 'سند و مجوزها',
        'icon': 'fa-file-contract',
        'accent': 'slate',
        'keys': ('سند', 'وضعیت سند', 'مجوز ساخت', 'قابل معاوضه'),
    },
    {
        'id': 'counts',
        'title': 'تعداد و ظرفیت',
        'icon': 'fa-hashtag',
        'accent': 'blue',
        'keys': ('تعداد پارکینگ', 'تعداد حمام', 'تعداد سرویس بهداشتی'),
    },
    {
        'id': 'luxury',
        'title': 'امکانات لوکس',
        'icon': 'fa-spa',
        'accent': 'rose',
        'keys': ('جکوزی', 'سونا'),
    },
    {
        'id': 'exterior',
        'title': 'نما و ابعاد',
        'icon': 'fa-building-columns',
        'accent': 'orange',
        'keys': ('نمای ساختمان', 'عرض ملک'),
    },
)

LISTING_CORE_AMENITIES = (
    {'key': 'آسانسور', 'field': 'elevator', 'icon': 'fa-elevator'},
    {'key': 'پارکینگ', 'field': 'parking', 'icon': 'fa-square-parking'},
    {'key': 'انباری', 'field': 'storage', 'icon': 'fa-box-archive'},
)

# چک‌باکس‌های امکانات در فرم ویرایش ملک CRM (گروه‌بندی‌شده)
PROPERTY_AMENITY_CHECKBOX_GROUPS = (
    {
        'id': 'core',
        'title': 'امکانات اصلی',
        'icon': 'fa-star',
        'items': (
            ('پارکینگ', 'fa-square-parking'),
            ('انباری', 'fa-box-archive'),
            ('آسانسور', 'fa-elevator'),
        ),
    },
    {
        'id': 'building',
        'title': 'امکانات ساختمان',
        'icon': 'fa-building',
        'items': (
            ('بالکن', 'fa-fan'),
            ('تراس', 'fa-tree'),
            ('لابی', 'fa-hotel'),
            ('آیفون تصویری', 'fa-video'),
            ('درب ضدسرقت', 'fa-shield-halved'),
            ('نگهبانی', 'fa-user-shield'),
            ('سرایداری', 'fa-bell-concierge'),
            ('آنتن مرکزی', 'fa-satellite-dish'),
        ),
    },
    {
        'id': 'luxury',
        'title': 'رفاهی و لوکس',
        'icon': 'fa-spa',
        'items': (
            ('استخر', 'fa-water-ladder'),
            ('روف گاردن', 'fa-seedling'),
            ('جکوزی', 'fa-hot-tub-person'),
            ('سونا', 'fa-temperature-high'),
            ('سالن ورزش', 'fa-dumbbell'),
        ),
    },
    {
        'id': 'conditions',
        'title': 'شرایط و وضعیت',
        'icon': 'fa-clipboard-check',
        'items': (
            ('حیوان خانگی مجاز', 'fa-paw'),
            ('قابل معاوضه', 'fa-right-left'),
            ('بازسازی شده', 'fa-hammer'),
            ('سند', 'fa-file-signature'),
            ('مجوز ساخت', 'fa-hard-hat'),
        ),
    },
)

# برچسب‌های بولین شناخته‌شده (چک‌باکس CRM + چیپ‌های دیوار)
PROPERTY_BOOL_AMENITY_LABELS = frozenset(
    label
    for group in PROPERTY_AMENITY_CHECKBOX_GROUPS
    for label, _icon in group['items']
)

BUILDER_BUY_PROPERTY_TYPES = ['ویلا', 'کلنگی', 'زمین']
BUILDER_SELL_PROPERTY_TYPES = ['آپارتمان']

TYPE_PROFILES = {
    'خریدار': {
        'money_mode': 'budget',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'section_hint': 'محدوده قیمت خرید (تومان)',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات جستجو',
        'prefs_hint': 'نوع ملک، متراژ، خواب، سال ساخت، طبقه و امکانات مورد نظر',
    },
    'فروشنده': {
        'money_mode': 'budget',
        'budget_labels': ('قیمت فروش از', 'قیمت فروش تا'),
        'section_hint': 'محدوده قیمت پیشنهادی فروش',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک',
        'prefs_hint': 'ویژگی‌های ملک در حال فروش',
    },
    'فروشنده ملک': {
        'money_mode': 'budget',
        'budget_labels': ('قیمت فروش از', 'قیمت فروش تا'),
        'section_hint': 'قیمت فروش ملک',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک',
        'prefs_hint': 'ویژگی‌های ملک در حال فروش',
    },
    'سازنده': {
        'money_mode': 'builder',
        'budget_labels': ('قیمت واحد از', 'قیمت واحد تا'),
        'section_hint': 'محدوده قیمت آپارتمان‌های فروش',
        'sell_section_title': 'خط فروش — آپارتمان',
        'sell_section_hint': 'نوع ملک فروش معمولاً آپارتمان است؛ محله و متراژ واحدهای در حال ساخت یا فروش را ثبت کنید.',
        'buy_section_title': 'تأمین پروژه — خرید زمین و کلنگی',
        'buy_section_hint': 'بودجه و منطقه خرید ویلا، کلنگی و زمین برای توسعه پروژه',
        'default_property_type': 'آپارتمان',
        'buy_property_types': BUILDER_BUY_PROPERTY_TYPES,
        'prefs_mode': 'builder',
        'prefs_title': 'مشخصات واحد فروش',
        'prefs_hint': 'مشخصات آپارتمان‌های فروش و محله‌های پروژه',
    },
    'مالک': {
        'money_mode': 'both',
        'budget_labels': ('قیمت فروش از', 'قیمت فروش تا'),
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره ماهانه از', 'اجاره ماهانه تا'),
        'section_hint': 'فروش یا رهن و اجاره',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک',
        'prefs_hint': 'ویژگی‌های ملک مالک',
    },
    'مستاجر': {
        'money_mode': 'rent',
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره ماهانه از', 'اجاره ماهانه تا'),
        'section_hint': 'محدوده رهن و اجاره مورد نظر',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات اجاره',
        'prefs_hint': 'نوع ملک، متراژ، خواب و امکانات مورد نظر برای اجاره',
    },
    'موجر': {
        'money_mode': 'rent',
        'deposit_labels': ('ودیعه درخواستی از', 'ودیعه درخواستی تا'),
        'rent_labels': ('اجاره درخواستی از', 'اجاره درخواستی تا'),
        'section_hint': 'ودیعه و اجاره اعلامی موجر',
        'prefs_mode': 'listing',
        'prefs_title': 'مشخصات ملک اجاره‌ای',
        'prefs_hint': 'ویژگی‌های ملک برای اجاره',
    },
    'متقاضی خرید': {
        'money_mode': 'budget',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'section_hint': 'محدوده بودجه خرید',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات جستجو',
        'prefs_hint': 'نوع ملک، متراژ، خواب، سال ساخت، طبقه و امکانات مورد نظر',
    },
    'متقاضی اجاره': {
        'money_mode': 'rent',
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره ماهانه از', 'اجاره ماهانه تا'),
        'section_hint': 'محدوده رهن و اجاره',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات اجاره',
        'prefs_hint': 'نوع ملک، متراژ، خواب و امکانات مورد نظر برای اجاره',
    },
    'سرمایه‌گذار': {
        'money_mode': 'budget',
        'budget_labels': ('سرمایه از', 'سرمایه تا'),
        'section_hint': 'محدوده سرمایه‌گذاری',
        'prefs_mode': 'seeker',
        'prefs_title': 'ترجیحات سرمایه‌گذاری',
        'prefs_hint': 'نوع ملک و محدوده مورد نظر برای سرمایه‌گذاری',
    },
    'سرنخ': {
        'money_mode': 'flexible',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره از', 'اجاره تا'),
        'section_hint': 'اطلاعات مالی اختیاری',
        'prefs_mode': 'flexible',
        'prefs_title': 'ترجیحات ملک',
        'prefs_hint': 'ترجیحات اختیاری برای پیشنهاد هوشمند',
    },
    'اشخاص حقوقی': {
        'money_mode': 'flexible',
        'budget_labels': ('بودجه از', 'بودجه تا'),
        'deposit_labels': ('ودیعه از', 'ودیعه تا'),
        'rent_labels': ('اجاره از', 'اجاره تا'),
        'section_hint': 'اطلاعات مالی شرکت',
        'prefs_mode': 'flexible',
        'prefs_title': 'ترجیحات ملک',
        'prefs_hint': 'ترجیحات اختیاری شرکت',
    },
}

ROLE_COLORS = {
    'مالک': ('#dbeafe', '#1d4ed8'),
    'فروشنده': ('#e0e7ff', '#4338ca'),
    'سازنده': ('#ccfbf1', '#0f766e'),
    'فروشنده ملک': ('#e0e7ff', '#4338ca'),
    'خریدار': ('#dcfce7', '#15803d'),
    'مستاجر': ('#fef3c7', '#b45309'),
    'موجر': ('#ffedd5', '#c2410c'),
    'سرمایه‌گذار': ('#f3e8ff', '#7c3aed'),
    'سرنخ': ('#f1f5f9', '#475569'),
    'متقاضی خرید': ('#ecfdf5', '#047857'),
    'متقاضی اجاره': ('#fff7ed', '#ea580c'),
    'پیشنهادی': ('#e5e7eb', '#374151'),
    'اشخاص حقوقی': ('#fae8ff', '#a21caf'),
}

LEAD_TYPES = {'سرنخ', 'متقاضی خرید', 'متقاضی اجاره'}

CONVERT_TYPE_MAP = {
    'سرنخ': ['خریدار', 'مستاجر', 'مالک', 'موجر', 'سرمایه‌گذار', 'سازنده'],
    'متقاضی خرید': ['خریدار'],
    'متقاضی اجاره': ['مستاجر'],
}

QUICK_LINK_ACTIONS = [
    {'label': 'ثبت مالک', 'role': 'مالک', 'deal_type': 'فروش', 'customer_type': 'مالک'},
    {'label': 'ثبت موجر', 'role': 'موجر', 'deal_type': 'رهن و اجاره', 'customer_type': 'موجر'},
    {'label': 'ثبت مستأجر', 'role': 'مستاجر', 'deal_type': 'اجاره', 'customer_type': 'مستاجر'},
    {'label': 'ثبت خریدار', 'role': 'خریدار', 'deal_type': 'خرید', 'customer_type': 'خریدار'},
    {'label': 'ثبت سرنخ', 'role': 'سرنخ', 'deal_type': 'سایر', 'customer_type': 'سرنخ'},
]

TABLE_COLUMNS_DEFAULT = [
    'شناسه', 'عنوان', 'قیمت', 'ودیعه', 'اجاره', 'متراژ', 'اتاق',
    'محله', 'شهر', 'نوع آگهی دهنده', 'لینک',
]

SUPPORTED_UPLOAD_EXTENSIONS = ('.xlsx', '.xls', '.csv', '.json')

# ── معاملات CRM (فاز ۲) ──
DEAL_STAGES = ['سرنخ', 'مذاکره', 'بازدید', 'پیش‌قرارداد', 'قرارداد', 'بسته‌شده', 'از دست رفته']
DEAL_ACTIVE_STAGES = ['سرنخ', 'مذاکره', 'بازدید', 'پیش‌قرارداد', 'قرارداد']
LOST_REASONS = ['قیمت بالا', 'رقبا', 'انصراف مشتری', 'ملک فروخته شد', 'مدارک ناقص', 'سایر']
DEFAULT_COMMISSION_RATE = 1.0

DEAL_STAGE_WON = 'بسته‌شده'
DEAL_STAGE_LOST = 'از دست رفته'
DEAL_TERMINAL_STAGES = (DEAL_STAGE_WON, DEAL_STAGE_LOST)

# ── آژانس CRM (فاز ۴) ──
AGENCY_ROLES = [
    ('owner', 'مالک'),
    ('manager', 'مدیر'),
    ('advisor', 'مشاور'),
    ('secretary', 'منشی'),
]
AGENCY_ROLE_OWNER = 'owner'
AGENCY_ROLE_MANAGER = 'manager'
AGENCY_ROLE_ADVISOR = 'advisor'
AGENCY_ROLE_SECRETARY = 'secretary'
AGENCY_MANAGER_ROLES = {AGENCY_ROLE_OWNER, AGENCY_ROLE_MANAGER}
AGENCY_FULL_VIEW_ROLES = {AGENCY_ROLE_OWNER, AGENCY_ROLE_MANAGER, AGENCY_ROLE_SECRETARY}
AGENCY_INBOX_ROLES = AGENCY_FULL_VIEW_ROLES

TEAM_VISIBILITY_PRIVATE = 'private'
TEAM_VISIBILITY_INBOX = 'team_inbox'
TEAM_VISIBILITY_ASSIGNED = 'assigned'
TEAM_VISIBILITY_CHOICES = [
    (TEAM_VISIBILITY_PRIVATE, 'خصوصی'),
    (TEAM_VISIBILITY_INBOX, 'صندوق تیم'),
    (TEAM_VISIBILITY_ASSIGNED, 'تخصیص‌یافته'),
]

LEAD_ROUTING_OWNER = 'owner'
LEAD_ROUTING_INBOX = 'inbox'
LEAD_ROUTING_ROUND_ROBIN = 'round_robin'
LEAD_ROUTING_CHOICES = [
    (LEAD_ROUTING_OWNER, 'مالک آژانس'),
    (LEAD_ROUTING_INBOX, 'صندوق سرنخ تیم'),
    (LEAD_ROUTING_ROUND_ROBIN, 'چرخشی بین مشاوران'),
]

AUDIT_EVENTS = [
    'agency.updated', 'api_key.regenerated', 'member.invited', 'member.role_changed',
    'member.removed', 'lead.assigned', 'lead.bulk_assigned', 'customer.transferred',
    'sync.export', 'sync.import', 'webhook.created', 'webhook.deleted', 'webhook.tested',
    'message.sent', 'message.broadcast', 'message.deleted', 'announcement.created',
    'announcement.updated', 'announcement.deleted', 'knowledge.created', 'knowledge.updated',
]

# ── مرکز فرماندهی آژانس — Feature Flags ماژولار ──
AGENCY_COMMAND_CENTER_FEATURES = {
    'messages': True,
    'announcements': True,
    'activity_feed': True,
    'kpi_leaderboard': True,
    'knowledge_base': True,
    'team_calendar': True,
    'heatmap': True,
    'tv_mode': True,
}

MESSAGE_RETENTION_DAYS = 30
MESSAGE_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MESSAGE_ALLOWED_EXTENSIONS = frozenset({
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.webp',
})

WEBHOOK_EVENTS = [
    'customer.created',
    'customer.assigned',
    'deal.created',
    'deal.closed',
    'deal.lost',
]

WEBHOOK_EVENT_LABELS = {
    'customer.created': 'ثبت مخاطب جدید',
    'customer.assigned': 'تخصیص به مشاور',
    'deal.created': 'معامله جدید',
    'deal.closed': 'بستن معامله',
    'deal.lost': 'از دست رفتن معامله',
}

AGENCY_ROLE_STYLES = {
    'owner': ('#f3e8ff', '#7c3aed'),
    'manager': ('#dbeafe', '#1d4ed8'),
    'advisor': ('#dcfce7', '#15803d'),
    'secretary': ('#fef3c7', '#b45309'),
}

DEAL_STAGE_COLORS = {
    'سرنخ': ('#f1f5f9', '#475569'),
    'مذاکره': ('#dbeafe', '#1d4ed8'),
    'بازدید': ('#fef3c7', '#b45309'),
    'پیش‌قرارداد': ('#e0e7ff', '#4338ca'),
    'قرارداد': ('#fce7f3', '#be185d'),
    'بسته‌شده': ('#dcfce7', '#15803d'),
    'از دست رفته': ('#fee2e2', '#b91c1c'),
}

DEFAULT_DEAL_CHECKLIST = [
    {'id': 'deed', 'label': 'سند ملک', 'required': True},
    {'id': 'inquiry', 'label': 'استعلام', 'required': True},
    {'id': 'owner_id', 'label': 'مدارک هویتی مالک', 'required': True},
    {'id': 'buyer_id', 'label': 'مدارک هویتی خریدار', 'required': False},
    {'id': 'deposit', 'label': 'پیش‌پرداخت / بیعانه', 'required': False},
    {'id': 'draft', 'label': 'پیش‌نویس قرارداد', 'required': True},
]

VISIT_OUTCOMES = ['پسندید', 'رد', 'در انتظار', 'بازدید مجدد']
VISIT_REJECT_REASONS = ['قیمت', 'موقعیت', 'متراژ', 'نور و تهویه', 'طبقه', 'سایر']

IMPORT_CONTACT_COLUMNS = {
    'نام': 'name',
    'تلفن': 'phone',
    'تلفن دوم': 'phone_alt',
    'ایمیل': 'email',
    'نوع': 'customer_type',
    'وضعیت': 'status',
    'اولویت': 'priority',
    'منبع': 'source',
    'شهر': 'city',
    'منطقه': 'district',
    'یادداشت': 'notes',
    'برچسب‌ها': 'tags',
}

IMPORT_PROPERTY_COLUMNS = {
    'عنوان': 'title',
    'نوع ملک': 'property_type',
    'نوع معامله': 'deal_mode',
    'وضعیت معامله': 'transaction_status',
    'وضعیت انتشار': 'publish_status',
    'نوع آگهی دهنده': 'business_type',
    'شماره تماس': 'phone',
    'شهر': 'city',
    'منطقه': 'district',
    'محله': 'neighborhood',
    'آدرس': 'address',
    'متراژ (متر)': 'area',
    'اتاق': 'rooms',
    'طبقه': 'floor',
    'تعداد طبقات': 'total_floors',
    'سال ساخت': 'build_year',
    'پارکینگ': 'has_parking',
    'انباری': 'has_storage',
    'آسانسور': 'has_elevator',
    'قیمت فروش (تومان)': 'sale_price',
    'رهن (تومان)': 'deposit',
    'اجاره ماهانه (تومان)': 'monthly_rent',
    'امکانات': 'amenities',
    'شناسه آگهی': 'token',
    'لینک': 'link',
    'عرض جغرافیایی': 'latitude',
    'طول جغرافیایی': 'longitude',
    'یادداشت': 'notes',
}

IMPORT_PROPERTY_HEADER_ALIASES = {
    'نوع آگهی‌دهنده': 'business_type',
    'business_type': 'business_type',
    'تلفن': 'phone',
    'موبایل': 'phone',
    'تماس': 'phone',
}

# ── اتوماسیون CRM (فاز ۳) ──
MESSAGE_TEMPLATE_CATEGORIES = ['پیگیری', 'بازدید', 'پیشنهاد', 'خوش‌آمد', 'سفارشی']
MESSAGE_CHANNELS = ['واتساپ', 'پیامک']
MESSAGE_PLACEHOLDERS = ['{name}', '{phone}', '{type}', '{status}', '{areas}', '{agency}']

AUTOMATION_TRIGGERS = [('inactive_days', 'بدون فعالیت (روز)')]
AUTOMATION_ACTIONS = [
    ('set_status', 'تغییر وضعیت'),
    ('create_reminder', 'ایجاد یادآور'),
]

REMINDER_RECURRENCE = [
    ('', 'یک‌بار'),
    ('weekly', 'هفتگی'),
    ('biweekly', 'دو هفته‌ای'),
    ('monthly', 'ماهانه'),
]

FUNNEL_STAGES = ['سرنخ', 'پیگیری', 'بازدید', 'قرارداد']
DEFAULT_STAGNANT_DAYS = 7
