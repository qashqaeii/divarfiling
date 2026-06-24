"""محتوای صفحه نویسنده — E-E-A-T."""
from __future__ import annotations

AUTHOR_SLUG = 'hossein-qashqaeii'


def author_page_content() -> dict:
    return {
        'slug': AUTHOR_SLUG,
        'name': 'Hossein Qashqaeii',
        'name_fa': 'حسین قشقایی',
        'role': 'سازنده فایلینگ دیوار',
        'tagline': 'متخصص طراحی ربات‌های استخراج داده، اتوماسیون املاک و سیستم‌های SaaS فارسی',
        'bio': (
            'حسین قشقایی توسعه‌دهنده و معمار محصول فایلینگ دیوار است — پلتفرمی که '
            'ربات استخراج آگهی دیوار، میزکار CRM املاک و تحلیل بازار را برای مشاوران '
            'و آژانس‌های ایرانی یکپارچه کرده است. تمرکز او روی تبدیل داده خام دیوار '
            'به ابزار تصمیم‌گیری حرفه‌ای برای بازار املاک است.'
        ),
        'expertise': [
            'Python',
            'Web Scraping',
            'Django',
            'Data Analytics',
            'Real Estate Data Automation',
        ],
        'expertise_fa': [
            'پایتون و توسعه بک‌اند',
            'وب‌اسکرپینگ و استخراج داده',
            'فریم‌ورک Django',
            'تحلیل داده و اتوماسیون',
            'داده‌کاوی املاک و دیوار',
        ],
        'highlights': [
            {
                'icon': 'fa-robot',
                'accent': 'indigo',
                'title': 'ربات استخراج دیوار',
                'text': 'طراحی ربات ویندوز برای جمع‌آوری خودکار آگهی املاک',
            },
            {
                'icon': 'fa-users',
                'accent': 'violet',
                'title': 'CRM املاک',
                'text': 'میزکار CRM رایگان برای مشاوران و آژانس‌ها',
            },
            {
                'icon': 'fa-chart-line',
                'accent': 'amber',
                'title': 'تحلیل بازار',
                'text': 'تحلیل قیمت و روند محله بر اساس داده واقعی آگهی',
            },
        ],
        'visuals': {
            'hero_shots': [
                {
                    'image': 'images/help-workspace-home.png',
                    'caption': 'میزکار یکپارچه فایلینگ دیوار',
                    'accent': 'emerald',
                },
                {
                    'image': 'images/help-crm-dashboard.png',
                    'caption': 'CRM املاک — داشبورد مشاور',
                    'accent': 'violet',
                },
                {
                    'image': 'images/help-bot-extract-tab.png',
                    'caption': 'ربات استخراج آگهی دیوار',
                    'accent': 'indigo',
                },
            ],
        },
        'stats_labels': {
            'articles': 'مقاله تخصصی',
            'landings': 'راهنمای محصول',
            'product': 'محصول نرم‌افزاری',
        },
        'meta_title': 'حسین قشقایی | سازنده فایلینگ دیوار — توسعه‌دهنده CRM املاک',
        'meta_description': (
            'حسین قشقایی (Hossein Qashqaeii)، سازنده فایلینگ دیوار: متخصص Python، '
            'وب‌اسکرپینگ، Django و اتوماسیون داده املاک برای مشاوران ایرانی.'
        ),
        'meta_keywords': (
            'حسین قشقایی, hossein qashqaeii, سازنده فایلینگ دیوار, '
            'توسعه دهنده CRM املاک, ربات دیوار'
        ),
        'pillar_links': [
            {
                'label': 'CRM مشاور املاک',
                'desc': 'راهنمای CRM رایگان',
                'landing_url_name': 'seo_landing_real_estate_crm',
            },
            {
                'label': 'نرم افزار مشاور املاک',
                'desc': 'میزکار یکپارچه',
                'landing_url_name': 'seo_landing_real_estate_software',
            },
            {
                'label': 'ربات دیوار',
                'desc': 'استخراج خودکار آگهی',
                'landing_url_name': 'seo_landing_robot_divar',
            },
        ],
    }
