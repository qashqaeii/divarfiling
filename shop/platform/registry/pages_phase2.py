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
            'راه‌حل پیدا کردن سریع فایل برای مشاور املاک: به‌جای اکسل و واتساپ، '
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
