"""ممیزی read-only موتور تطبیق — بدون تغییر کش یا rebuild ایندex."""
from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from workspace.models import Customer
from workspace.services.crm_matching import (
    _crm_match_candidates_filtered_qs,
    _crm_match_compatible,
    _crm_property_is_rent_listing,
    _crm_property_is_sale_listing,
    _divar_match_candidates_filtered_qs,
    _infer_listing_property_type,
    _is_rent_customer,
    _is_rent_profile,
    _listing_is_genuine_owner,
    _listing_is_rent_listing,
    _listing_is_sale_listing,
    _listing_match_compatible,
    _match_tuning,
    _profile_allowed_property_types,
    _profile_area_eligible,
    _profile_budget_eligible,
    _profile_detail_eligible,
    _profile_neighborhood_eligible,
    _profile_property_type_eligible,
    _score_crm_property,
    _score_listing,
    is_builder_customer,
)
from workspace.services.features import extract_listing_features
from workspace.services.crm_matching_geo import listing_matching_district, listing_structured_location_extras
from workspace.services.crm_matching import _parse_int_feature

MATCH_AUDIT_ENGINE_VERSION = '3.2-location-rank-readonly'


def _audit_meta(
    *,
    crm_sample_cap: int,
    divar_sample_cap: int,
) -> Dict[str, Any]:
    cache_backend = settings.CACHES.get('default', {}).get('BACKEND', '')
    return {
        'engine_version': MATCH_AUDIT_ENGINE_VERSION,
        'generated_at': timezone.now().isoformat(),
        'cache_backend_class': cache_backend.rsplit('.', 1)[-1] if cache_backend else '',
        'touches_match_index_cache': False,
        'crm_sample_cap': crm_sample_cap,
        'divar_sample_cap': divar_sample_cap,
    }


def _crm_budget_is_rent(customer: Customer, prop) -> bool:
    is_rent_listing = _crm_property_is_rent_listing(prop)
    is_sale_listing = _crm_property_is_sale_listing(prop)
    rent_customer = _is_rent_profile(customer)
    return is_rent_listing and (rent_customer or not is_sale_listing)


def _crm_eligibility_reason(customer: Customer, prop) -> Optional[str]:
    if not _crm_match_compatible(customer, prop):
        return 'deal_or_status_incompatible'
    if not _profile_property_type_eligible(customer, prop.property_type or ''):
        allowed = _profile_allowed_property_types(customer)
        if allowed and not (prop.property_type or '').strip():
            return 'property_type_unknown'
        return 'property_type_mismatch'
    if not _profile_neighborhood_eligible(
        customer,
        neighborhood=prop.neighborhood or '',
        city=prop.city or '',
        district=prop.district or '',
    ):
        return 'location_hard_filter'
    if not _profile_area_eligible(customer, prop.area):
        return 'area_out_of_range'
    if not _profile_detail_eligible(
        customer,
        rooms=prop.rooms,
        build_year=prop.build_year,
        floor=prop.floor,
        has_parking=prop.has_parking,
        has_storage=prop.has_storage,
        has_elevator=prop.has_elevator,
    ):
        return 'detail_preference'
    if not _profile_budget_eligible(
        customer,
        sale_price=prop.sale_price,
        deposit=prop.deposit,
        rent=prop.monthly_rent,
        is_rent=_crm_budget_is_rent(customer, prop),
    ):
        return 'budget_out_of_range'
    return None


def _divar_eligibility_reason(customer: Customer, listing) -> Optional[str]:
    if not _listing_is_genuine_owner(listing):
        return 'not_genuine_owner'
    if not _listing_match_compatible(customer, listing):
        return 'deal_or_status_incompatible'
    inferred = _infer_listing_property_type(listing)
    if not _profile_property_type_eligible(customer, inferred):
        allowed = _profile_allowed_property_types(customer)
        if allowed and not inferred:
            return 'property_type_unknown'
        return 'property_type_mismatch'

    feats = extract_listing_features(listing)
    listing_floor = _parse_int_feature(feats.get('floor'))
    listing_year = _parse_int_feature(feats.get('build_year'))
    listing_rooms = feats.get('rooms') or listing.rooms
    listing_extras = listing_structured_location_extras(listing)
    listing_district = listing_matching_district(listing)

    if not _profile_neighborhood_eligible(
        customer,
        neighborhood=listing.neighborhood or '',
        city=listing.city or '',
        district=listing_district,
        extra_values=listing_extras,
    ):
        return 'location_hard_filter'
    if not _profile_area_eligible(customer, listing.area):
        return 'area_out_of_range'
    if not _profile_detail_eligible(
        customer,
        rooms=listing_rooms,
        build_year=listing_year,
        floor=listing_floor,
        has_parking=feats.get('parking'),
        has_storage=feats.get('storage'),
        has_elevator=feats.get('elevator'),
    ):
        return 'detail_preference'

    is_rent_listing = _listing_is_rent_listing(listing)
    is_sale_listing = _listing_is_sale_listing(listing)
    rent_customer = _is_rent_profile(customer)
    use_rent_price = is_rent_listing and (rent_customer or not is_sale_listing)
    if not _profile_budget_eligible(
        customer,
        sale_price=listing.price,
        deposit=listing.deposit,
        rent=listing.rent,
        is_rent=use_rent_price,
    ):
        return 'budget_out_of_range'
    return None


def _scan_crm_sample(
    customer: Customer,
    user,
    *,
    min_score: int,
    sample_cap: int,
) -> Dict[str, Any]:
    qs = _crm_match_candidates_filtered_qs(customer, user)
    sql_total = qs.count()
    drop = Counter()
    scores: List[int] = []
    eligible_ids: List[int] = []
    examined = 0

    for prop in qs.order_by('pk').iterator(chunk_size=200):
        examined += 1
        reason = _crm_eligibility_reason(customer, prop)
        if reason:
            drop[reason] += 1
        else:
            item = _score_crm_property(customer, prop)
            if not item:
                drop['score_pipeline_none'] += 1
            else:
                score = int(item.get('score') or 0)
                scores.append(score)
                if score >= min_score:
                    eligible_ids.append(int(prop.pk))
                else:
                    drop['below_min_score'] += 1
        if examined >= sample_cap:
            break

    return {
        'sql_candidates_total': sql_total,
        'rows_examined': examined,
        'sample_complete': examined >= sql_total,
        'removed_reasons_in_sample': dict(drop),
        'score_distribution_in_sample': _score_histogram(scores),
        'eligible_ids_in_sample': eligible_ids,
        'eligible_count_in_sample': len(eligible_ids),
    }


def _scan_divar_sample(
    customer: Customer,
    user,
    *,
    min_score: int,
    sample_cap: int,
    dataset_id=None,
) -> Dict[str, Any]:
    qs = _divar_match_candidates_filtered_qs(customer, user, dataset_id=dataset_id)
    sql_total = qs.count()
    drop = Counter()
    scores: List[int] = []
    eligible_keys: List[str] = []
    examined = 0

    for listing in qs.order_by('pk').iterator(chunk_size=200):
        examined += 1
        reason = _divar_eligibility_reason(customer, listing)
        if reason:
            drop[reason] += 1
        else:
            item = _score_listing(customer, listing)
            if not item:
                drop['score_pipeline_none'] += 1
            else:
                score = int(item.get('score') or 0)
                scores.append(score)
                key = str(listing.token or listing.pk)
                if score >= min_score:
                    eligible_keys.append(key)
                else:
                    drop['below_min_score'] += 1
        if examined >= sample_cap:
            break

    return {
        'sql_candidates_total': sql_total,
        'rows_examined': examined,
        'sample_complete': examined >= sql_total,
        'removed_reasons_in_sample': dict(drop),
        'score_distribution_in_sample': _score_histogram(scores),
        'eligible_tokens_in_sample': eligible_keys,
        'eligible_count_in_sample': len(eligible_keys),
    }


def audit_customer_matches(
    customer: Customer,
    user,
    *,
    divar_enabled: bool = True,
    dataset_id=None,
    crm_sample_cap: int = 500,
    divar_sample_cap: int = 500,
) -> Dict[str, Any]:
    """گزارش نمونه‌ای — read-only، بدون کش."""
    tuning = _match_tuning(customer)
    crm_min = tuning['crm_min_score']
    divar_min = tuning['divar_min_score']

    t0 = time.perf_counter()
    crm_block = _scan_crm_sample(
        customer, user, min_score=crm_min, sample_cap=max(1, int(crm_sample_cap)),
    )
    divar_block: Dict[str, Any] = {
        'sql_candidates_total': 0,
        'rows_examined': 0,
        'sample_complete': True,
        'removed_reasons_in_sample': {},
        'score_distribution_in_sample': {},
        'eligible_tokens_in_sample': [],
        'eligible_count_in_sample': 0,
    }
    if divar_enabled and not is_builder_customer(customer):
        divar_block = _scan_divar_sample(
            customer,
            user,
            min_score=divar_min,
            sample_cap=max(1, int(divar_sample_cap)),
            dataset_id=dataset_id,
        )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    meta = _audit_meta(crm_sample_cap=crm_sample_cap, divar_sample_cap=divar_sample_cap)
    meta['elapsed_ms'] = elapsed_ms
    meta['customer_id'] = customer.pk
    meta['viewer_user_id'] = user.pk

    return {
        'audit_meta': meta,
        'customer_summary': {
            'customer_id': customer.pk,
            'customer_type': customer.customer_type,
            'areas': customer.areas or '',
            'budget_min': customer.budget_min,
            'budget_max': customer.budget_max,
            'is_rent_customer': _is_rent_customer(customer),
        },
        'min_scores': {'crm': crm_min, 'divar': divar_min},
        'crm': crm_block,
        'divar': divar_block,
        'disclaimer': (
            'آمار eligible و دلایل حذف فقط روی نمونه بررسی‌شده است مگر sample_complete=true. '
            'sql_candidates_total تعداد کل پس از prefilter SQL است.'
        ),
    }


def _score_histogram(scores: List[int]) -> Dict[str, int]:
    buckets = Counter()
    for s in scores:
        if s >= 80:
            buckets['80+'] += 1
        elif s >= 60:
            buckets['60-79'] += 1
        elif s >= 40:
            buckets['40-59'] += 1
        elif s >= 25:
            buckets['25-39'] += 1
        else:
            buckets['0-24'] += 1
    return dict(buckets)


def compare_match_snapshots(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """مقایسه دو snapshot — فقط روی نمونه‌های بررسی‌شده در هر طرف."""
    b_crm = before.get('crm') or {}
    a_crm = after.get('crm') or {}
    b_div = before.get('divar') or {}
    a_div = after.get('divar') or {}

    b_ids = set(b_crm.get('eligible_ids_in_sample') or [])
    a_ids = set(a_crm.get('eligible_ids_in_sample') or [])
    b_tok = set(b_div.get('eligible_tokens_in_sample') or [])
    a_tok = set(a_div.get('eligible_tokens_in_sample') or [])

    same_sample_scope = (
        b_crm.get('rows_examined') == a_crm.get('rows_examined')
        and b_crm.get('sql_candidates_total') == a_crm.get('sql_candidates_total')
        and b_crm.get('sample_complete') == a_crm.get('sample_complete')
    )

    return {
        'before_meta': before.get('audit_meta'),
        'after_meta': after.get('audit_meta'),
        'same_crm_sample_scope': same_sample_scope,
        'crm_sql_total_before': b_crm.get('sql_candidates_total'),
        'crm_sql_total_after': a_crm.get('sql_candidates_total'),
        'crm_rows_examined_before': b_crm.get('rows_examined'),
        'crm_rows_examined_after': a_crm.get('rows_examined'),
        'crm_eligible_in_sample_before': b_crm.get('eligible_count_in_sample'),
        'crm_eligible_in_sample_after': a_crm.get('eligible_count_in_sample'),
        'crm_ids_only_in_before_sample': sorted(b_ids - a_ids),
        'crm_ids_only_in_after_sample': sorted(a_ids - b_ids),
        'crm_ids_in_both_samples': len(b_ids & a_ids),
        'divar_eligible_in_sample_before': b_div.get('eligible_count_in_sample'),
        'divar_eligible_in_sample_after': a_div.get('eligible_count_in_sample'),
        'divar_tokens_only_in_before_sample': sorted(b_tok - a_tok),
        'divar_tokens_only_in_after_sample': sorted(a_tok - b_tok),
        'disclaimer': (
            'این diff فقط شناسه‌های واجد شرایط داخل نمونه هر snapshot را مقایسه می‌کند؛ '
            'جایگزین اسکن کامل نیست.'
        ),
    }


def compare_match_id_sets(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """سازگاری با snapshotهای قدیمی (v1)."""
    if before.get('crm') or after.get('crm'):
        return compare_match_snapshots(before, after)
    b_crm = set(before.get('crm_eligible_sample_ids') or [])
    a_crm = set(after.get('crm_eligible_sample_ids') or [])
    return {
        'legacy_v1_compare': True,
        'crm_ids_only_in_before_sample': sorted(b_crm - a_crm),
        'crm_ids_only_in_after_sample': sorted(a_crm - b_crm),
        'disclaimer': 'snapshot قدیمی — فقط زیرمجموعه ۵۰تایی',
    }


def audit_report_json(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, default=str)
