"""سرویس خلاصه هوشمند فایل شخصی CRM."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

from workspace.models import CRMProperty, Listing
from workspace.services.analyzer import listings_to_dataframe
from workspace.services.crm import resolve_listing_for_property
from workspace.services.crm_scope import property_for_user
from workspace.services.display import transaction_profile
from workspace.services.formatting import format_toman, full_deposit_equiv
from workspace.services.valuation import compute_expected_values, value_verdict

from ai_workspace.constants import FEATURE_LISTING_SUMMARY
from ai_workspace.context_builders import property_context
from ai_workspace.services.gateway import GatewayResult, run
from ai_workspace.services.listing_summary import generate_summary
from ai_workspace.services.property_context_gate import assess_property_context
from ai_workspace.services.property_summary_skip import PropertySummaryInsufficientContext


def _transaction_type_for_property(prop: CRMProperty) -> str:
    deal_mode = (prop.deal_mode or '').strip()
    if deal_mode == 'فروش':
        return 'فروش'
    if deal_mode in ('رهن و اجاره', 'اجاره'):
        return 'اجاره'
    return deal_mode or 'فروش'


def _property_listing_shim(prop: CRMProperty) -> SimpleNamespace:
    data: Dict[str, Any] = {}
    if prop.floor is not None:
        data['طبقه'] = str(prop.floor)
    if prop.total_floors:
        data['تعداد کل طبقات ساختمان'] = str(prop.total_floors)
    if prop.build_year:
        data['ساخت'] = str(prop.build_year)
    if prop.has_parking:
        data['پارکینگ'] = 'دارد'
    if prop.has_storage:
        data['انباری'] = 'دارد'
    if prop.has_elevator:
        data['آسانسور'] = 'دارد'

    price_per_sqm = None
    if prop.sale_price and prop.area and prop.area > 0:
        price_per_sqm = int(prop.sale_price / prop.area)

    return SimpleNamespace(
        pk=-int(prop.pk),
        token=prop.token or f'crm-{prop.pk}',
        title=prop.title or '',
        price=prop.sale_price,
        deposit=prop.deposit,
        rent=prop.monthly_rent,
        area=prop.area,
        rooms=prop.rooms or '',
        neighborhood=prop.neighborhood or '',
        city=prop.city or '',
        business_type=prop.business_type or '',
        link=prop.link or '',
        published_at=None,
        data=data,
        price_per_sqm=price_per_sqm,
    )


def _comparable_listings(user, prop: CRMProperty) -> List[Listing]:
    qs = Listing.objects.filter(dataset__user=user).select_related('dataset')
    if prop.city:
        city_qs = qs.filter(city=prop.city)
        if city_qs.exists():
            qs = city_qs
    if prop.neighborhood:
        neighborhood_qs = qs.filter(neighborhood=prop.neighborhood)
        if neighborhood_qs.count() >= 4:
            qs = neighborhood_qs
    return list(qs[:5000])


def benchmark_crm_property(user, prop: CRMProperty) -> Dict[str, Any]:
    """مقایسه بازار فایل شخصی — همان منطق benchmark_listing روی فایلینگ کاربر."""
    listings = _comparable_listings(user, prop)
    result: Dict[str, Any] = {'token': prop.token or '', 'title': prop.title or ''}
    if not listings:
        return result

    transaction_type = _transaction_type_for_property(prop)
    tx = transaction_profile(transaction_type)
    shim = _property_listing_shim(prop)
    combined = list(listings) + [shim]
    df = listings_to_dataframe(combined)
    if df.empty:
        return result

    mode = 'rent' if tx['is_rent'] and not tx['show_price_per_sqm'] else 'sale'
    if tx['is_mixed']:
        mode = 'rent' if (prop.monthly_rent or prop.deposit) and not prop.sale_price else 'sale'

    scored = compute_expected_values(df, mode=mode)
    row = scored[scored['listing_id'] == shim.pk]
    if row.empty:
        return result
    r = row.iloc[0]
    score = r.get('value_score')

    if mode == 'rent':
        full_dep = r.get('full_deposit')
        if full_dep is None or (hasattr(full_dep, '__float__') and str(full_dep) == 'nan'):
            full_dep = full_deposit_equiv(prop.deposit, prop.monthly_rent, 30)
        result['metric'] = 'full_deposit'
        result['label'] = 'رهن کامل معادل'
        result['price_per_sqm_fmt'] = format_toman(full_dep) if full_dep else '—'
        med = scored['full_deposit'].median()
        result['market_median_fmt'] = format_toman(med) if med == med else '—'
        if prop.monthly_rent in (0, None) and (prop.deposit or 0) > 0:
            result['note'] = 'رهن کامل — مقایسه بر اساس رهن کامل معادل'
    else:
        pps = shim.price_per_sqm
        result['metric'] = 'price_per_sqm'
        result['label'] = 'قیمت هر متر'
        result['price_per_sqm_fmt'] = format_toman(pps, per_sqm=True) if pps else '—'
        med = scored['price_per_sqm'].median()
        result['market_median_fmt'] = format_toman(med, per_sqm=True) if med == med else '—'

    result['diff_pct'] = score
    result['verdict'] = value_verdict(score)
    if score is not None and score <= -12:
        result['verdict'] = 'زیر بازار — فرصت مناسب برای مشتری'
    elif score is not None and score >= 12:
        result['verdict'] = 'بالای بازار — پیشنهاد مذاکره'
    elif score is not None:
        result['verdict'] = 'در محدوده متعارف بازار (تعدیل‌شده)'
    return result


def _feature_profile_for_property(user, prop: CRMProperty) -> Dict[str, Any]:
    source = resolve_listing_for_property(user, prop)
    if not source:
        return {'has_details': False, 'groups': [], 'core': [], 'detail_count': 0}
    from workspace.services.features import extract_listing_features
    from workspace.services.listing_features import build_listing_feature_profile

    feat = extract_listing_features(source)
    return build_listing_feature_profile(source, feat)


def generate_property_summary(
    user,
    prop: CRMProperty,
    *,
    feature_profile: Dict[str, Any] | None = None,
) -> GatewayResult:
    """خلاصه هوشمند — اگر آگهی منبع در فایلینگ باشد همان مسیر آگهی، وگرنه از داده فایل شخصی."""
    source = resolve_listing_for_property(user, prop)
    if source and source.dataset:
        return generate_summary(user, source.dataset, source)

    profile = feature_profile if feature_profile is not None else _feature_profile_for_property(user, prop)
    assessment = assess_property_context(prop, feature_profile=profile)
    if not assessment.meaningful:
        raise PropertySummaryInsufficientContext(reason=assessment.reason)

    benchmark = benchmark_crm_property(user, prop)
    context = property_context.build(prop, benchmark, feature_profile=profile)
    return run(
        FEATURE_LISTING_SUMMARY,
        user,
        context=context,
        entity_type='crm_property',
        entity_id=str(prop.id),
    )


def build_fallback_for_property(user, prop: CRMProperty) -> Dict[str, Any]:
    """خلاصه ساختاریافته — مدل داخلی سیستم برای فایل شخصی."""
    from ai_workspace.context_builders import property_context
    from ai_workspace.fallbacks.listing_summary import build

    profile = _feature_profile_for_property(user, prop)
    benchmark = benchmark_crm_property(user, prop)
    context = property_context.build(prop, benchmark, feature_profile=profile)
    return build(context)['data']


def build_fallback_for_listing(user, dataset, listing) -> Dict[str, Any]:
    """خلاصه ساختاریافته — مدل داخلی سیستم برای آگهی فایلینگ."""
    from ai_workspace.context_builders import listing_context
    from ai_workspace.fallbacks.listing_summary import build
    from workspace.services.analyzer import benchmark_listing, listings_to_dataframe

    df = listings_to_dataframe(dataset.listings.all())
    benchmark = benchmark_listing(listing, df, dataset.transaction_type) if len(df) else {}
    context = listing_context.build(listing, dataset, benchmark)
    return build(context)['data']


def generate_summary_for_user(user, property_id: int) -> GatewayResult:
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at is not None:
        raise LookupError('property_not_found')
    return generate_property_summary(user, prop)
