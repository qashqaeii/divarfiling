"""ثابت‌های استودیو محتوای ملک."""
from __future__ import annotations

# محدودیت عنوان آگهی دیوار — از راهنمای انتشار عمومی (حداکثر کاراکتر عنوان)
DIVAR_AD_TITLE_MAX_CHARS = 50
DIVAR_AD_DESCRIPTION_MAX_CHARS = 2000

POSTER_TEMPLATES = (
    {'id': 'luxury', 'label': 'لوکس', 'description': 'تصویر برجسته با گرادینت و تایپوگرافی شیک'},
    {'id': 'minimal', 'label': 'مینیمال', 'description': 'پس‌زمینه روشن و چیدمان متعادل'},
    {'id': 'gallery', 'label': 'چندتصویری', 'description': 'کلاژ از تصاویر واقعی ملک'},
    {'id': 'bold', 'label': 'تبلیغاتی', 'description': 'عنوان و قیمت برجسته برای شبکه‌های اجتماعی'},
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
    'file_code': True,
}

DEFAULT_BRAND_COLORS = {
    'primary': '#7c3aed',
    'text_on_primary': '#ffffff',
    'accent': '#5b21b6',
}

DRAFT_VERSION = 1
