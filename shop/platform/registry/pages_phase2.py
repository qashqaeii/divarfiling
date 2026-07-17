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
        related_solutions=('fast-property-search',),
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
