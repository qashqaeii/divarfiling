"""ثابت‌های استودیو محتوای ملک."""
from __future__ import annotations

# محدودیت عنوان آگهی دیوار — از راهنمای انتشار عمومی (حداکثر کاراکتر عنوان)
DIVAR_AD_TITLE_MAX_CHARS = 50
DIVAR_AD_DESCRIPTION_MAX_CHARS = 2000
# عنوان روی پوستر/استوری — کوتاه برای خوانایی روی تصویر
POSTER_AD_HEADLINE_MAX_CHARS = 44

# کلیدهای سبک متن آگهی دیوار (هم‌نام value در UI استودیو)
DIVAR_BODY_STYLE_GUIDES: dict[str, dict[str, str]] = {
    'formal': {
        'label': 'رسمی حرفه‌ای',
        'guide': (
            'لحن مشاور املاک رسمی؛ جملات منظم و قابل اعتماد؛ '
            'همه مشخصات موجود در divar_facts_outline را با ایموجی خط‌اول بپوشانید؛ '
            '۱ پاراگراف کوتاه جمع‌بندی در پایان.'
        ),
    },
    'promo': {
        'label': 'تبلیغاتی جذاب',
        'guide': (
            'لحن پرانرژی ولی واقع‌بین؛ بر نقاط قوت ثبت‌شده در context تأکید کنید؛ '
            'همان مشخصات را با ایموجی حرفه‌ای بیاورید؛ از اغراق و وعده کاذب پرهیز کنید.'
        ),
    },
    'short': {
        'label': 'مختصر و سریع',
        'guide': (
            'حداکثر ۸–۱۰ خط؛ فقط مهم‌ترین موارد: قیمت، موقعیت، متراژ، اتاق، طبقه، ۲–۳ امکان کلیدی؛ '
            'ایموجی در ابتدای هر خط؛ بدون پاراگراف طولانی.'
        ),
    },
    'full': {
        'label': 'کامل با همه مشخصات',
        'guide': (
            'کامل‌ترین خروجی: هر مورد divar_facts_outline + detail_chips + amenities موجود در context '
            'باید در متن بیاید (هر کدام یک خط با ایموجی مناسب)؛ '
            'سپس ۲–۳ جمله توضیح از description_excerpt یا studio facts (بازنویسی، نه کپی خام CRM).'
        ),
    },
    'consultant': {
        'label': 'مشاورانه',
        'guide': (
            'لحن راهنما: «مناسب برای…» فقط بر اساس facts؛ '
            'مشخصات فنی با ایموجی؛ یک جمله دلیل بازدید؛ CTA مودب.'
        ),
    },
    'luxury': {
        'label': 'لوکس و اعتمادساز',
        'guide': (
            'لحن فایلینگ لوکس؛ واژگان باکیفیت بدون اغراق؛ '
            'همه مشخصات ثبت‌شده؛ ایموجی محدود و شیک (✅ 📍 📐 🏠 💰).'
        ),
    },
    'friendly': {
        'label': 'صمیمی حرفه‌ای',
        'guide': (
            'گرم و قابل‌فهم با «شما»؛ همچنان حرفه‌ای؛ '
            'مشخصات کامل با ایموجی؛ جملات کوتاه؛ بدون slang.'
        ),
    },
}

POSTER_TEMPLATES = (
    {'id': 'luxury', 'label': 'لوکس', 'description': 'تصویر برجسته با گرادینت و تایپوگرافی شیک'},
    {'id': 'minimal', 'label': 'مینیمال', 'description': 'پس‌زمینه روشن و چیدمان متعادل'},
    {'id': 'gallery', 'label': 'چندتصویری', 'description': 'کلاژ از تصاویر واقعی ملک'},
    {'id': 'bold', 'label': 'تبلیغاتی', 'description': 'عنوان و قیمت برجسته برای شبکه‌های اجتماعی'},
    {
        'id': 'pearlescent',
        'label': 'قاب استوری',
        'description': 'قاب PNG با جایگاه شفاف برای تصویر — مناسب استوری',
        'overlay': 'images/Pearlescent Blue Real Estate Story Template-3.webp',
    },
    {
        'id': 'pearlescent_ribbon',
        'label': 'ریبون مروارید',
        'description': 'استوری لوکس با ریبون مروارید و پنل زمردی — مناسب فایل تک‌تصویر',
        'overlay': 'images/Pearlescent ribbon luxury real estate template-4.png',
    },
    {
        'id': 'sculptural',
        'label': 'قاب عاج',
        'description': 'قاب استوری عاج و زیتونی — مناسب فایل‌های با چند تصویر',
        'overlay': 'images/Sculptural ivory olive real estate story template-4.webp',
    },
    {
        'id': 'sculpted_travertine',
        'label': 'تراورتن طلایی',
        'description': 'قاب سنگ تراورتن با قوس طلایی — استوری لوکس تک‌تصویر',
        'overlay': 'images/Sculpted travertine luxury story template.png',
    },
    {
        'id': 'emerald_atelier',
        'label': 'قاب زمرد',
        'description': 'قاب معماری زمرد — حداقل دو تصویر (قوس و نوار)',
        'overlay': 'images/Emerald Atelier architectural story template-3.webp',
    },
    {
        'id': 'pearl_gallery',
        'label': 'گالری مروارید',
        'description': 'قاب لوکس مروارید — دو دایره (شاخص + مکمل)',
        'overlay': 'images/Pearl Gallery luxury property story-2.webp',
    },
)

OUTPUT_FORMATS = {
    'story': {'label': 'استوری', 'width': 1080, 'height': 1920, 'aspect': '9/16'},
    'post': {'label': 'پست', 'width': 1080, 'height': 1350, 'aspect': '4/5'},
    'square': {'label': 'واتساپ/تلگرام', 'width': 1080, 'height': 1080, 'aspect': '1/1'},
}

DEFAULT_VISIBILITY = {
    'price': True,
    'neighborhood': True,
    'area': True,
    'bedrooms': True,
    'floor': True,
    'amenities': True,
    'consultant_name': True,
    'contact_phone': True,
    'file_code': False,
}

DEFAULT_BRAND_COLORS = {
    'primary': '#7c3aed',
    'text_on_primary': '#ffffff',
    'accent': '#5b21b6',
}

DRAFT_VERSION = 1

# هویت پیش‌فرض هر اسلاید استوری‌برد (قالب + نام نمایشی + تنظیمات پوستر)
STORY_SLIDE_IDENTITIES: dict[str, dict] = {
    'cover': {
        'template_id': 'luxury',
        'label': 'لوکس',
        'poster': {
            'font_key': 'gulzar',
            'headline_scale': 140,
            'price_scale': 140,
            'img_brightness': 115,
            'img_blur': 0,
            'img_opacity': 100,
        },
    },
    'specs': {
        'template_id': 'minimal',
        'label': 'مینیمال',
        'poster': {
            'font_key': 'vazirmatn',
            'headline_scale': 100,
            'price_scale': 100,
            'img_brightness': 100,
            'img_blur': 0,
            'img_opacity': 100,
        },
    },
    'gallery_price': {
        'template_id': 'gallery',
        'label': 'گالری',
        'poster': {
            'font_key': 'vazirmatn',
            'headline_scale': 100,
            'price_scale': 110,
            'img_brightness': 105,
            'img_blur': 0,
            'img_opacity': 100,
        },
    },
    'extra_photos': {
        'template_id': 'sculptural',
        'label': 'عاج',
        'poster': {
            'font_key': 'vazirmatn',
            'headline_scale': 105,
            'price_scale': 105,
            'img_brightness': 108,
            'img_blur': 0,
            'img_opacity': 100,
        },
    },
    'emerald_showcase': {
        'template_id': 'emerald_atelier',
        'label': 'زمرد',
        'poster': {
            'font_key': 'vazirmatn',
            'headline_scale': 102,
            'price_scale': 108,
            'img_brightness': 106,
            'img_blur': 0,
            'img_opacity': 100,
        },
    },
    'pearl_showcase': {
        'template_id': 'pearl_gallery',
        'label': 'مروارید',
        'poster': {
            'font_key': 'gulzar',
            'headline_scale': 108,
            'price_scale': 112,
            'img_brightness': 108,
            'img_blur': 0,
            'img_opacity': 100,
        },
    },
    'contact': {
        'template_id': 'bold',
        'label': 'دعوت',
        'poster': {
            'font_key': 'estedad',
            'headline_scale': 115,
            'price_scale': 100,
            'img_brightness': 100,
            'img_blur': 0,
            'img_opacity': 100,
        },
    },
}
