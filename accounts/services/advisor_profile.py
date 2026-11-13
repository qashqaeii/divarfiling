"""پروفایل حرفه‌ای مشاور — پارس، ذخیره و نمایش."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from accounts.services.divar_places import (
    cities_by_province_for_js,
    city_in_province,
    list_cities_for_province_slug,
    list_provinces_for_select,
    places_config_available,
    province_label,
    resolve_province_slug,
)
from accounts.advisor_profile_catalog import (
    ALLOWED_EXPERTISE,
    ALLOWED_JOB_ROLES,
    ALLOWED_PROPERTY,
    EXPERTISE_AREA_CHOICES,
    EXPERTISE_LABELS,
    IRAN_PROVINCE_CHOICES,
    JOB_ROLE_CHOICES,
    JOB_ROLE_LABELS,
    JOB_ROLES_REQUIRE_AGENCY,
    PROPERTY_LABELS,
    PROPERTY_SPECIALTY_CHOICES,
    PROVINCE_LABELS,
)
from accounts.models import UserProfile

_LIST_SPLIT_RE = re.compile(r'[,\n،;]+')


def _clean_str(value: Optional[str], *, max_len: int = 500) -> str:
    return (value or '').strip()[:max_len]


def parse_tag_list(raw: str, *, max_items: int = 40, max_item_len: int = 120) -> List[str]:
    items: List[str] = []
    seen = set()
    for part in _LIST_SPLIT_RE.split(raw or ''):
        token = part.strip()
        if not token:
            continue
        token = token[:max_item_len]
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(token)
        if len(items) >= max_items:
            break
    return items


def parse_choice_list(values: Sequence[str], allowed: frozenset) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values or []:
        key = (value or '').strip()
        if not key or key not in allowed or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def apply_advisor_profile_from_post(profile: UserProfile, post, *, files=None) -> None:
    province_raw = _clean_str(post.get('activity_province'), max_len=80)
    province_slug = resolve_province_slug(province_raw) if places_config_available() else province_raw
    profile.activity_province = province_slug
    activity_city = _clean_str(post.get('activity_city'), max_len=100)
    if places_config_available() and province_slug and activity_city:
        if not city_in_province(province_slug, activity_city):
            activity_city = ''
    profile.activity_city = activity_city
    profile.city = activity_city or profile.city
    profile.activity_districts = parse_tag_list(post.get('activity_districts', ''))
    profile.activity_neighborhoods = parse_tag_list(post.get('activity_neighborhoods', ''))

    years_raw = _clean_str(post.get('years_experience'), max_len=4)
    years_val: Optional[int] = None
    if years_raw.isdigit():
        years_val = min(int(years_raw), 60)
    profile.years_experience = years_val

    profile.expertise_areas = parse_choice_list(
        post.getlist('expertise_areas') if hasattr(post, 'getlist') else [],
        ALLOWED_EXPERTISE,
    )
    profile.property_specialties = parse_choice_list(
        post.getlist('property_specialties') if hasattr(post, 'getlist') else [],
        ALLOWED_PROPERTY,
    )

    role = _clean_str(post.get('job_role'), max_len=32)
    profile.job_role = role if role in ALLOWED_JOB_ROLES else ''

    profile.office_agency_name = _clean_str(post.get('office_agency_name'), max_len=200)
    profile.office_agency_city = _clean_str(post.get('office_agency_city'), max_len=100)
    profile.office_agency_address = _clean_str(post.get('office_agency_address'), max_len=2000)
    profile.office_agency_phone = _clean_str(post.get('office_agency_phone'), max_len=20)

    if 'bio' in post:
        profile.bio = _clean_str(post.get('bio'), max_len=4000)
    if 'address' in post:
        profile.address = _clean_str(post.get('address'), max_len=2000)


def _list_nonempty(value) -> bool:
    return bool(value) and isinstance(value, (list, tuple)) and len(value) > 0


def activity_scope_complete(profile: Optional[UserProfile]) -> bool:
    if not profile:
        return False
    if not (profile.activity_province or '').strip():
        return False
    if not (profile.activity_city or '').strip():
        return False
    districts = profile.activity_districts or []
    neighborhoods = profile.activity_neighborhoods or []
    return _list_nonempty(districts) or _list_nonempty(neighborhoods)


def years_experience_complete(profile: Optional[UserProfile]) -> bool:
    if not profile:
        return False
    years = profile.years_experience
    return years is not None and years >= 1


def multi_choice_complete(profile: Optional[UserProfile], attr: str) -> bool:
    if not profile:
        return False
    return _list_nonempty(getattr(profile, attr, None) or [])


def job_role_complete(profile: Optional[UserProfile]) -> bool:
    if not profile:
        return False
    role = (profile.job_role or '').strip()
    return bool(role) and role in ALLOWED_JOB_ROLES


def agency_office_complete(profile: Optional[UserProfile]) -> bool:
    if not profile:
        return False
    role = (profile.job_role or '').strip()
    if role not in JOB_ROLES_REQUIRE_AGENCY:
        return True
    return all(
        (
            (profile.office_agency_name or '').strip(),
            (profile.office_agency_city or '').strip(),
            (profile.office_agency_address or '').strip(),
            (profile.office_agency_phone or '').strip(),
        )
    )


def is_advisor_profile_complete(profile: Optional[UserProfile]) -> bool:
    return all(
        (
            activity_scope_complete(profile),
            years_experience_complete(profile),
            multi_choice_complete(profile, 'expertise_areas'),
            multi_choice_complete(profile, 'property_specialties'),
            job_role_complete(profile),
            agency_office_complete(profile),
        )
    )


def join_tags(items: Optional[List[str]]) -> str:
    if not items:
        return ''
    return '، '.join(str(x) for x in items if (x or '').strip())


def label_list(keys: Optional[List[str]], labels_map: Dict[str, str]) -> List[str]:
    if not keys:
        return []
    return [labels_map.get(key, key) for key in keys]


def build_advisor_profile_form_context(profile: Optional[UserProfile]) -> Dict[str, Any]:
    profile = profile or UserProfile()
    role = (profile.job_role or '').strip()
    use_divar_places = places_config_available()
    province_slug = resolve_province_slug(profile.activity_province) if use_divar_places else (profile.activity_province or '')
    province_choices = list_provinces_for_select() if use_divar_places else list(IRAN_PROVINCE_CHOICES)
    city_choices = (
        list_cities_for_province_slug(province_slug) if use_divar_places and province_slug else []
    )
    return {
        'expertise_choices': EXPERTISE_AREA_CHOICES,
        'property_choices': PROPERTY_SPECIALTY_CHOICES,
        'job_role_choices': JOB_ROLE_CHOICES,
        'province_choices': province_choices,
        'city_choices': city_choices,
        'activity_province_slug': province_slug,
        'places_available': use_divar_places,
        'places_cities_by_province': cities_by_province_for_js() if use_divar_places else {},
        'selected_expertise': set(profile.expertise_areas or []),
        'selected_properties': set(profile.property_specialties or []),
        'activity_districts_text': join_tags(profile.activity_districts),
        'activity_neighborhoods_text': join_tags(profile.activity_neighborhoods),
        'job_role_requires_agency': role in JOB_ROLES_REQUIRE_AGENCY,
        'display_job_role': JOB_ROLE_LABELS.get(role, '—') if role else '—',
        'display_province': (
            province_label(profile.activity_province)
            if use_divar_places
            else PROVINCE_LABELS.get(profile.activity_province, profile.activity_province or '—')
        ),
        'display_expertise': '، '.join(label_list(profile.expertise_areas, EXPERTISE_LABELS)) or '—',
        'display_properties': '، '.join(label_list(profile.property_specialties, PROPERTY_LABELS)) or '—',
        'display_districts': join_tags(profile.activity_districts) or '—',
        'display_neighborhoods': join_tags(profile.activity_neighborhoods) or '—',
    }
