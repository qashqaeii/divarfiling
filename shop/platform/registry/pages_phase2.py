"""صفحات فاز ۲ — Product Lines + Solutions + Feature drafts."""
from __future__ import annotations

from shop.platform.types import PageSEO, PageSpec


def build_pages() -> list[PageSpec]:
    return [
        _filing_product_line(),
        _filing_search_feature_draft(),
        _filing_filter_feature_draft(),
        _filing_saved_search_feature_draft(),
        _fast_property_search_solution(),
        _market_intelligence_product_line(),
        _mi_price_analysis_feature_draft(),
        _mi_value_score_feature_draft(),
        _mi_map_analysis_feature_draft(),
        _mi_comparison_feature_draft(),
        _mi_pricing_tools_feature_draft(),
        _property_pricing_solution(),
        _agency_product_line(),
        _agency_team_management_feature_draft(),
        _agency_roles_feature_draft(),
        _agency_inbox_feature_draft(),
        _agency_activity_feature_draft(),
        _agency_reports_feature_draft(),
        _agency_tv_feature_draft(),
        _agency_announcements_feature_draft(),
        _agency_management_solution(),
        _extraction_product_line(),
        _extraction_location_filter_feature_draft(),
        _extraction_category_filter_feature_draft(),
        _extraction_deduplication_feature_draft(),
        _extraction_export_feature_draft(),
        _extraction_license_feature_draft(),
        _extraction_dataset_builder_feature_draft(),
        _extraction_advertiser_signals_feature_draft(),
        _build_property_database_solution(),
    ]


def _filing_product_line() -> PageSpec:
    seo = PageSEO(
        title='فایلینگ دیوار | بانک فایل Dataset، جستجو و نقشه آگهی — فایلینگ دیوار',
        description=(
            'فایلینگ دیوار بانک Dataset آگهی‌های استخراج‌شده است: آپلود، جدول فیلترپذیر، '
            'جزئیات آگهی، نقشه و مقایسه — روی همان میزکار. با لایسنس ربات فعال می‌شود.'
        ),
        keywords='فایلینگ دیوار, بانک فایل املاک, Dataset دیوار, جستجوی فایل مشاور, نقشه آگهی',
        og_title='فایلینگ دیوار — خط محصول بانک فایل',
        h1='فایلینگ: آگهی‌های دیوار را بانک فایل منظم کنید',
    )
    return PageSpec(
        section='features',
        path='filing',
        variant='product_line',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='sky',
        icon='fa-folder-tree',
        decor_icon='layers',
        product_line='filing',
        funnel_role='consideration',
        intent='commercial',
        primary_keyword='فایلینگ دیوار',
        content_key='filing_product_line',
        related_solutions=('build-property-database', 'fast-property-search'),
        related_articles=(
            'tatbiq-hooshmand-melk-moshtari-dataset-60s-rahnama',
        ),
        related_seo_landings=('robot-divar', 'real-estate-software'),
        sitemap_priority=0.87,
    )


def _draft_filing_feature(
    *,
    path: str,
    content_key: str,
    title: str,
    description: str,
    h1: str,
    keyword: str,
    icon: str,
) -> PageSpec:
    """Feature زیر فایلینگ — draft تا Sprint انتشار Feature."""
    seo = PageSEO(
        title=title,
        description=description,
        keywords=keyword,
        og_title=h1.split(':')[0].strip(),
        h1=h1,
    )
    return PageSpec(
        section='features',
        path=path,
        variant='feature',
        status='draft',
        marketability='section_only',
        seo=seo,
        accent='sky',
        icon=icon,
        decor_icon='layers',
        product_line='filing',
        parent_path='filing',
        funnel_role='consideration',
        intent='informational',
        primary_keyword=keyword.split(',')[0].strip(),
        content_key=content_key,
        related_solutions=('fast-property-search',),
        related_seo_landings=('robot-divar',),
        sitemap_priority=0.5,
    )


def _filing_search_feature_draft() -> PageSpec:
    return _draft_filing_feature(
        path='filing/search',
        content_key='filing_search',
        title='جستجوی فایل Dataset | Search در فایلینگ دیوار',
        description=(
            'جستجو روی جدول بانک فایل Dataset برای رسیدن سریع به آگهی مناسب در میزکار فایلینگ دیوار.'
        ),
        h1='جستجوی فایل: ردیف درست را در جدول Dataset پیدا کنید',
        keyword='جستجوی فایل Dataset, search فایلینگ دیوار',
        icon='fa-magnifying-glass',
    )


def _filing_filter_feature_draft() -> PageSpec:
    return _draft_filing_feature(
        path='filing/filter',
        content_key='filing_filter',
        title='فیلتر پیشرفته فایل | Advanced Filter فایلینگ دیوار',
        description=(
            'فیلتر بودجه، محله، متراژ و نوع معامله روی Dataset برای کوتاه کردن لیست قبل از پیشنهاد به مشتری.'
        ),
        h1='فیلتر پیشرفته: لیست فایل را قبل از پیشنهاد کوتاه کنید',
        keyword='فیلتر فایل املاک, فیلتر Dataset دیوار',
        icon='fa-filter',
    )


def _filing_saved_search_feature_draft() -> PageSpec:
    return _draft_filing_feature(
        path='filing/saved-search',
        content_key='filing_saved_search',
        title='جستجوی ذخیره‌شده فایل | Saved Search فایلینگ دیوار',
        description=(
            'ذخیرهٔ فیلترها و جستجوهای پرتکرار روی Dataset برای دسترسی سریع‌تر در روزهای شلوغ.'
        ),
        h1='جستجوی ذخیره‌شده: فیلترهای پرتکرار را دوباره نسازید',
        keyword='جستجوی ذخیره شده فایل, saved search املاک',
        icon='fa-bookmark',
    )


def _fast_property_search_solution() -> PageSpec:
    seo = PageSEO(
        title='پیدا کردن سریع فایل املاک | جستجوی Dataset — فایلینگ دیوار',
        description=(
            'راه‌حل پیدا کردن سریع فایل برای مشاور املاک: به‌جای دفترچه و گشتن دوباره روی دیوار، '
            'با فیلتر، جستجو، جزئیات و نقشه روی بانک Dataset فایل مناسب را پیشنهاد دهید.'
        ),
        keywords=(
            'پیدا کردن فایل املاک, جستجوی سریع فایل مشاور, فایلینگ دیوار, '
            'جستجوی Dataset, فیلتر آگهی دیوار'
        ),
        og_title='پیدا کردن سریع فایل — راه‌حل فایلینگ دیوار',
        h1='پیدا کردن سریع فایل: وقتی مشتری زنگ زد معطل نمانید',
    )
    return PageSpec(
        section='solutions',
        path='fast-property-search',
        variant='solution',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='sky',
        icon='fa-magnifying-glass-location',
        decor_icon='layers',
        funnel_role='conversion',
        intent='problem-solution',
        primary_keyword='پیدا کردن سریع فایل املاک',
        content_key='fast_property_search',
        related_features=('filing/search', 'filing/filter', 'filing/saved-search'),
        related_solutions=('build-property-database',),
        related_articles=(
            'tatbiq-hooshmand-melk-moshtari-dataset-60s-rahnama',
        ),
        related_seo_landings=('robot-divar',),
        sitemap_priority=0.84,
    )


def _market_intelligence_product_line() -> PageSpec:
    seo = PageSEO(
        title='تحلیل بازار املاک | آمار قیمت، نقشه و Value Score — فایلینگ دیوار',
        description=(
            'خط محصول تحلیل بازار: از Dataset فایلینگ آمار قیمت، نمودار، نقشه و Value Score '
            'بگیرید تا قیمت‌گذاری و پیشنهاد به مشتری حدسی نباشد.'
        ),
        keywords=(
            'تحلیل بازار املاک, Value Score, قیمت گذاری ملک, نقشه آگهی, '
            'آمار قیمت دیوار, فایلینگ دیوار'
        ),
        og_title='تحلیل بازار — خط محصول فایلینگ دیوار',
        h1='تحلیل بازار: قیمت را از داده بخوانید، نه از حدس',
    )
    return PageSpec(
        section='features',
        path='market-intelligence',
        variant='product_line',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='amber',
        icon='fa-chart-line',
        decor_icon='sparkles',
        product_line='market-intelligence',
        funnel_role='consideration',
        intent='commercial',
        primary_keyword='تحلیل بازار املاک',
        content_key='market_intelligence_product_line',
        related_solutions=('property-pricing',),
        related_seo_landings=('robot-divar', 'real-estate-software'),
        sitemap_priority=0.86,
    )


def _draft_mi_feature(
    *,
    path: str,
    content_key: str,
    title: str,
    description: str,
    h1: str,
    keyword: str,
    icon: str,
) -> PageSpec:
    seo = PageSEO(
        title=title,
        description=description,
        keywords=keyword,
        og_title=h1.split(':')[0].strip(),
        h1=h1,
    )
    return PageSpec(
        section='features',
        path=path,
        variant='feature',
        status='draft',
        marketability='section_only',
        seo=seo,
        accent='amber',
        icon=icon,
        decor_icon='sparkles',
        product_line='market-intelligence',
        parent_path='market-intelligence',
        funnel_role='consideration',
        intent='informational',
        primary_keyword=keyword.split(',')[0].strip(),
        content_key=content_key,
        related_solutions=('property-pricing',),
        related_seo_landings=('robot-divar',),
        sitemap_priority=0.5,
    )


def _mi_price_analysis_feature_draft() -> PageSpec:
    return _draft_mi_feature(
        path='market-intelligence/price-analysis',
        content_key='mi_price_analysis',
        title='تحلیل قیمت Dataset | Price Analysis فایلینگ دیوار',
        description='آمار میانه، میانگین و بازه قیمت روی Dataset برای قیمت‌گذاری مستندتر.',
        h1='تحلیل قیمت: میانه و بازه را از Dataset بخوانید',
        keyword='تحلیل قیمت ملک, میانه قیمت املاک',
        icon='fa-chart-pie',
    )


def _mi_value_score_feature_draft() -> PageSpec:
    return _draft_mi_feature(
        path='market-intelligence/value-score',
        content_key='mi_value_score',
        title='Value Score املاک | امتیاز ارزش نسبی فایلینگ دیوار',
        description='مقایسه نسبی قیمت آگهی با انتظار بازار همان Dataset — بدون ادعای فرصت قطعی.',
        h1='Value Score: نسبت قیمت به انتظار Dataset',
        keyword='Value Score املاک, فایل زیر بازار',
        icon='fa-percent',
    )


def _mi_map_analysis_feature_draft() -> PageSpec:
    return _draft_mi_feature(
        path='market-intelligence/map-analysis',
        content_key='mi_map_analysis',
        title='تحلیل نقشه املاک | Map Analysis فایلینگ دیوار',
        description='پراکندگی مکانی آگهی‌های Dataset برای قیمت‌گذاری آگاهانه‌تر از محدوده.',
        h1='تحلیل نقشه: پراکندگی قیمت را روی زمین ببینید',
        keyword='نقشه قیمت املاک, تحلیل نقشه آگهی',
        icon='fa-map-location-dot',
    )


def _mi_comparison_feature_draft() -> PageSpec:
    return _draft_mi_feature(
        path='market-intelligence/comparison',
        content_key='mi_comparison',
        title='مقایسه دوره‌ای قیمت | Comparison فایلینگ دیوار',
        description='مقایسه دو Dataset یا دوره استخراج برای دیدن تغییر قیمت مشاهده‌شده.',
        h1='مقایسه دوره‌ای: تغییر قیمت را بین دو استخراج ببینید',
        keyword='مقایسه قیمت املاک, مقایسه Dataset',
        icon='fa-scale-balanced',
    )


def _mi_pricing_tools_feature_draft() -> PageSpec:
    return _draft_mi_feature(
        path='market-intelligence/pricing-tools',
        content_key='mi_pricing_tools',
        title='ابزارهای قیمت‌گذاری | Pricing Tools فایلینگ دیوار',
        description='محاسبات کمکی قیمت متری، تبدیل رهن/اجاره و پیشنهاد بر پایه میانه بازار.',
        h1='ابزارهای قیمت: محاسبه سریع کنار تحلیل Dataset',
        keyword='ابزار قیمت گذاری ملک, محاسبه قیمت متری',
        icon='fa-wand-magic-sparkles',
    )


def _property_pricing_solution() -> PageSpec:
    seo = PageSEO(
        title='قیمت‌گذاری ملک با تحلیل فایل‌های مشابه | فایلینگ دیوار',
        description=(
            'فایل‌های مشابه، میانه قیمت، نقشه و Value Score را بررسی کنید '
            'و برای مذاکره ملک به یک بازه منطقی‌تر برسید؛ بدون ادعای قیمت قطعی.'
        ),
        keywords=(
            'قیمت گذاری ملک, تخمین قیمت ملک, تحلیل قیمت املاک, '
            'مقایسه قیمت املاک, فایل مشابه, Value Score'
        ),
        og_title='قیمت‌گذاری ملک — راه‌حل تحلیل بازار فایلینگ دیوار',
        h1='قیمت ملک را با فایل‌های مشابه بررسی کنید، نه فقط با حدس',
    )
    return PageSpec(
        section='solutions',
        path='property-pricing',
        variant='solution',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='indigo',
        icon='fa-tags',
        decor_icon='sparkles',
        funnel_role='conversion',
        intent='problem-solution',
        primary_keyword='قیمت گذاری ملک',
        content_key='property_pricing',
        related_features=(
            'market-intelligence/price-analysis',
            'market-intelligence/value-score',
            'market-intelligence/map-analysis',
            'market-intelligence/comparison',
            'market-intelligence/pricing-tools',
        ),
        related_articles=('gozaresh-gheymat-malek-divar-dade-rahnama',),
        related_seo_landings=('robot-divar', 'real-estate-software'),
        sitemap_priority=0.84,
    )


def _agency_product_line() -> PageSpec:
    seo = PageSEO(
        title='مدیریت آژانس املاک | CRM تیمی، نقش‌ها و Agency TV — فایلینگ دیوار',
        description=(
            'خط محصول مدیریت آژانس: نقش‌ها، صندوق سرنخ، تخصیص، پیام و اطلاعیه، '
            'گزارش عملکرد و Agency TV — رایگان با CRM، بدون افشای بی‌دلیل پرونده مشتری.'
        ),
        keywords=(
            'مدیریت آژانس املاک, CRM تیمی املاک, مدیریت مشاوران املاک, '
            'Agency TV, گزارش عملکرد مشاور, مدیریت دفتر املاک'
        ),
        og_title='مدیریت آژانس — خط محصول فایلینگ دیوار',
        h1='مدیریت تیم آژانس؛ بدون گزارش‌های پراکنده و پیگیری‌های گمشده',
    )
    return PageSpec(
        section='features',
        path='agency',
        variant='product_line',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='violet',
        icon='fa-people-group',
        decor_icon='users',
        product_line='agency',
        funnel_role='consideration',
        intent='commercial',
        primary_keyword='مدیریت آژانس املاک',
        content_key='agency_product_line',
        related_solutions=('agency-management',),
        related_articles=(
            'crm-team-modiriyat-ajans-rahnama',
            'agency-tv-dashboard-ajans-amlak',
        ),
        related_seo_landings=('real-estate-crm',),
        sitemap_priority=0.86,
    )


def _draft_agency_feature(
    *,
    path: str,
    content_key: str,
    title: str,
    description: str,
    h1: str,
    keyword: str,
    icon: str,
) -> PageSpec:
    seo = PageSEO(
        title=title,
        description=description,
        keywords=keyword,
        og_title=h1.split(':')[0].strip(),
        h1=h1,
    )
    return PageSpec(
        section='features',
        path=path,
        variant='feature',
        status='draft',
        marketability='section_only',
        seo=seo,
        accent='violet',
        icon=icon,
        decor_icon='users',
        product_line='agency',
        parent_path='agency',
        funnel_role='consideration',
        intent='informational',
        primary_keyword=keyword.split(',')[0].strip(),
        content_key=content_key,
        related_seo_landings=('real-estate-crm',),
        sitemap_priority=0.5,
    )


def _agency_team_management_feature_draft() -> PageSpec:
    return _draft_agency_feature(
        path='agency/team-management',
        content_key='agency_team_management',
        title='مدیریت اعضای تیم آژانس | Team Management فایلینگ دیوار',
        description='دعوت اعضا، وضعیت عضویت و هماهنگی تیم آژانس در میزکار CRM.',
        h1='مدیریت تیم: اعضا را به آژانس اضافه کنید',
        keyword='مدیریت تیم آژانس, اعضای CRM تیمی',
        icon='fa-people-group',
    )


def _agency_roles_feature_draft() -> PageSpec:
    return _draft_agency_feature(
        path='agency/roles-permissions',
        content_key='agency_roles_permissions',
        title='نقش‌ها و دسترسی آژانس | Roles فایلینگ دیوار',
        description='نقش‌های مالک، مدیر، منشی و مشاور برای کنترل دسترسی در تیم آژانس.',
        h1='نقش‌ها: دسترسی متناسب با مسئولیت',
        keyword='نقش مشاور املاک, دسترسی مدیر آژانس',
        icon='fa-user-tag',
    )


def _agency_inbox_feature_draft() -> PageSpec:
    return _draft_agency_feature(
        path='agency/team-inbox',
        content_key='agency_team_inbox',
        title='صندوق سرنخ تیم | Team Inbox فایلینگ دیوار',
        description='سرنخ‌های تخصیص‌نیافته و تخصیص به مشاور در صندوق تیم آژانس.',
        h1='صندوق تیم: سرنخ بدون مسئول نماند',
        keyword='صندوق سرنخ آژانس, تخصیص سرنخ املاک',
        icon='fa-inbox',
    )


def _agency_activity_feature_draft() -> PageSpec:
    return _draft_agency_feature(
        path='agency/activity-feed',
        content_key='agency_activity_feed',
        title='فعالیت و ممیزی تیم | Activity فایلینگ دیوار',
        description='مرور رویدادهای ثبت‌شده تیمی و مسیر ممیزی برای مدیر آژانس.',
        h1='فعالیت تیم: رویدادهای ثبت‌شده را مرور کنید',
        keyword='فعالیت تیم آژانس, ممیزی CRM تیمی',
        icon='fa-clock-rotate-left',
    )


def _agency_reports_feature_draft() -> PageSpec:
    return _draft_agency_feature(
        path='agency/reports',
        content_key='agency_reports',
        title='گزارش عملکرد تیم | Reports فایلینگ دیوار',
        description='گزارش عملکرد مشاوران و خروجی CSV برای ارزیابی پیگیری و فعالیت.',
        h1='گزارش تیم: عملکرد ثبت‌شده را ببینید',
        keyword='گزارش عملکرد مشاور, KPI آژانس املاک',
        icon='fa-chart-column',
    )


def _agency_tv_feature_draft() -> PageSpec:
    return _draft_agency_feature(
        path='agency/tv-dashboard',
        content_key='agency_tv_dashboard',
        title='Agency TV | داشبورد نمایشگر دفتر فایلینگ دیوار',
        description='نمایش KPI و برنامه دفتر روی تلویزیون بدون شماره مشتری؛ به‌روزرسانی دوره‌ای.',
        h1='Agency TV: وضعیت دفتر روی نمایشگر',
        keyword='Agency TV, داشبورد آژانس املاک',
        icon='fa-tv',
    )


def _agency_announcements_feature_draft() -> PageSpec:
    return _draft_agency_feature(
        path='agency/announcements',
        content_key='agency_announcements',
        title='اطلاعیه تیم آژانس | Announcements فایلینگ دیوار',
        description='تابلوی اطلاعیه برای اعلامیه‌های مهم اعضای آژانس در میزکار.',
        h1='اطلاعیه تیم: پیام مهم در یک محل مشخص',
        keyword='اطلاعیه آژانس املاک, announcement CRM',
        icon='fa-bullhorn',
    )


def _agency_management_solution() -> PageSpec:
    seo = PageSEO(
        title='مدیریت آژانس املاک؛ تیم، سرنخ و پیگیری در یک میزکار',
        description=(
            'نقش‌ها، صندوق سرنخ، تخصیص، پیگیری معوق و گزارش عملکرد تیم املاک را '
            'در یک میزکار رایگان مدیریت کنید؛ بدون ادعای کنترل مطلق یا افشای پرونده‌ها.'
        ),
        keywords=(
            'مدیریت آژانس املاک, نرم افزار مدیریت آژانس, مدیریت تیم مشاوران املاک, '
            'CRM تیمی املاک, تخصیص سرنخ, گزارش عملکرد مشاور, پیگیری تیم فروش, '
            'مدیریت دفتر املاک, داشبورد آژانس, Agency TV'
        ),
        og_title='مدیریت آژانس املاک — راه‌حل تیم و سرنخ فایلینگ دیوار',
        h1='مدیریت آژانس املاک؛ بدانید کار دست چه کسی است',
    )
    return PageSpec(
        section='solutions',
        path='agency-management',
        variant='solution',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='violet',
        icon='fa-people-group',
        decor_icon='users',
        funnel_role='conversion',
        intent='problem-solution',
        primary_keyword='مدیریت آژانس املاک',
        content_key='agency_management',
        related_features=(
            'agency/team-management',
            'agency/roles-permissions',
            'agency/team-inbox',
            'agency/reports',
            'agency/tv-dashboard',
        ),
        related_articles=(
            'crm-team-modiriyat-ajans-rahnama',
            'agency-tv-dashboard-ajans-amlak',
        ),
        related_seo_landings=('real-estate-crm',),
        sitemap_priority=0.84,
    )


def _extraction_product_line() -> PageSpec:
    seo = PageSEO(
        title='ربات استخراج آگهی دیوار | ساخت Dataset برای فایلینگ املاک',
        description=(
            'آگهی‌های دیوار را با محدوده و نوع معامله ساختاریافته استخراج کنید، '
            'خروجی Excel/CSV/JSON بسازید و به فایلینگ بسپارید؛ روی ویندوز و با لایسنس فعال.'
        ),
        keywords=(
            'ربات استخراج آگهی دیوار, استخراج آگهی املاک, ربات دیوار املاک, '
            'خروجی آگهی دیوار, ساخت بانک فایل املاک, Dataset املاک, '
            'خروجی اکسل دیوار, حذف آگهی تکراری, استخراج فایل منطقه'
        ),
        og_title='ربات استخراج آگهی — خط محصول فایلینگ دیوار',
        h1='استخراج آگهی‌های دیوار و ساخت Dataset برای فایلینگ املاک',
    )
    return PageSpec(
        section='features',
        path='extraction',
        variant='product_line',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='orange',
        icon='fa-robot',
        decor_icon='robot',
        product_line='extraction',
        funnel_role='consideration',
        intent='commercial',
        primary_keyword='ربات استخراج آگهی دیوار',
        content_key='extraction_product_line',
        related_solutions=('build-property-database', 'fast-property-search'),
        related_seo_landings=('robot-divar',),
        sitemap_priority=0.88,
    )


def _build_property_database_solution() -> PageSpec:
    seo = PageSEO(
        title='ساخت بانک فایل املاک؛ از استخراج آگهی تا Dataset قابل جستجو',
        description=(
            'آگهی‌های منطقه را ساختاریافته استخراج کنید، تکراری‌ها را کنترل کنید '
            'و در فایلینگ دیوار یک بانک فایل قابل جستجو، مقایسه و تحلیل بسازید.'
        ),
        keywords=(
            'ساخت بانک فایل املاک, بانک فایل املاک, ساخت فایلینگ املاک, '
            'جمع‌آوری فایل ملک, مدیریت فایل‌های املاک, بانک اطلاعات املاک, '
            'Dataset املاک, استخراج آگهی املاک, فایل‌یابی املاک, حذف فایل تکراری, '
            'به‌روزرسانی بانک فایل'
        ),
        og_title='ساخت بانک فایل املاک — راه‌حل فایلینگ دیوار',
        h1='ساخت بانک فایل املاک؛ از آگهی پراکنده تا Dataset قابل جستجو',
    )
    return PageSpec(
        section='solutions',
        path='build-property-database',
        variant='solution',
        status='published',
        marketability='marketable',
        seo=seo,
        accent='orange',
        icon='fa-database',
        decor_icon='layers',
        funnel_role='conversion',
        intent='problem-solution',
        primary_keyword='ساخت بانک فایل املاک',
        content_key='build_property_database',
        related_features=(
            'extraction/dataset-builder',
            'extraction/deduplication',
            'extraction/export',
            'filing/search',
            'filing/filter',
        ),
        related_articles=(
            'hazf-agahi-tekrari-divar-bank-file-rahnama',
            'bank-file-mantaghe-amlak',
        ),
        related_seo_landings=('robot-divar',),
        sitemap_priority=0.85,
    )


def _draft_extraction_feature(
    *,
    path: str,
    content_key: str,
    title: str,
    description: str,
    h1: str,
    keyword: str,
    icon: str,
) -> PageSpec:
    seo = PageSEO(
        title=title,
        description=description,
        keywords=keyword,
        og_title=h1.split(':')[0].strip(),
        h1=h1,
    )
    return PageSpec(
        section='features',
        path=path,
        variant='feature',
        status='draft',
        marketability='section_only',
        seo=seo,
        accent='orange',
        icon=icon,
        decor_icon='robot',
        product_line='extraction',
        parent_path='extraction',
        funnel_role='consideration',
        intent='informational',
        primary_keyword=keyword.split(',')[0].strip(),
        content_key=content_key,
        related_seo_landings=('robot-divar',),
        sitemap_priority=0.5,
    )


def _extraction_location_filter_feature_draft() -> PageSpec:
    return _draft_extraction_feature(
        path='extraction/location-filter',
        content_key='extraction_location_filter',
        title='فیلتر محدوده استخراج | استان شهر محله',
        description='انتخاب استان، شهر و محله برای استخراج هدفمند آگهی‌های دیوار.',
        h1='محدوده: فقط بازار هدف را استخراج کنید',
        keyword='فیلتر شهر دیوار, استخراج محله املاک',
        icon='fa-map-location-dot',
    )


def _extraction_category_filter_feature_draft() -> PageSpec:
    return _draft_extraction_feature(
        path='extraction/category-filter',
        content_key='extraction_category_filter',
        title='فیلتر نوع معامله و دسته ملک | ربات استخراج',
        description='فروش، اجاره و دسته‌های ملکی واقعی در ربات استخراج فایلینگ دیوار.',
        h1='نوع معامله: فروش و اجاره را جدا نگه دارید',
        keyword='استخراج فروش اجاره, دسته ملک دیوار',
        icon='fa-tags',
    )


def _extraction_deduplication_feature_draft() -> PageSpec:
    return _draft_extraction_feature(
        path='extraction/deduplication',
        content_key='extraction_deduplication',
        title='حذف آگهی تکراری | Deduplication',
        description='کنترل تکراری بر اساس شناسه آگهی در خروجی Excel و واردات Filing.',
        h1='تکراری‌ها: Dataset تمیزتر با شناسه آگهی',
        keyword='حذف آگهی تکراری, deduplication املاک',
        icon='fa-clone',
    )


def _extraction_export_feature_draft() -> PageSpec:
    return _draft_extraction_feature(
        path='extraction/export',
        content_key='extraction_export',
        title='خروجی Excel CSV JSON | Export ربات',
        description='خروجی‌های واقعی ربات استخراج: Excel، CSV و JSON.',
        h1='خروجی: Excel، CSV و JSON',
        keyword='خروجی اکسل دیوار, CSV آگهی املاک',
        icon='fa-file-export',
    )


def _extraction_license_feature_draft() -> PageSpec:
    return _draft_extraction_feature(
        path='extraction/license-management',
        content_key='extraction_license_management',
        title='مدیریت لایسنس ربات | License',
        description='کلید لایسنس، اتصال به دستگاه ویندوز و وضعیت انقضا.',
        h1='لایسنس: فعال‌سازی روی دستگاه ویندوز',
        keyword='لایسنس ربات دیوار, فعال سازی لایسنس',
        icon='fa-key',
    )


def _extraction_dataset_builder_feature_draft() -> PageSpec:
    return _draft_extraction_feature(
        path='extraction/dataset-builder',
        content_key='extraction_dataset_builder',
        title='ساخت Dataset | آپلود به فایلینگ',
        description='آپلود مستقیم از ربات یا بارگذاری دستی خروجی به بانک فایل.',
        h1='Dataset: از خروجی ربات تا فایلینگ',
        keyword='ساخت Dataset املاک, آپلود فایلینگ',
        icon='fa-database',
    )


def _extraction_advertiser_signals_feature_draft() -> PageSpec:
    return _draft_extraction_feature(
        path='extraction/advertiser-signals',
        content_key='extraction_advertiser_signals',
        title='سیگنال آگهی‌دهنده | شخصی یا بنگاه',
        description='فیلتر شخصی و سیگنال نوع حساب — بدون ادعای هویت قطعی مالک.',
        h1='سیگنال آگهی‌دهنده: احتمالی، نه قطعی',
        keyword='آگهی شخصی دیوار, تشخیص مشاور مالک',
        icon='fa-id-badge',
    )
