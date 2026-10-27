"""اطلاعات برند، سایت و سازنده — منبع واحد برای قالب‌ها و SEO."""

SITE_DISPLAY_NAME = 'فایلینگ دیوار'
SITE_URL = 'https://divarfiling.ir'
SITE_URL_DISPLAY = 'divarfiling.ir'

CREATOR_NAME = 'حسین قشقایی'
CREATOR_PHONE = '09357930033'
CREATOR_PHONE_DISPLAY = 'تماس مستقیم با مدیر'
CREATOR_PHONE_TEL = '+989357930033'

CREATOR_TELEGRAM = '@hosseinQashqaeii'
CREATOR_TELEGRAM_URL = 'https://t.me/hosseinQashqaeii'

SUPPORT_EMAIL = 'info@divarfiling.ir'

# شبکه‌های اجتماعی رسمی برند فایلینگ دیوار (فوتر، تماس، SEO)
COMPANY_SOCIAL_LINKS: tuple[dict, ...] = (
    {
        'key': 'telegram',
        'label': 'تلگرام فایلینگ دیوار',
        'href': 'https://t.me/divarfiling',
        'icon': 'fab fa-telegram',
        'icon_file': 'icons/telegram.png',
    },
    {
        'key': 'instagram',
        'label': 'اینستاگرام فایلینگ دیوار',
        'href': 'https://www.instagram.com/divarfiling/',
        'icon': 'fab fa-instagram',
        'icon_file': 'icons/Instagram.png',
    },
    {
        'key': 'youtube',
        'label': 'یوتیوب فایلینگ دیوار',
        'href': 'https://www.youtube.com/@DivarFiling',
        'icon': 'fab fa-youtube',
        'icon_file': 'icons/youtube.png',
    },
    {
        'key': 'aparat',
        'label': 'آپارات فایلینگ دیوار',
        'href': 'https://www.aparat.com/DivarFiling',
        'icon': 'fas fa-play-circle',
        'icon_file': 'icons/aparat.png',
    },
)


def company_social_links() -> list:
    return list(COMPANY_SOCIAL_LINKS)


def company_social_urls() -> list:
    return [item['href'] for item in COMPANY_SOCIAL_LINKS]


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
        'company_social_links': company_social_links(),
        'company_social_urls': company_social_urls(),
    }
