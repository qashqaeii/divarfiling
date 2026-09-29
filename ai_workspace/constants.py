"""ثابت‌ها و Feature Flag — فاز صفر AI."""
from __future__ import annotations

from django.conf import settings

from workspace.services.access import has_active_bot_license

FEATURE_LISTING_SUMMARY = 'listing_summary'
FEATURE_CRM_MESSAGE = 'crm_message'
FEATURE_UPLOAD_BRIEF = 'upload_brief'
FEATURE_NL_COMMAND = 'nl_command'
FEATURE_MANAGEMENT_ANALYSIS = 'management_analysis'

AI_FEATURES = {
    FEATURE_LISTING_SUMMARY: True,
    FEATURE_CRM_MESSAGE: True,
    # غیرفعال محصولی — endpoint فقط پاسخ کنترل‌شده می‌دهد؛ LLM صدا زده نمی‌شود.
    FEATURE_UPLOAD_BRIEF: False,
    FEATURE_NL_COMMAND: True,
    FEATURE_MANAGEMENT_ANALYSIS: True,
}

FEATURE_DAILY_LIMITS = {
    FEATURE_LISTING_SUMMARY: 30,
    FEATURE_CRM_MESSAGE: 24,
    FEATURE_NL_COMMAND: 30,
    FEATURE_MANAGEMENT_ANALYSIS: 200,
}

FEATURE_GENERATION = {
    FEATURE_NL_COMMAND: {
        'temperature': 0.1,
        'max_tokens': 700,
    },
    FEATURE_MANAGEMENT_ANALYSIS: {
        'temperature': 0.1,
        'max_tokens': 2200,
    },
}

DEFAULT_DAILY_LIMIT = 30

FEATURE_LABELS = {
    FEATURE_LISTING_SUMMARY: 'خلاصه آگهی',
    FEATURE_CRM_MESSAGE: 'پیام CRM',
    FEATURE_UPLOAD_BRIEF: 'تحلیل آپلود',
    FEATURE_NL_COMMAND: 'فرمان هوشمند',
    FEATURE_MANAGEMENT_ANALYSIS: 'تحلیل مدیریت',
}

DEFAULT_CRM_TONE = 'رسمی'

CRM_MESSAGE_TONES = {
    'رسمی': {
        'label': 'رسمی و حرفه‌ای',
        'guide': 'محترمانه، منظم و مناسب مشاور املاک؛ جملات کوتاه و شفاف.',
        'emoji': False,
    },
    'صمیمی': {
        'label': 'صمیمی و گرم',
        'guide': 'دوستانه ولی حرفه‌ای؛ از «شما» استفاده کنید و لحن گفت‌وگویی داشته باشید.',
        'emoji': False,
    },
    'کوتاه': {
        'label': 'کوتاه و مستقیم',
        'guide': 'حداکثر ۵ خط؛ مستقیم به معرفی ملک‌ها و دعوت به اقدام برسید؛ بدون مقدمه طولانی.',
        'emoji': False,
    },
    'مشاورانه': {
        'label': 'مشاورانه',
        'guide': 'لحن راهنما و مشاور؛ دلیل پیشنهاد هر ملک را در یک عبارت کوتاه بگویید.',
        'emoji': False,
    },
    'پیگیری': {
        'label': 'پیگیری ملایم',
        'guide': 'ملایم و پیگیر؛ مناسب پیام پیگیری بدون فشار؛ تأکید بر آمادگی برای همکاری.',
        'emoji': False,
    },
}

CRM_MESSAGE_TONE_CHOICES = tuple(
    (key, meta['label']) for key, meta in CRM_MESSAGE_TONES.items()
)

DEFAULT_LISTING_SUMMARY_TONE = 'مشاورانه'
DEFAULT_LISTING_SUMMARY_STYLE = 'کارتی'

LISTING_SUMMARY_TONES = {
    'رسمی': {
        'label': 'رسمی',
        'hint': 'محترمانه و حرفه‌ای',
        'icon': 'fa-user-tie',
        'guide': 'لحن رسمی و شفاف؛ مناسب ارائه به مشتری جدی و مکاتبات رسمی؛ از عامیانه پرهیز کنید.',
    },
    'صمیمی': {
        'label': 'صمیمی',
        'hint': 'گرم و قابل‌فهم',
        'icon': 'fa-face-smile',
        'guide': 'لحن دوستانه اما حرفه‌ای؛ از «شما» استفاده کنید؛ جملات روان و نزدیک به گفت‌وگو.',
    },
    'مشاورانه': {
        'label': 'مشاورانه',
        'hint': 'راهنما و تحلیلی',
        'icon': 'fa-compass',
        'guide': 'لحن مشاور املاک؛ توضیح «چرا این فایل مهم است»؛ متعادل بین تحلیل و پیشنهاد عمل.',
    },
    'کوتاه': {
        'label': 'کوتاه',
        'hint': 'مستقیم و فشرده',
        'icon': 'fa-bolt',
        'guide': 'حداقل کلمات؛ بدون مقدمه؛ هر جمله یک اطلاعات مشخص؛ مناسب اسکن سریع.',
    },
}

LISTING_SUMMARY_STYLES = {
    'کارتی': {
        'label': 'کارت‌وار',
        'hint': 'خلاصه + نکات',
        'icon': 'fa-layer-group',
        'guide': 'summary ۲–۳ جمله؛ highlights ۴–۶ مورد کوتاه و اسکن‌پذیر؛ negotiation_tip یک جمله عملی.',
    },
    'واتساپ': {
        'label': 'واتساپ',
        'hint': 'آماده ارسال',
        'icon': 'fa-comment-dots',
        'guide': 'متن طوری بنویس که مشاور بتواند با کمترین ویرایش در واتساپ بفرستد؛ summary حداکثر ۲ جمله؛ highlights حداکثر ۴ مورد خیلی کوتاه.',
    },
    'ارائه': {
        'label': 'ارائه',
        'hint': 'معرفی به مشتری',
        'icon': 'fa-chalkboard-user',
        'guide': 'مناسب معرفی اولیه ملک؛ تاکید بر مزیت رقابتی و موقعیت؛ highlights با عبارت کامل و مثبتِ واقع‌بینانه.',
    },
    'یادداشت داخلی': {
        'label': 'یادداشت',
        'hint': 'فقط برای شما',
        'icon': 'fa-note-sticky',
        'guide': 'مستقیم و کاربردی؛ تاکید بر ریسک، نقطه ضعف احتمالی و اقدام بعدی؛ negotiation_tip بسیار عملی.',
    },
    'تحلیلی': {
        'label': 'تحلیلی',
        'hint': 'تمرکز بازار',
        'icon': 'fa-chart-line',
        'guide': 'اگر benchmark در CONTEXT هست در summary و highlights پررنگ کن؛ مقایسه با میانه بازار؛ بدون عدد جدید.',
    },
}

LISTING_SUMMARY_TONE_CHOICES = tuple(
    {'key': key, **meta} for key, meta in LISTING_SUMMARY_TONES.items()
)
LISTING_SUMMARY_STYLE_CHOICES = tuple(
    {'key': key, **meta} for key, meta in LISTING_SUMMARY_STYLES.items()
)

JSON_FEATURES = frozenset({
    FEATURE_LISTING_SUMMARY,
    FEATURE_NL_COMMAND,
    FEATURE_MANAGEMENT_ANALYSIS,
})

# نسخه دستی prompt — فقط وقتی محتوا عوض شد افزایش دهید (نه mtime)
PROMPT_VERSIONS = {
    FEATURE_LISTING_SUMMARY: 'listing_summary_v7',
    FEATURE_CRM_MESSAGE: 'crm_message_v5',
    FEATURE_UPLOAD_BRIEF: 'upload_brief_v1',
    FEATURE_NL_COMMAND: 'nl_command_v3',
    # max 20 chars — AIUsageLog.prompt_version
    FEATURE_MANAGEMENT_ANALYSIS: 'mgmt_analysis_v1',
}

NL_COMMAND_INTENT_CREATE_REMINDER = 'create_reminder'
NL_COMMAND_INTENT_CREATE_CONTACT = 'create_contact'
NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY = 'create_personal_property'
NL_COMMAND_INTENT_UNKNOWN = 'unknown'
NL_COMMAND_ALLOWED_INTENTS = frozenset({
    NL_COMMAND_INTENT_CREATE_REMINDER,
    NL_COMMAND_INTENT_CREATE_CONTACT,
    NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY,
    NL_COMMAND_INTENT_UNKNOWN,
})

NL_COMMAND_UNKNOWN_MESSAGE = (
    'فعلاً فرمان هوشمند برای ثبت یادآوری، مخاطب و فایل شخصی فعال است.'
)

NL_COMMAND_PARSE_FAILED_MESSAGE = (
    'فرمان قابل تشخیص نبود. دوباره ساده‌تر بنویسید.'
)

NL_COMMAND_PROVIDER_UNAVAILABLE_MESSAGE = (
    'سرویس هوشمند موقتاً در دسترس نیست. دوباره تلاش کنید.'
)

NL_COMMAND_EXAMPLE_PHRASES = (
    'فردا ساعت ۱۰ یادم بنداز به احمدی زنگ بزنم',
    'خانم احمدی رو با شماره ۰۹۱۲۱۲۳۴۵۶۷ ذخیره کن',
    'یه آپارتمان ۱۲۰ متری پونک برای فروش، ۱۲ میلیارد',
)

MAX_NL_COMMAND_CHARS = 1500

NL_COMMAND_INPUT_TOO_LONG_MESSAGE = (
    'فرمان خیلی طولانی است. لطفاً کوتاه‌تر بگویید یا بنویسید.'
)


def nl_command_contact_not_found_message(contact_name: str) -> str:
    name = (contact_name or '').strip() or 'موردنظر'
    return f'مخاطبی با نام {name} پیدا نشد.'


def is_ai_enabled() -> bool:
    return bool(getattr(settings, 'AI_ENABLED', False))


def is_feature_enabled(feature: str, user) -> bool:
    if feature == FEATURE_MANAGEMENT_ANALYSIS:
        if not getattr(settings, 'ADMIN_MANAGEMENT_AI_ENABLED', False):
            return False
        if not is_ai_enabled():
            return False
        if not user or not user.is_authenticated:
            return False
        return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))
    if not is_ai_enabled():
        return False
    if feature not in AI_FEATURES or not AI_FEATURES[feature]:
        return False
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    return has_active_bot_license(user)


def feature_uses_json(feature: str) -> bool:
    return feature in JSON_FEATURES


def normalize_crm_tone(tone: str | None) -> str:
    key = (tone or '').strip()
    # لحن قدیمی ایموجی — به صمیمی نگاشت می‌شود
    if key in {'ایموجی‌دار', 'ایموجیدار', 'ایموجی دار'}:
        return 'صمیمی'
    if key in CRM_MESSAGE_TONES:
        return key
    return DEFAULT_CRM_TONE


def crm_tone_meta(tone: str | None) -> dict:
    return CRM_MESSAGE_TONES[normalize_crm_tone(tone)]


def normalize_listing_summary_tone(tone: str | None) -> str:
    key = (tone or '').strip()
    if key in LISTING_SUMMARY_TONES:
        return key
    return DEFAULT_LISTING_SUMMARY_TONE


def normalize_listing_summary_style(style: str | None) -> str:
    key = (style or '').strip()
    if key in LISTING_SUMMARY_STYLES:
        return key
    return DEFAULT_LISTING_SUMMARY_STYLE


def listing_summary_tone_meta(tone: str | None) -> dict:
    key = normalize_listing_summary_tone(tone)
    meta = LISTING_SUMMARY_TONES[key]
    return {'key': key, **meta}


def listing_summary_style_meta(style: str | None) -> dict:
    key = normalize_listing_summary_style(style)
    meta = LISTING_SUMMARY_STYLES[key]
    return {'key': key, **meta}


INTERNAL_MODEL_LABEL = 'مدل داخلی سیستم'


def resolve_model_label(
    *,
    provider: str = '',
    model: str = '',
    is_fallback: bool = False,
    source: str = 'ai',
) -> str:
    """برچسب نمایشی مدل تولید متن — fallback سیستمی: «مدل داخلی سیستم»."""
    provider = (provider or '').strip()
    model = (model or '').strip()
    source = (source or 'ai').strip()

    if source == 'fallback' or provider == 'rule_based':
        return INTERNAL_MODEL_LABEL
    if is_fallback and not model:
        return INTERNAL_MODEL_LABEL
    if model:
        return model
    if provider == 'openrouter':
        return 'مدل پشتیبان'
    if provider == 'arvan':
        return model or 'Arvan AI'
    if provider == 'gemini':
        return 'Gemini'
    if is_fallback:
        return INTERNAL_MODEL_LABEL
    return ''
