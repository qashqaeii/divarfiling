"""ممیزی read-only موتور تطبیق — بدون PII."""
from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from workspace.models import Customer
from workspace.services.crm_matching import (
    _crm_match_candidates_filtered_qs,
    _crm_match_compatible,
    _divar_match_candidates_filtered_qs,
    _infer_listing_property_type,
    _listing_is_genuine_owner,
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
from workspace.services.crm_matching_retrieval import (
    build_crm_index,
    build_divar_index,
    collect_customer_match_results,
)


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
        is_rent=False,
    ):
        return 'budget_out_of_range'
    return None


def _divar_eligibility_reason(customer: Customer, listing) -> Optional[str]:
    if not _listing_is_genuine_owner(listing):
        return 'not_genuine_owner'
    inferred = _infer_listing_property_type(listing)
    if not _listing_match_compatible(customer, listing):
        if not _profile_property_type_eligible(customer, inferred):
            allowed = _profile_allowed_property_types(customer)
            if allowed and not inferred:
                return 'property_type_unknown'
            return 'property_type_or_deal_incompatible'
        return 'location_or_criteria'
    return None


def audit_customer_matches(
    customer: Customer,
    user,
    *,
    divar_enabled: bool = True,
    dataset_id=None,
    crm_sample_cap: int = 2000,
    divar_sample_cap: int = 2000,
) -> Dict[str, Any]:
    """گزارش مرحله‌ای برای یک مخاطب — read-only."""
    tuning = _match_tuning(customer)
    crm_min = tuning['crm_min_score']
    divar_min = tuning['divar_min_score']

    t0 = time.perf_counter()
    crm_qs = _crm_match_candidates_filtered_qs(customer, user)
    crm_sql = crm_qs.count()
    crm_drop = Counter()
    crm_scores: List[int] = []
    crm_eligible_ids: List[int] = []

    for prop in crm_qs.order_by('pk').iterator(chunk_size=500):
        reason = _crm_eligibility_reason(customer, prop)
        if reason:
            crm_drop[reason] += 1
            continue
        item = _score_crm_property(customer, prop)
        if not item:
            crm_drop['score_pipeline_none'] += 1
            continue
        score = int(item.get('score') or 0)
        crm_scores.append(score)
        if score >= crm_min:
            crm_eligible_ids.append(int(prop.pk))
        else:
            crm_drop['below_min_score'] += 1
        if sum(crm_drop.values()) + len(crm_scores) >= crm_sample_cap:
            break

    divar_sql = 0
    divar_drop = Counter()
    divar_scores: List[int] = []
    divar_eligible_tokens: List[str] = []
    if divar_enabled and not is_builder_customer(customer):
        div_qs = _divar_match_candidates_filtered_qs(customer, user, dataset_id=dataset_id)
        divar_sql = div_qs.count()
        for listing in div_qs.order_by('pk').iterator(chunk_size=500):
            reason = _divar_eligibility_reason(customer, listing)
            if reason:
                divar_drop[reason] += 1
                continue
            item = _score_listing(customer, listing)
            if not item:
                divar_drop['score_pipeline_none'] += 1
                continue
            score = int(item.get('score') or 0)
            divar_scores.append(score)
            if score >= divar_min:
                divar_eligible_tokens.append(str(listing.token or listing.pk))
            else:
                divar_drop['below_min_score'] += 1
            if sum(divar_drop.values()) + len(divar_scores) >= divar_sample_cap:
                break

    index_crm = build_crm_index(customer, user, min_score=crm_min)
    index_divar = (
        build_divar_index(customer, user, min_score=divar_min, dataset_id=dataset_id)
        if divar_enabled and not is_builder_customer(customer)
        else []
    )

    payload = collect_customer_match_results(
        customer,
        user,
        divar_enabled=divar_enabled,
        dataset_id=dataset_id,
        crm_min_score=crm_min,
        divar_min_score=divar_min,
        page_size=1_000_000,
        rebuild_index=True,
    )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return {
        'customer_id': customer.pk,
        'customer_type': customer.customer_type,
        'areas': customer.areas or '',
        'budget_min': customer.budget_min,
        'budget_max': customer.budget_max,
        'crm_sql_candidates': crm_sql,
        'crm_eligible_count': len(crm_eligible_ids),
        'crm_index_count': len(index_crm),
        'crm_display_total': payload.get('crm_total_count'),
        'crm_removed_reasons': dict(crm_drop),
        'crm_score_distribution': _score_histogram(crm_scores),
        'crm_eligible_sample_ids': crm_eligible_ids[:50],
        'divar_sql_candidates': divar_sql,
        'divar_eligible_count': len(divar_eligible_tokens),
        'divar_index_count': len(index_divar),
        'divar_display_total': payload.get('divar_total_count'),
        'divar_removed_reasons': dict(divar_drop),
        'divar_score_distribution': _score_histogram(divar_scores),
        'total_display_count': payload.get('total_count'),
        'min_scores': {'crm': crm_min, 'divar': divar_min},
        'elapsed_ms_cold_sample': elapsed_ms,
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


def compare_match_id_sets(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """مقایسه دو خروجی audit — مثلاً snapshot قبل/بعد."""
    b_crm = set(before.get('crm_eligible_sample_ids') or [])
    a_crm = set(after.get('crm_eligible_sample_ids') or [])
    return {
        'crm_only_before': sorted(b_crm - a_crm),
        'crm_only_after': sorted(a_crm - b_crm),
        'crm_intersection': len(b_crm & a_crm),
        'crm_total_before': before.get('crm_eligible_count'),
        'crm_total_after': after.get('crm_eligible_count'),
        'divar_total_before': before.get('divar_eligible_count'),
        'divar_total_after': after.get('divar_eligible_count'),
    }


def audit_report_json(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, default=str)
