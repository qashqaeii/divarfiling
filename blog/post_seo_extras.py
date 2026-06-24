"""متادیتای سئو مقاله — pillar، مقالات مرتبط، CTA."""
from __future__ import annotations

PHASE_A_EXTRAS: dict[str, dict] = {
    'crm-amlak-raygan-rahnama': {
        'pillar_url_name': 'seo_landing_real_estate_crm',
        'pillar_title': 'CRM مشاور املاک',
        'pillar_desc': 'راهنمای کامل CRM رایگان میزکار',
        'related_slugs': [
            'crm-amlak-online-vs-excel',
            'peigiri-moshtari-moshaver-amlak',
            'narm-afzar-crm-amlak-rahnama-kamel',
        ],
    },
    'peigiri-moshtari-moshaver-amlak': {
        'pillar_url_name': 'seo_landing_real_estate_crm',
        'pillar_title': 'CRM مشاور املاک',
        'pillar_desc': 'قیف معامله و پیگیری روزانه',
        'related_slugs': [
            'crm-amlak-raygan-rahnama',
            'crm-amlak-online-vs-excel',
            'narm-afzar-crm-amlak-rahnama-kamel',
        ],
    },
    'crm-amlak-online-vs-excel': {
        'pillar_url_name': 'seo_landing_real_estate_crm',
        'pillar_title': 'CRM مشاور املاک',
        'pillar_desc': 'جایگزین حرفه‌ای اکسل',
        'related_slugs': [
            'crm-amlak-raygan-rahnama',
            'peigiri-moshtari-moshaver-amlak',
            'narm-afzar-crm-amlak-rahnama-kamel',
        ],
    },
    'chetor-agahi-divar-download': {
        'pillar_url_name': 'seo_landing_robot_divar',
        'pillar_title': 'ربات دیوار',
        'pillar_desc': 'استخراج خودکار آگهی املاک',
        'related_slugs': [
            'moghayese-dasti-vs-robot-divar',
        ],
    },
    'moghayese-dasti-vs-robot-divar': {
        'pillar_url_name': 'seo_landing_robot_divar',
        'pillar_title': 'ربات دیوار',
        'pillar_desc': 'مقایسه و خرید ربات استخراج',
        'related_slugs': [
            'chetor-agahi-divar-download',
        ],
    },
    'narm-afzar-crm-amlak-rahnama-kamel': {
        'pillar_url_name': 'seo_landing_real_estate_crm',
        'pillar_title': 'CRM مشاور املاک',
        'pillar_desc': 'راهنمای انتخاب نرم‌افزار',
        'related_slugs': [
            'crm-amlak-raygan-rahnama',
            'crm-amlak-online-vs-excel',
            'peigiri-moshtari-moshaver-amlak',
        ],
    },
}


def get_post_seo_extras(slug: str) -> dict:
    return PHASE_A_EXTRAS.get(slug, {})
