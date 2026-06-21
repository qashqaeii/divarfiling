"""اطلاعات برند، سایت و سازنده — منبع واحد برای قالب‌ها و SEO."""

SITE_DISPLAY_NAME = 'فایلینگ دیوار'
SITE_URL = 'https://divarfiling.ir'
SITE_URL_DISPLAY = 'divarfiling.ir'

CREATOR_NAME = 'حسین قشقایی'
CREATOR_PHONE = '09357930033'
CREATOR_PHONE_DISPLAY = '۰۹۳۵۷۹۳۰۰۳۳'
CREATOR_PHONE_TEL = '+989357930033'

CREATOR_TELEGRAM = '@hosseinQashqaeii'
CREATOR_TELEGRAM_URL = 'https://t.me/hosseinQashqaeii'

SUPPORT_EMAIL = 'info@divarfiling.ir'


def site_brand_context() -> dict:
    """دیکشنری برای context processor و قالب‌ها."""
    return {
        'site_display_name': SITE_DISPLAY_NAME,
        'site_url': SITE_URL,
        'site_url_display': SITE_URL_DISPLAY,
        'creator_name': CREATOR_NAME,
        'creator_phone': CREATOR_PHONE,
        'creator_phone_display': CREATOR_PHONE_DISPLAY,
        'creator_phone_tel': CREATOR_PHONE_TEL,
        'creator_telegram': CREATOR_TELEGRAM,
        'creator_telegram_url': CREATOR_TELEGRAM_URL,
        'support_email': SUPPORT_EMAIL,
    }
