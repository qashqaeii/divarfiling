"""محتوای صفحه نویسنده — E-E-A-T."""
from __future__ import annotations

AUTHOR_SLUG = 'hossein-qashqaeii'


def author_page_content() -> dict:
    return {
        'slug': AUTHOR_SLUG,
        'name': 'Hossein Qashqaeii',
        'name_fa': 'حسین قشقایی',
        'role': 'نویسنده و بنیان‌گذار فایلینگ دیوار',
        'tagline': (
            'توسعه‌دهنده، تحلیل‌گر داده و علاقه‌مند به ساخت ابزارهای کاربردی برای مشاوران املاک'
        ),
        'handquote': 'فناوری باید کار را ساده‌تر کند نه پیچیده‌تر...',
        'hero_quote': 'با داده‌های درست، فرصت‌های بهتری دیده می‌شوند.',
        'bio': (
            'من حسین قشقایی هستم؛ توسعه‌دهنده و معمار نرم‌افزار با تمرکز بر ساخت سیستم‌های '
            'کاربردی برای بازار املاک. فایلینگ دیوار از دل نیاز واقعی مشاوران شکل گرفت؛ '
            'پلتفرمی که استخراج داده، فایلینگ، CRM و تحلیل بازار را در یک میزکار یکپارچه '
            'کنار هم قرار می‌دهد.'
        ),
        'about_title': 'درباره حسین قشقایی',
        'about_paragraphs': [
            (
                'بیش از پنج سال در حوزه املاک و داده فعالیت کرده‌ام و همواره تلاش کرده‌ام فناوری را '
                'به ابزاری تبدیل کنم که کار روزمره مشاوران را ساده‌تر کند. از طراحی CRM و ERP '
                'سفارشی گرفته تا پلتفرم‌های تحلیلی و اتوماسیون فرآیندها، تمرکز من روی تبدیل '
                'فرآیندهای واقعی کسب‌وکار به نرم‌افزارهای قابل‌اتکا و قابل‌اندازه‌گیری است.'
            ),
            (
                'فایلینگ دیوار نتیجه همین رویکرد است؛ اکوسیستمی که داده را از مرحله استخراج تا '
                'تصمیم‌گیری در اختیار مشاور قرار می‌دهد و به او کمک می‌کند یک قدم جلوتر از بازار '
                'باشد.'
            ),
        ],
        'visuals': {
            'portrait': 'images/author-portrait.webp',
            'about_image': 'images/help-map-view.webp',
        },
        'social_links': [
            {
                'label': 'LinkedIn',
                'url': 'https://www.linkedin.com/in/hosseinqashqaeii',
                'icon': 'fab fa-linkedin-in',
            },
            {
                'label': 'YouTube',
                'url': 'https://www.youtube.com/@hosseinQashqaeii',
                'icon': 'fab fa-youtube',
            },
            {
                'label': 'Telegram',
                'url': 'https://t.me/hosseinQashqaeii',
                'icon': 'fab fa-telegram',
            },
            {
                'label': 'Instagram',
                'url': 'https://www.instagram.com/hosseinQashqaeii',
                'icon': 'fab fa-instagram',
            },
        ],
        'expertise': [
            'Custom CRM & ERP Systems',
            'Real Estate Market Analysis',
            'Customer Relationship Management',
            'Data Engineering & Automation',
            'SaaS Growth & Marketing',
        ],
        'expertise_section': {
            'title': 'حوزه‌های تخصصی',
        },
        'expertise_areas': [
            {'icon': 'fa-code', 'label': 'فناوری و محصول'},
            {'icon': 'fa-chart-bar', 'label': 'تحلیل بازار املاک'},
            {'icon': 'fa-users', 'label': 'CRM و مدیریت مشتری'},
            {'icon': 'fa-database', 'label': 'داده و اتوماسیون'},
            {'icon': 'fa-chart-line', 'label': 'رشد SaaS و مارکتینگ'},
        ],
        'stats_meta': {
            'years_experience': 5,
            'articles_label': 'مقاله تخصصی',
            'users_label': 'کاربر فعال',
            'users_label_thousands': 'هزار کاربر فعال',
            'data_label': 'داده استخراج شده',
            'years_label': 'سال تجربه در حوزه املاک و داده',
        },
        'articles_section': {
            'title': 'مقالات اخیر',
            'all_label': 'مشاهده همه مقالات',
        },
        'meta_title': (
            'حسین قشقایی | معمار نرم‌افزار — CRM، ERP و پلتفرم‌های تحلیلی سفارشی'
        ),
        'meta_description': (
            'حسین قشقایی، معمار و توسعه‌دهنده سیستم‌های نرم‌افزاری کسب‌وکار: CRM و ERP اختصاصی، '
            'پلتفرم‌های تحلیلی، اتوماسیون و زیرساخت داده. سازنده فایلینگ دیوار.'
        ),
        'meta_keywords': (
            'حسین قشقایی, hossein qashqaeii, معمار نرم‌افزار, CRM سفارشی, ERP اختصاصی, '
            'پلتفرم تحلیلی, اتوماسیون فرآیند, فایلینگ دیوار'
        ),
    }
