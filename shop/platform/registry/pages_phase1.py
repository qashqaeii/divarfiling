"""صفحات فاز ۱ — فقط published و marketable."""
from __future__ import annotations

from shop.platform.types import PageSEO, PageSpec


def build_pages() -> list[PageSpec]:
    return [
        _features_hub(),
        _crm_product_line(),
        _crm_reminders_feature(),
        _solutions_hub(),
        _customer_follow_up_solution(),
    ]


def _features_hub() -> PageSpec:
    seo = PageSEO(
        title='امکانات فایلینگ دیوار | CRM، فایلینگ، تحلیل بازار و مدیریت آژانس',
        description=(
            'بخش‌های اصلی پلتفرم فایلینگ دیوار برای مشاوران و مدیران آژانس: '
            'CRM رایگان، فایلینگ هوشمند، تحلیل بازار، مدیریت تیم، ربات استخراج و اپ موبایل.'
        ),
        keywords='امکانات فایلینگ دیوار, CRM املاک, فایلینگ هوشمند, میزکار مشاور املاک',
        og_title='امکانات پلتفرم فایلینگ دیوار',
        h1='امکانات پلتفرم فایلینگ دیوار',
    )
    return PageSpec(
        section='features',
        path='',
        variant='hub',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='violet',
        icon='fa-layer-group',
        decor_icon='layers',
        funnel_role='awareness',
        intent='navigational',
        primary_keyword='امکانات فایلینگ دیوار',
        content_key='features_hub',
        related_seo_landings=('real-estate-software', 'real-estate-crm'),
        sitemap_priority=0.92,
        sitemap_changefreq='weekly',
    )


def _crm_product_line() -> PageSpec:
    seo = PageSEO(
        title='CRM املاک فایلینگ دیوار | مدیریت مشتری، معامله و پیگیری — رایگان',
        description=(
            'CRM املاک آنلاین و فارسی: مخاطب، قیف معامله، یادآور، تقویم، قالب پیام '
            'و اتصال به فایل‌های دیوار. ثبت‌نام میزکار رایگان است.'
        ),
        keywords='CRM املاک, CRM مشاور املاک, مدیریت مشتری املاک, CRM رایگان',
        og_title='CRM املاک — خط محصول فایلینگ دیوار',
        h1='CRM املاک: مشتری، معامله و پیگیری را در یک میزکار نگه دارید',
    )
    return PageSpec(
        section='features',
        path='crm',
        variant='product_line',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='rose',
        icon='fa-users',
        decor_icon='clipboard_list',
        product_line='crm',
        funnel_role='consideration',
        intent='commercial',
        primary_keyword='CRM املاک',
        content_key='crm_product_line',
        related_solutions=('customer-follow-up',),
        related_articles=(
            'crm-amlak-raygan-rahnama',
            'behtarin-crm-moshaver-amlak-iran-1405',
            'peigiri-moshtari-moshaver-amlak',
            'crm-team-modiriyat-ajans-rahnama',
        ),
        related_seo_landings=('real-estate-crm',),
        sitemap_priority=0.88,
    )


def _crm_reminders_feature() -> PageSpec:
    seo = PageSEO(
        title='یادآور و تقویم CRM املاک | پیگیری به‌موقع مشتری — فایلینگ دیوار',
        description=(
            'یادآور تماس، بازدید و قرار در CRM املاک فایلینگ دیوار. '
            'صف کار امروز و تقویم ماهانه تا هیچ پیگیری از قلم نیفتد.'
        ),
        keywords='یادآور CRM املاک, پیگیری مشتری مشاور, تقویم مشاور املاک, صف کار امروز',
        og_title='یادآور و تقویم CRM',
        h1='یادآور CRM: فردا صبح بدانید اول به کی زنگ بزنید',
    )
    return PageSpec(
        section='features',
        path='crm/reminders',
        variant='feature',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='amber',
        icon='fa-bell',
        decor_icon='sticky_note',
        product_line='crm',
        parent_path='crm',
        funnel_role='consideration',
        intent='informational',
        primary_keyword='یادآور CRM املاک',
        content_key='crm_reminders',
        related_solutions=('customer-follow-up',),
        related_articles=(
            'peigiri-moshtari-moshaver-amlak',
            'automation-crm-5-ghanon-pigiri-rahnama',
            'crm-amlak-raygan-rahnama',
        ),
        related_seo_landings=('real-estate-crm',),
        sitemap_priority=0.82,
    )


def _solutions_hub() -> PageSpec:
    seo = PageSEO(
        title='راه‌حل‌های فایلینگ دیوار | حل چالش‌های روزانه مشاور و مدیر آژانس',
        description=(
            'راه‌حل‌های عملی برای مشاوران املاک: پیگیری مشتری، جستجوی سریع فایل، '
            'قیمت‌گذاری، مدیریت تیم و بیشتر — با میزکار فایلینگ دیوار.'
        ),
        keywords='راه حل CRM املاک, چالش مشاور املاک, نرم افزار آژانس املاک',
        og_title='راه‌حل‌های فایلینگ دیوار',
        h1='راه‌حل‌ها برای کار واقعی مشاور و مدیر آژانس',
    )
    return PageSpec(
        section='solutions',
        path='',
        variant='hub',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='emerald',
        icon='fa-lightbulb',
        decor_icon='sparkles',
        funnel_role='awareness',
        intent='problem-aware',
        primary_keyword='راه حل CRM املاک',
        content_key='solutions_hub',
        sitemap_priority=0.85,
        sitemap_changefreq='weekly',
    )


def _customer_follow_up_solution() -> PageSpec:
    seo = PageSEO(
        title='پیگیری مشتری املاک | هیچ مشتری‌ای را فراموش نکنید — فایلینگ دیوار',
        description=(
            'راه‌حل پیگیری مشتری برای مشاور املاک: یادآور، صف کار امروز، تقویم '
            'و اتوماسیون CRM تا تماس دوم و سوم از قلم نیفتد.'
        ),
        keywords='پیگیری مشتری مشاور املاک, فراموشی پیگیری, CRM پیگیری, یادآور مشتری',
        og_title='پیگیری مشتری — راه‌حل فایلینگ دیوار',
        h1='هیچ مشتری‌ای را فراموش نکنید',
    )
    return PageSpec(
        section='solutions',
        path='customer-follow-up',
        variant='solution',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='rose',
        icon='fa-phone-volume',
        decor_icon='clipboard_list',
        funnel_role='conversion',
        intent='problem-solution',
        primary_keyword='پیگیری مشتری مشاور املاک',
        content_key='customer_follow_up',
        related_features=('crm/reminders',),
        related_articles=('peigiri-moshtari-moshaver-amlak',),
        related_seo_landings=('real-estate-crm',),
        sitemap_priority=0.84,
    )
