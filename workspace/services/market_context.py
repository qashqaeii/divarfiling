"""زمینه بازار — تشخیص نوع ملک و معامله برای تحلیل مناسب."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from workspace.services.display import transaction_profile
from workspace.services.formatting import format_toman, strip_toman_suffix
from workspace.services.market_segments import (
    detect_property_type,
    normalize_subcategory,
    resolve_segment_profile,
    segment_badge,
)

COMMERCIAL_KEYS = (
    'اداری', 'تجاری', 'دفتر', 'مغازه', 'کارگاه', 'انبار', 'صنعتی',
    'office', 'commercial', 'مطب', 'اتاق اداری',
)
LAND_KEYS = ('کلنگی', 'زمین', 'باغ ویلا', 'باغ‌ویلا', 'عرصه')
VILLA_KEYS = ('ویلا', 'ویلایی')


def detect_market_context(
    dataset_name: str = '',
    subcategory: str = '',
    transaction_type: str = '',
    df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """تشخیص نوع فایل: فروش/اجاره × مسکونی/اداری/کلنگی/ویلا/پروژه."""
    tx = transaction_profile(transaction_type)
    blob = f'{dataset_name} {subcategory}'.lower().replace('_', ' ')

    prop = detect_property_type(dataset_name, subcategory)
    # سازگاری با transaction_type صریح اداری
    if any(k in blob for k in COMMERCIAL_KEYS) or 'اداری' in (transaction_type or '') or 'تجاری' in (transaction_type or ''):
        if 'پروژه' not in blob and 'ساخت' not in blob:
            prop = 'commercial'
    if any(k in blob for k in LAND_KEYS) and prop not in ('commercial', 'project'):
        if not any(k in blob for k in VILLA_KEYS) or 'کلنگی' in blob or 'زمین' in blob:
            prop = 'land'

    if tx['is_rent']:
        deal = 'rent'
    elif tx['is_mixed']:
        deal = 'mixed'
    else:
        deal = 'sale'

    sub_key = normalize_subcategory(dataset_name, subcategory, prop)
    segment_id, segment_profile = resolve_segment_profile(deal, prop, sub_key)

    ctx = _profile(prop, deal, tx, sub_key=sub_key, subcategory=subcategory)
    ctx['prop'] = prop
    ctx['deal'] = deal
    ctx['segment'] = f'{deal}_{prop}'
    ctx['subcategory'] = subcategory
    ctx['subcategory_key'] = sub_key
    ctx['segment_id'] = segment_id
    ctx['segment_profile'] = segment_profile
    ctx['badge'] = segment_badge(deal, prop, sub_key, subcategory)
    for flag in (
        'show_build_year',
        'show_residential_amenities',
        'scenario_range_first',
        'amenities_section_title',
    ):
        if flag in segment_profile:
            ctx[flag] = segment_profile[flag]
    if segment_profile.get('commercial_focus_tips'):
        ctx['commercial_focus_tips'] = segment_profile['commercial_focus_tips']
    return ctx


def build_analysis_header(
    *,
    dataset_name: str = '',
    city: str = '',
    ctx: Dict[str, Any],
    valid_count: int = 0,
    scope_line: str = '',
) -> Dict[str, Any]:
    """متن هدر صفحه تحلیل — نوع معامله و ملک شفاف باشد."""
    deal = ctx.get('deal', 'sale')
    prop = ctx.get('prop', 'residential')
    sub_key = ctx.get('subcategory_key', '')
    subcategory = (ctx.get('subcategory') or '').strip()

    deal_label = {
        'rent': 'رهن و اجاره',
        'sale': 'فروش',
        'mixed': 'فروش و رهن/اجاره',
    }.get(deal, 'بازار')

    sub_labels = {
        'apartment': 'آپارتمان',
        'villa': 'ویلا',
        'office': 'اداری',
        'shop': 'مغازه',
        'industrial': 'صنعتی / انبار',
        'kolongi': 'کلنگی',
        'land_plot': 'زمین',
        'project': 'پروژه',
    }
    prop_labels = {
        'residential': 'مسکونی',
        'commercial': 'تجاری',
        'land': 'زمین / کلنگی',
        'villa': 'ویلا',
        'project': 'پروژه',
    }

    property_label = sub_labels.get(sub_key) or subcategory or prop_labels.get(prop, '')
    analysis_subject = (ctx.get('badge') or f'{deal_label} {property_label}').strip()

    location = (dataset_name or '').strip()
    if ' — ' in location:
        location = location.split(' — ', 1)[0].strip()
    elif ' - ' in location:
        location = location.split(' - ', 1)[0].strip()

    tags: List[Dict[str, str]] = [
        {'text': deal_label, 'tone': 'deal'},
    ]
    if property_label:
        tags.append({'text': property_label, 'tone': 'property'})
    if prop == 'residential' and sub_key == 'apartment':
        tags.append({'text': 'مسکونی', 'tone': 'segment'})
    elif prop_labels.get(prop) and prop_labels[prop] not in property_label:
        tags.append({'text': prop_labels[prop], 'tone': 'segment'})
    if city and city not in (location, dataset_name):
        tags.append({'text': city, 'tone': 'city'})

    title = location or dataset_name or analysis_subject
    headline = f'تحلیل بازار {analysis_subject}'

    if scope_line:
        subtitle = scope_line
    else:
        bits: List[str] = []
        if valid_count:
            bits.append(f'{valid_count:,}'.replace(',', '،') + ' فایل')
        if city:
            bits.append(city)
        subtitle = ' · '.join(bits)

    return {
        'title': title,
        'headline': headline,
        'analysis_subject': analysis_subject,
        'subtitle': subtitle,
        'tags': tags,
        'deal_label': deal_label,
        'property_label': property_label,
        'location': location,
    }


def _profile(
    prop: str,
    deal: str,
    tx: Dict[str, Any],
    *,
    sub_key: str = '',
    subcategory: str = '',
) -> Dict[str, Any]:
    is_rent = deal in ('rent', 'mixed')
    is_sale = deal in ('sale', 'mixed')

    labels = _labels_for(prop, deal, sub_key=sub_key, subcategory=subcategory)

    return {
        'labels': labels,
        'is_rent': is_rent,
        'is_sale': is_sale,
        'show_pps': is_sale and prop not in ('land', 'project'),
        'show_total_price': is_sale,
        'show_deposit': is_rent,
        'show_rent': is_rent,
        'show_rent_per_sqm': False,
        'show_build_year': prop in ('residential', 'villa'),
        'show_residential_amenities': prop == 'residential',
        'scenario_range_first': False,
        'show_amenities': prop in ('residential', 'villa', 'commercial'),
        'show_rooms': prop == 'residential' and sub_key == 'apartment',
        'area_word': (
            'زیربنا' if prop == 'commercial'
            else ('عرصه' if prop in ('land', 'villa') else 'متراژ')
        ),
        'client_word': 'مستأجر' if deal == 'rent' else 'مشتری',
        'opportunity_title': (
            'فرصت‌های برتر اجاره' if deal == 'rent'
            else 'فرصت‌های برتر — کدام فایل‌ها؟'
        ),
    }


def _labels_for(prop: str, deal: str, *, sub_key: str = '', subcategory: str = '') -> Dict[str, str]:
    rent = deal in ('rent', 'mixed')
    commercial = prop == 'commercial'
    land = prop == 'land'

    if rent and not deal == 'mixed':
        rent_labels = {
            'apartment': 'خلاصه بازار اجاره آپارتمان',
            'villa': 'خلاصه بازار اجاره ویلا',
            'office': 'خلاصه بازار اجاره اداری',
            'shop': 'خلاصه بازار اجاره مغازه',
            'industrial': 'خلاصه بازار اجاره صنعتی',
        }
        hero = rent_labels.get(sub_key, 'خلاصه بازار اجاره')
        return {
            'hero_title': hero,
            'metric_primary': 'رهن کامل معادل',
            'metric_primary_hint': 'عدد اصلی مقایسه — رهن + (اجاره × ۳۰)',
            'metric_secondary': 'اجاره ماهانه معمول',
            'metric_secondary_hint': 'اجاره خام ماهانه (بدون لحاظ رهن)',
            'metric_tertiary': 'رهن معمول',
            'metric_tertiary_hint': 'مبلغ رهن رایج در این فایل',
            'price_section': 'رهن و اجاره در این بازار',
            'col_typical': 'مبلغ معمول',
            'col_half_market': 'بیشتر فایل‌ها بین',
            'col_most_market': 'تقریباً همه بین',
            'market_mix': 'وضعیت قیمت فایل‌ها',
            'market_mix_hint': 'ارزون‌تر، سر به سر، یا گرون‌تر از بازار',
            'insights': 'نکات مهم برای اجاره',
            'negotiate': 'راهنمای سریع مشاور (رهن کامل)',
            'segments': 'اجاره به تفکیک متراژ',
            'segments_lead': 'هر متراژ معمولاً چقدر رهن و اجاره می‌خواد',
            'liquidity': 'سرعت اجاره رفتن',
            'confidence': 'اعتماد به این آمار',
            'data_quality': 'تعداد فایل بررسی‌شده',
            'charts': 'نمودار بازار',
            'neighborhoods': 'مقایسه محله‌ها',
            'amenities': 'امکانات رایج در فایل‌ها',
            'build_section': 'وضعیت بنا',
            'data_section': 'جزئیات داده‌ها',
        }

    if commercial:
        comm_labels = {
            'office': 'خلاصه بازار اداری',
            'shop': 'خلاصه بازار مغازه',
            'industrial': 'خلاصه بازار صنعتی / انبار',
        }
        hero = comm_labels.get(sub_key, 'خلاصه بازار اداری / تجاری')
        if deal == 'rent':
            hero = hero.replace('بازار', 'بازار اجاره')
        return {
            'hero_title': hero,
            'metric_primary': 'قیمت هر متر معمول',
            'metric_primary_hint': 'اصلی‌ترین معیار مقایسه دفتر و مغازه',
            'metric_secondary': 'قیمت کل معمول',
            'metric_secondary_hint': 'برای صحبت با مشتری',
            'metric_tertiary': 'اعتماد به گزارش',
            'metric_tertiary_hint': 'بر اساس تعداد و یکدستی فایل‌ها',
            'price_section': 'قیمت دفتر / مغازه',
            'col_typical': 'قیمت معمول',
            'col_half_market': 'بیشتر فایل‌ها بین',
            'col_most_market': 'تقریباً همه بین',
            'market_mix': 'ترکیب قیمت فایل‌ها',
            'market_mix_hint': 'چند فایل زیر بازار، سر به سر، یا بالای بازار',
            'insights': 'نکات کلیدی',
            'negotiate': 'راهنمای مذاکره',
            'segments': 'قیمت به تفکیک زیربنا',
            'segments_lead': 'متراژ رایج و قیمت هر بازه',
            'liquidity': 'سرعت معامله',
            'confidence': 'اعتماد به آمار',
            'data_quality': 'فایل‌های تحلیل‌شده',
            'charts': 'نمودار',
            'neighborhoods': 'مقایسه محله‌ها',
            'amenities': 'امکانات (پارکینگ، آسانسور و …)',
            'build_section': 'سال ساخت',
            'data_section': 'کیفیت داده',
        }

    if land:
        land_labels = {
            'kolongi': 'خلاصه بازار کلنگی',
            'land_plot': 'خلاصه بازار زمین',
        }
        return {
            'hero_title': land_labels.get(sub_key, 'خلاصه بازار کلنگی / زمین'),
            'metric_primary': 'قیمت کل معمول',
            'metric_primary_hint': 'در کلنگی و زمین، قیمت کل مهم‌تر از متریه',
            'metric_secondary': 'متراژ معمول',
            'metric_secondary_hint': 'عرصه یا زیربنا در این فایل',
            'metric_tertiary': 'قیمت هر متر',
            'metric_tertiary_hint': 'فقط برای مقایسه نسبی',
            'price_section': 'قیمت زمین / کلنگی',
            'col_typical': 'قیمت معمول',
            'col_half_market': 'بیشتر فایل‌ها بین',
            'col_most_market': 'تقریباً همه بین',
            'market_mix': 'وضعیت قیمت‌ها',
            'market_mix_hint': 'ارزون، سر به سر، گرون',
            'insights': 'نکات مهم',
            'negotiate': 'نکات مذاکره',
            'segments': 'قیمت به تفکیک متراژ',
            'segments_lead': 'هر اندازه زمین معمولاً چند می‌خوره',
            'liquidity': 'سرعت فروش',
            'confidence': 'اعتماد به آمار',
            'data_quality': 'تعداد فایل',
            'charts': 'نمودار',
            'neighborhoods': 'محله‌ها',
            'amenities': 'امکانات',
            'build_section': 'وضعیت بنا',
            'data_section': 'داده‌ها',
        }

    if prop == 'project':
        return {
            'hero_title': 'خلاصه بازار پروژه ساخت‌وساز',
            'metric_primary': 'قیمت کل واحد معمول',
            'metric_primary_hint': 'در پروژه، قیمت کل قرارداد مهم‌تر از متری است',
            'metric_secondary': 'قیمت هر متر قرارداد',
            'metric_secondary_hint': 'برای مقایسه با بازار مشابه',
            'metric_tertiary': 'اعتماد به گزارش',
            'metric_tertiary_hint': 'بر اساس تعداد فایل و یکدستی داده',
            'price_section': 'قیمت پروژه',
            'col_typical': 'قیمت معمول',
            'col_half_market': 'بیشتر فایل‌ها بین',
            'col_most_market': 'تقریباً همه بین',
            'market_mix': 'وضعیت قیمت واحدها',
            'market_mix_hint': 'زیر بازار، سر به سر، بالای بازار',
            'insights': 'نکات پروژه',
            'negotiate': 'راهنمای مذاکره پروژه',
            'segments': 'قیمت به تفکیک متراژ',
            'segments_lead': 'متراژ رایج واحدها در پروژه',
            'liquidity': 'سرعت فروش',
            'confidence': 'اعتماد به آمار',
            'data_quality': 'فایل‌های تحلیل‌شده',
            'charts': 'نمودار',
            'neighborhoods': 'محله‌ها',
            'amenities': 'امکانات',
            'build_section': 'وضعیت پروژه',
            'data_section': 'کیفیت داده',
        }

    res_labels = {
        'apartment': 'خلاصه بازار فروش آپارتمان',
        'villa': 'خلاصه بازار فروش ویلا',
    }
    # sale residential / villa default
    return {
        'hero_title': res_labels.get(sub_key, 'خلاصه بازار فروش مسکونی'),
        'metric_primary': 'قیمت هر متر معمول',
        'metric_primary_hint': 'مهم‌ترین عدد برای مقایسه آگهی‌ها',
        'metric_secondary': 'قیمت کل معمول',
        'metric_secondary_hint': 'برای واحد با متراژ رایج این فایل',
        'metric_tertiary': 'اعتماد به گزارش',
        'metric_tertiary_hint': 'هرچه فایل بیشتر، عدد دقیق‌تر',
        'price_section': 'قیمت فروش',
        'col_typical': 'قیمت معمول',
        'col_half_market': 'بیشتر فایل‌ها بین',
        'col_most_market': 'تقریباً همه بین',
        'market_mix': 'وضعیت قیمت فایل‌ها',
        'market_mix_hint': 'زیر بازار، سر به سر، بالای بازار',
        'insights': 'نکات مهم',
        'negotiate': 'راهنمای مذاکره',
        'segments': 'قیمت به تفکیک متراژ',
        'segments_lead': 'هر متراژ چند می‌خوره',
        'liquidity': 'سرعت معامله',
        'confidence': 'اعتماد به آمار',
        'data_quality': 'فایل‌های بررسی‌شده',
        'charts': 'نمودار بازار',
        'neighborhoods': 'مقایسه محله‌ها',
        'amenities': 'امکانات رایج',
        'build_section': 'سال ساخت',
        'data_section': 'جزئیات داده',
    }


def build_action_cards(report: Dict[str, Any], ctx: Dict[str, Any]) -> List[Dict[str, str]]:
    """کارهای عملی برای مشاور — با عدد آماده."""
    cards: List[Dict[str, str]] = []
    pa = report.get('price_analysis', {})
    depth = report.get('market_depth', {})
    client = ctx.get('client_word', 'مشتری')
    deal = ctx.get('deal', 'sale')
    prop = ctx.get('prop', 'residential')
    scenarios = report.get('practical_scenarios') or []

    if scenarios and deal != 'rent':
        top = scenarios[0]
        cards.append({
            'title': 'عدد آماده برای مشتری',
            'body': f'{top["title"]}: {top["price"]}. {top.get("body", "")}',
        })

    if deal == 'rent':
        ctx_data = report.get('context') or {}
        unit = (ctx_data.get('segment_profile') or {}).get('unit_word', 'واحد')
        fd = pa.get('full_deposit', {})
        rent = pa.get('rent', {})
        dep = pa.get('deposit', {})
        region = (report.get('neighborhoods') or [{}])[0].get('neighborhood') or report.get('dataset_name', 'این منطقه')
        if len(report.get('neighborhoods') or []) != 1:
            region = report.get('dataset_name', 'این منطقه')

        if dep.get('median_fmt') and rent.get('median_fmt'):
            full_fmt = fd.get('median_fmt', '—')
            cards.append({
                'title': 'عدد آماده برای مشتری',
                'body': (
                    f'واحد معمولی در {region} معمولاً با {dep["median_fmt"]} رهن + '
                    f'{rent["median_fmt"]} اجاره فایل می‌شود '
                    f'(رهن کامل معادل حدود {full_fmt}).'
                ),
            })
        if dep.get('median') and rent.get('median'):
            dep_m = int(dep['median'])
            rent_m = int(rent['median'])
            full = dep_m + rent_m * 30
            cards.append({
                'title': 'رهن کامل معادل',
                'body': (
                    f'رهن کامل این بازار حدود {format_toman(full)} است. '
                    f'محاسبه: {dep.get("median_fmt", "—")} + ({rent.get("median_fmt", "—")} × ۳۰).'
                ),
            })
        if depth.get('under_market'):
            cards.append({
                'title': 'فرصت معرفی',
                'body': (
                    f'{depth["under_market"]} فایل با رهن کامل پایین‌تر از عرف بازار — '
                    f'اول به {client} همین‌ها را نشان بده.'
                ),
            })
    elif prop == 'commercial':
        pps = pa.get('price_per_sqm', {})
        price = pa.get('price', {})
        unit = (report.get('context') or {}).get('segment_profile', {}).get('unit_word', 'واحد')
        sub_key = ctx.get('subcategory_key', '')
        if pps.get('median_fmt'):
            buy_fmt = depth.get('p40_fmt') or pps.get('p25_fmt', '—')
            sell_fmt = depth.get('p60_fmt') or pps.get('p75_fmt', '—')
            fair_lo = strip_toman_suffix(buy_fmt) if buy_fmt != '—' else ''
            fair_hi = strip_toman_suffix(sell_fmt) if sell_fmt != '—' else ''
            body = (
                f'متری مرجع بازار: {pps["median_fmt"]}. '
                f'فرصت خرید: زیر {buy_fmt}. '
            )
            if fair_lo and fair_hi:
                body += f'محدوده متعارف: {fair_lo} تا {fair_hi} تومان/متر. '
            body += f'نیازمند مذاکره: بالای {sell_fmt}.'
            cards.append({'title': 'مبنای مقایسه', 'body': body})
        segs = report.get('area_segments', [])
        if segs:
            top = max(segs, key=lambda s: s['count'])
            bucket = top.get('bucket_plain', '')
            cards.append({
                'title': 'زیربنای پرمعامله بازار',
                'body': (
                    f'بیشترین تعداد فایل‌ها در بازه {bucket} قرار دارند. '
                    f'برای {client} یا سرمایه‌گذار، ابتدا همین بازه را بررسی کنید '
                    f'زیرا بیشترین حجم معاملات بازار در این محدوده شکل می‌گیرد.'
                ),
            })
        if sub_key == 'shop' and price.get('range_50_fmt') and pps.get('median_fmt'):
            profile = (report.get('context') or {}).get('segment_profile') or {}
            area = (profile.get('sample_areas') or [30])[0]
            ref = int((pps.get('median') or 0) * area)
            cards.append({
                'title': 'عدد آماده برای مشتری',
                'body': (
                    f'مغازه {area} متری در این محدوده معمولاً بین {price["range_50_fmt"]} معامله می‌شود. '
                    f'عدد مرجع بازار: حدود {format_toman(ref)} (متری {pps["median_fmt"]}).'
                ),
            })
        if depth.get('over_market'):
            cards.append({
                'title': 'فایل گران',
                'body': f'{depth["over_market"]} فایل بالای بازار — مذاکره یا بررسی موقعیت مکانی.',
            })
    elif prop == 'project':
        price = pa.get('price', {})
        if price.get('median_fmt'):
            cards.append({
                'title': 'قیمت واحد پروژه',
                'body': (
                    f'قیمت کل معمول واحد {price["median_fmt"]}. '
                    f'زمان تحویل و اقساط را جدا از این عدد بررسی کن.'
                ),
            })
    elif prop in ('villa',) and deal == 'sale':
        pps = pa.get('price_per_sqm', {})
        price = pa.get('price', {})
        if pps.get('median_fmt'):
            cards.append({
                'title': 'مبنای مقایسه ویلا',
                'body': f'متری {pps["median_fmt"]} — عرصه و بر را جدا از زیربنا چک کن.',
            })
        if price.get('median_fmt') and depth.get('under_market'):
            cards.append({
                'title': 'زیر بازار',
                'body': f'{depth["under_market"]} فایل زیر قیمت بازار — اول به {client} نشان بده.',
            })
    elif prop == 'land':
        price = pa.get('price', {})
        if price.get('median_fmt'):
            cards.append({
                'title': 'قیمت کل',
                'body': f'قیمت معمول {price["median_fmt"]}. در کلنگی/زمین روی قیمت کل تمرکز کن نه فقط متری.',
            })
    else:
        pps = pa.get('price_per_sqm', {})
        price = pa.get('price', {})
        if pps.get('p25_fmt'):
            cheap = strip_toman_suffix(pps['p25_fmt'])
            cards.append({
                'title': 'قبل از بازدید',
                'body': (
                    f'متری مرجع {pps.get("median_fmt", "—")}. '
                    f'واحدهای زیر {cheap} تومان/متر را اول به {client} پیشنهاد بده.'
                ),
            })
        if price.get('median_fmt'):
            amt = strip_toman_suffix(price['median_fmt'])
            cards.append({
                'title': 'صحبت با مشتری',
                'body': f'بگو قیمت معمول واحد در این منطقه حدود {amt} تومان است — همین عدد، نه میانگین خام.',
            })
        if depth.get('under_market'):
            cards.append({
                'title': 'زیر بازار',
                'body': (
                    f'{depth["under_market"]} فایل زیر قیمت بازار شناسایی شده‌اند. '
                    f'پیشنهاد می‌شود ابتدا همین فایل‌ها به {client} معرفی شوند.'
                ),
            })

    return cards[:4]
