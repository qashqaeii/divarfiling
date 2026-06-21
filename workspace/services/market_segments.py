"""پروفایل تحلیل حرفه‌ای — بر اساس نوع معامله، دسته و زیردسته ملک."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

PROJECT_KEYS = ('پروژه', 'ساخت‌وساز', 'ساخت وساز', 'project', 'ساختمان')
LAND_KEYS = ('کلنگی', 'زمین', 'عرصه', 'باغ ویلا', 'باغ‌ویلا')
VILLA_KEYS = ('ویلا', 'ویلایی', 'خانه و ویلا', 'خانه')
COMMERCIAL_KEYS = (
    'اداری', 'تجاری', 'دفتر', 'مغازه', 'غرفه', 'کارگاه', 'انبار', 'صنعتی',
    'office', 'commercial', 'مطب', 'اتاق اداری', 'کشاورزی',
)
APARTMENT_KEYS = ('آپارتمان', 'apartment')
SHOP_KEYS = ('مغازه', 'غرفه')
OFFICE_KEYS = ('دفتر', 'اداری', 'مطب', 'اتاق اداری')
INDUSTRIAL_KEYS = ('صنعتی', 'کشاورزی', 'کارگاه', 'انبار', 'تجاری صنعتی')


def _blob(dataset_name: str, subcategory: str) -> str:
    return f'{dataset_name} {subcategory}'.lower().replace('_', ' ')


def detect_property_type(dataset_name: str, subcategory: str) -> str:
    """دسته اصلی ملک: residential | villa | land | commercial | project."""
    text = _blob(dataset_name, subcategory)
    if any(k in text for k in PROJECT_KEYS):
        return 'project'
    if any(k in text for k in LAND_KEYS) and not any(k in text for k in ('آپارتمان',)):
        return 'land'
    if any(k in text for k in COMMERCIAL_KEYS):
        return 'commercial'
    if any(k in text for k in VILLA_KEYS):
        return 'villa'
    return 'residential'


def normalize_subcategory(
    dataset_name: str,
    subcategory: str,
    prop: str,
) -> str:
    """زیردسته نرمال — apartment, villa, kolongi, office, shop, industrial, project."""
    text = _blob(dataset_name, subcategory)
    if any(k in text for k in PROJECT_KEYS):
        return 'project'
    if any(k in text for k in APARTMENT_KEYS):
        return 'apartment'
    if any(k in text for k in SHOP_KEYS):
        return 'shop'
    if any(k in text for k in OFFICE_KEYS):
        return 'office'
    if any(k in text for k in INDUSTRIAL_KEYS):
        return 'industrial'
    if 'کلنگی' in text:
        return 'kolongi'
    if any(k in text for k in ('زمین', 'عرصه')):
        return 'land_plot'
    if any(k in text for k in VILLA_KEYS):
        return 'villa'
    defaults = {
        'villa': 'villa',
        'land': 'kolongi',
        'commercial': 'office',
        'project': 'project',
    }
    return defaults.get(prop, 'apartment')


def segment_key(deal: str, prop: str, sub_key: str) -> str:
    return f'{deal}_{prop}_{sub_key}'


def _base_profile(
    *,
    unit_word: str,
    metric_mode: str,
    market_value_mode: str,
    sample_areas: List[int],
    overview_title: str,
    depth_metric_word: str,
    specialty_tips: Optional[List[str]] = None,
    scenario_unit_word: Optional[str] = None,
    bands_on: str = 'pps',
    client_word: str = 'مشتری',
    show_build_year: bool = True,
    show_residential_amenities: bool = True,
    scenario_range_first: bool = False,
    amenities_section_title: str = 'امکانات و وضعیت بنا',
    commercial_focus_tips: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        'unit_word': unit_word,
        'scenario_unit_word': scenario_unit_word or unit_word,
        'metric_mode': metric_mode,
        'market_value_mode': market_value_mode,
        'sample_areas': sample_areas,
        'overview_title': overview_title,
        'depth_metric_word': depth_metric_word,
        'specialty_tips': specialty_tips or [],
        'bands_on': bands_on,
        'client_word': client_word,
        'show_build_year': show_build_year,
        'show_residential_amenities': show_residential_amenities,
        'scenario_range_first': scenario_range_first,
        'amenities_section_title': amenities_section_title,
        'commercial_focus_tips': commercial_focus_tips or [],
    }


# پروفایل‌های تخصصی — با fallback در resolve_segment_profile
SEGMENT_PROFILES: Dict[str, Dict[str, Any]] = {
  # ─── فروش مسکونی ───
    'sale_residential_apartment': _base_profile(
        unit_word='آپارتمان',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[80, 100, 120],
        overview_title='تحلیل کلی فروش آپارتمان',
        depth_metric_word='قیمت هر متر',
        bands_on='pps',
        specialty_tips=[
            'در آپارتمان، قیمت هر متر خط قرمز مقایسه است — قبل از بازدید متری آگهی را چک کن.',
            'طبقه، نورگیر و وضعیت مشاعات در همین بازه متراژ اثر مستقیم روی قیمت دارد.',
        ],
    ),
    'sale_residential_villa': _base_profile(
        unit_word='ویلا',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[200, 250, 300],
        overview_title='تحلیل کلی فروش ویلا',
        depth_metric_word='قیمت هر متر',
        bands_on='pps',
        specialty_tips=[
            'در ویلا علاوه بر زیربنا، عرصه و بر ملک را جدا بررسی کن — متری فقط راهنماست.',
            'سال ساخت، دیوارکشی و دسترسی به معبر اصلی در قیمت ویلا تعیین‌کننده‌تر از آپارتمان است.',
        ],
    ),
    'sale_villa_villa': _base_profile(
        unit_word='ویلا',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[200, 250, 300],
        overview_title='تحلیل کلی فروش ویلا',
        depth_metric_word='قیمت هر متر',
        bands_on='pps',
        specialty_tips=[
            'در ویلا علاوه بر زیربنا، عرصه و بر ملک را جدا بررسی کن — متری فقط راهنماست.',
            'سال ساخت، دیوارکشی و دسترسی به معبر اصلی در قیمت ویلا تعیین‌کننده‌تر از آپارتمان است.',
        ],
    ),
    'rent_villa_villa': _base_profile(
        unit_word='ویلا',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[150, 200, 250],
        overview_title='تحلیل کلی اجاره ویلا',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
        specialty_tips=[
            'اجاره ویلا معمولاً ترکیب رهن بالا + اجاره پایین است — مبنای مقایسه رهن کامل معادل است.',
            'حیاط، پارکینگ و وضعیت بنا در اجاره ویلا اثر بیشتری از آپارتمان دارد.',
        ],
    ),
    # ─── فروش کلنگی / زمین ───
    'sale_land_kolongi': _base_profile(
        unit_word='کلنگی',
        metric_mode='total_price',
        market_value_mode='total',
        sample_areas=[100, 150, 200],
        overview_title='تحلیل کلی فروش کلنگی',
        depth_metric_word='قیمت کل',
        bands_on='price',
        specialty_tips=[
            'در کلنگی قیمت کل ملک مهم‌تر از متری است — گشت اراضی و بنا را جدا ببین.',
            'سهم‌الارث، سند و وضعیت ساختمان قدیمی قبل از پیشنهاد به خریدار شفاف شود.',
        ],
    ),
    'sale_land_land_plot': _base_profile(
        unit_word='زمین',
        metric_mode='total_price',
        market_value_mode='total',
        sample_areas=[150, 200, 300],
        overview_title='تحلیل کلی فروش زمین',
        depth_metric_word='قیمت کل',
        bands_on='price',
        specialty_tips=[
            'برای زمین، قیمت کل و کاربری مهم‌تر از قیمت هر متر است.',
            'بر، طول بر، گذر و بافت شهری را در کنار قیمت بررسی کن.',
        ],
    ),
    # ─── فروش اداری / تجاری ───
    'sale_commercial_office': _base_profile(
        unit_word='دفتر',
        scenario_unit_word='دفتر کار',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[50, 80, 120],
        overview_title='تحلیل کلی فروش اداری',
        depth_metric_word='قیمت هر متر زیربنا',
        bands_on='pps',
        show_build_year=False,
        show_residential_amenities=False,
        scenario_range_first=True,
        amenities_section_title='ویژگی‌های اداری',
        commercial_focus_tips=[
            'موقعیت مکانی، طبقه و دسترسی مترو/بزرگراه مهم‌تر از امکانات مسکونی است.',
            'کلاس اداری ساختمان و تعداد پارکینگ اختصاصی را در مذاکره لحاظ کن.',
        ],
        specialty_tips=[
            'در دفتر، موقعیت مکانی، طبقه و دسترسی مترو/بزرگراه اثر بیشتری از امکانات مسکونی دارد.',
            'متری زیربنا را با فایل‌های هم‌محله و هم‌متراژ مقایسه کن، نه با آپارتمان مسکونی.',
            'قبل از مقایسه قیمت، طبقه و دسترسی حمل‌ونقل را بررسی کن.',
        ],
    ),
    'sale_commercial_shop': _base_profile(
        unit_word='مغازه',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[30, 50, 80],
        overview_title='تحلیل کلی فروش مغازه',
        depth_metric_word='قیمت هر متر',
        bands_on='pps',
        show_build_year=False,
        show_residential_amenities=False,
        scenario_range_first=True,
        amenities_section_title='ویژگی‌های تجاری',
        commercial_focus_tips=[
            'در مغازه، پاخور و موقعیت از متراژ مهم‌تر است.',
            'دو مغازه با متراژ یکسان ممکن است چند برابر اختلاف قیمت داشته باشند.',
            'مغازه‌های بر خیابان اصلی معمولاً ارزش بیشتری از واحدهای داخل پاساژ دارند.',
            'قبل از مقایسه قیمت، عرض ویترین و نوع گذر (اصلی/فرعی) را بررسی کن.',
        ],
        specialty_tips=[
            'متری فقط معیار اولیه است — بر ملک، گذر و پاخور تعیین‌کننده‌ترند.',
            'مغازه‌های بر اصلی معمولاً تا ۳۰٪ گران‌تر از میانگین بازار معامله می‌شوند.',
            'مغازه‌های پاساژی را با مغازه‌های خیابانی مقایسه نکن.',
            'فایل‌های زیر قیمت بازار معمولاً سریع‌تر جذب سرمایه‌گذار می‌شوند.',
        ],
    ),
    'sale_commercial_industrial': _base_profile(
        unit_word='ملک صنعتی',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[200, 500, 1000],
        overview_title='تحلیل کلی فروش صنعتی / انبار',
        depth_metric_word='قیمت هر متر',
        bands_on='pps',
        specialty_tips=[
            'در ملک صنعتی، دسترسی کامیون، ارتفاع سوله و کاربری زمین از متری مهم‌تر است.',
        ],
    ),
    # ─── اجاره مسکونی ───
    'rent_residential_apartment': _base_profile(
        unit_word='آپارتمان',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[60, 80, 100],
        overview_title='تحلیل کلی اجاره آپارتمان',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
        specialty_tips=[
            'قبل از بازدید نوع قرارداد را مشخص کن: رهن کامل، رهن+اجاره، یا اجاره خالص.',
            'همه فایل‌ها را با رهن کامل معادل مقایسه کن: رهن + (اجاره × ۳۰).',
        ],
    ),
    'rent_residential_villa': _base_profile(
        unit_word='ویلا',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[150, 200, 250],
        overview_title='تحلیل کلی اجاره ویلا',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
        specialty_tips=[
            'اجاره ویلا معمولاً ترکیب رهن بالا + اجاره پایین است — مبنای مقایسه رهن کامل معادل است.',
            'حیاط، پارکینگ و وضعیت بنا در اجاره ویلا اثر بیشتری از آپارتمان دارد.',
        ],
    ),
    # ─── اجاره اداری / تجاری ───
    'rent_commercial_office': _base_profile(
        unit_word='دفتر',
        scenario_unit_word='دفتر کار',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[40, 60, 90],
        overview_title='تحلیل کلی اجاره اداری',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
        show_build_year=False,
        show_residential_amenities=False,
        amenities_section_title='ویژگی‌های اداری',
        specialty_tips=[
            'در اجاره دفتر، رهن کامل معادل معیار اصلی است — نه فقط رهن یا اجاره خام.',
            'موقعیت، طبقه و پارکینگ اختصاصی در مذاکره اجاره اداری تعیین‌کننده است.',
        ],
    ),
    'rent_commercial_shop': _base_profile(
        unit_word='مغازه',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[25, 40, 60],
        overview_title='تحلیل کلی اجاره مغازه',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
        show_build_year=False,
        show_residential_amenities=False,
        amenities_section_title='ویژگی‌های تجاری',
        commercial_focus_tips=[
            'حق کسب و پیشه و موقعیت گذر را قبل از پیشنهاد به مستأجر چک کن.',
            'پاخور و دید ویترین در اجاره مغازه از متراژ مهم‌تر است.',
        ],
        specialty_tips=[
            'اجاره مغازه را با رهن کامل معادل مقایسه کن — فقط رهن یا اجاره خام گمراه‌کننده است.',
            'حق کسب و پیشه و موقعیت گذر را قبل از پیشنهاد به مستأجر چک کن.',
        ],
    ),
    'rent_commercial_industrial': _base_profile(
        unit_word='ملک صنعتی',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[200, 500, 800],
        overview_title='تحلیل کلی اجاره صنعتی',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
        specialty_tips=[
            'در اجاره انبار/کارگاه، رهن کامل معادل را با فایل‌های هم‌کاربری مقایسه کن.',
        ],
    ),
    # ─── پروژه ───
    'sale_project_project': _base_profile(
        unit_word='واحد پروژه',
        metric_mode='total_price',
        market_value_mode='total',
        sample_areas=[80, 100, 120],
        overview_title='تحلیل کلی پروژه ساخت‌وساز',
        depth_metric_word='قیمت کل واحد',
        bands_on='price',
        specialty_tips=[
            'در پروژه، قیمت کل واحد و متری قرارداد با قیمت تحویل و اقساط را جدا بررسی کن.',
            'اعتبار سازنده، مرحله پیشرفت و زمان تحویل در ارزش‌گذاری پروژه حیاتی است.',
        ],
    ),
    'sale_commercial': _base_profile(
        unit_word='ملک تجاری',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[50, 80, 120],
        overview_title='تحلیل کلی فروش اداری / تجاری',
        depth_metric_word='قیمت هر متر',
        bands_on='pps',
        specialty_tips=['در اداری/تجاری موقعیت مکانی اثر بیشتری از امکانات مسکونی دارد.'],
    ),
    'rent_commercial': _base_profile(
        unit_word='ملک تجاری',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[40, 60, 90],
        overview_title='تحلیل کلی اجاره اداری / تجاری',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
        specialty_tips=['اجاره اداری/تجاری را با رهن کامل معادل مقایسه کن.'],
    ),
    'sale_land': _base_profile(
        unit_word='ملک',
        metric_mode='total_price',
        market_value_mode='total',
        sample_areas=[100, 150, 200],
        overview_title='تحلیل کلی فروش زمین / کلنگی',
        depth_metric_word='قیمت کل',
        bands_on='price',
        specialty_tips=['در زمین و کلنگی قیمت کل مهم‌تر از متری است.'],
    ),
    'sale_residential': _base_profile(
        unit_word='واحد مسکونی',
        metric_mode='pps',
        market_value_mode='pps',
        sample_areas=[80, 100, 120],
        overview_title='تحلیل کلی فروش مسکونی',
        depth_metric_word='قیمت هر متر',
        bands_on='pps',
    ),
    'rent_residential': _base_profile(
        unit_word='واحد مسکونی',
        metric_mode='rent_equiv',
        market_value_mode='rent',
        sample_areas=[60, 80, 100],
        overview_title='تحلیل کلی اجاره مسکونی',
        depth_metric_word='رهن کامل',
        bands_on='full_deposit',
        client_word='مستأجر',
    ),
}

# fallback زنجیره‌ای
FALLBACK_KEYS: Dict[str, List[str]] = {
    'sale_residential_villa': ['sale_villa_villa', 'sale_residential_apartment', 'sale_residential'],
    'sale_villa_villa': ['sale_residential_villa', 'sale_residential'],
    'sale_land_kolongi': ['sale_land'],
    'sale_land_land_plot': ['sale_land'],
    'rent_residential_villa': ['rent_residential_apartment', 'rent_residential'],
    'sale_commercial_shop': ['sale_commercial'],
    'sale_commercial_industrial': ['sale_commercial'],
    'rent_commercial_office': ['rent_commercial'],
    'rent_commercial_industrial': ['rent_commercial'],
}


def resolve_segment_profile(
    deal: str,
    prop: str,
    sub_key: str,
) -> Tuple[str, Dict[str, Any]]:
    """پروفایل تحلیل با fallback — (segment_id, profile)."""
    primary = segment_key(deal, prop, sub_key)
    candidates = [primary]
    candidates.extend(FALLBACK_KEYS.get(primary, []))
    candidates.append(f'{deal}_{prop}')
    candidates.append(f'{deal}_default')
    candidates.append('default')

    seen: set = set()
    for key in candidates:
        if key in seen:
            continue
        seen.add(key)
        if key in SEGMENT_PROFILES:
            profile = dict(SEGMENT_PROFILES[key])
            profile['segment_id'] = primary
            profile['profile_key'] = key
            return primary, profile

    profile = _base_profile(
        unit_word='واحد',
        metric_mode='pps' if deal == 'sale' else 'rent_equiv',
        market_value_mode='pps' if deal == 'sale' else 'rent',
        sample_areas=[80, 100, 120],
        overview_title='تحلیل کلی بازار',
        depth_metric_word='قیمت' if deal == 'sale' else 'رهن کامل',
    )
    profile['segment_id'] = primary
    profile['profile_key'] = 'default'
    return primary, profile


def segment_badge(deal: str, prop: str, sub_key: str, subcategory: str = '') -> str:
    """برچسب فارسی برای هدر گزارش."""
    sub_label = (subcategory or '').strip()
    badges = {
        ('sale', 'residential', 'apartment'): 'فروش آپارتمان',
        ('sale', 'villa', 'villa'): 'فروش ویلا',
        ('rent', 'villa', 'villa'): 'رهن و اجاره ویلا',
        ('sale', 'land', 'kolongi'): 'فروش کلنگی',
        ('sale', 'land', 'land_plot'): 'فروش زمین',
        ('sale', 'commercial', 'office'): 'فروش اداری',
        ('sale', 'commercial', 'shop'): 'فروش مغازه',
        ('sale', 'commercial', 'industrial'): 'فروش صنعتی / انبار',
        ('rent', 'residential', 'apartment'): 'رهن و اجاره آپارتمان',
        ('rent', 'residential', 'villa'): 'رهن و اجاره ویلا',
        ('rent', 'commercial', 'office'): 'رهن و اجاره اداری',
        ('rent', 'commercial', 'shop'): 'رهن و اجاره مغازه',
        ('rent', 'commercial', 'industrial'): 'رهن و اجاره صنعتی',
        ('sale', 'project', 'project'): 'پروژه ساخت‌وساز',
    }
    key = (deal, prop, sub_key)
    if key in badges:
        return badges[key]
    if sub_label:
        tx = 'رهن و اجاره' if deal == 'rent' else 'فروش'
        return f'{tx} {sub_label}'
    generic = {
        'sale': 'فروش',
        'rent': 'رهن و اجاره',
        'mixed': 'فروش و رهن/اجاره',
    }
    prop_fa = {
        'residential': 'مسکونی',
        'villa': 'ویلا',
        'land': 'زمین / کلنگی',
        'commercial': 'اداری / تجاری',
        'project': 'پروژه',
    }
    return f'{generic.get(deal, deal)} {prop_fa.get(prop, prop)}'
