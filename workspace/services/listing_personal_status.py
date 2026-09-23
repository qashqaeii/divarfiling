"""وضعیت «قبلاً به فایل شخصی اضافه شده» برای آگهی‌های فایلینگ."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from django.db import IntegrityError
from django.db.models import OuterRef, Subquery

from workspace.models import CRMProperty
from workspace.services.crm_scope import properties_qs

DIVAR_SOURCE_PLATFORM = 'divar'


def divar_source_identity(token: str) -> Tuple[str, str]:
    """platform + external_id برای آگهی دیوار."""
    return DIVAR_SOURCE_PLATFORM, str(token or '').strip()


def get_crm_property_by_source_identity(
    user,
    platform: str,
    external_id: str,
) -> Optional[CRMProperty]:
    """
    Lookup مطابق unique constraint (user, source_platform, source_external_id).
    بدون فیلتر agency/membership — برای idempotency و recovery پس از IntegrityError.
    """
    platform = str(platform or '').strip()
    external_id = str(external_id or '').strip()
    if not platform or not external_id or user is None:
        return None
    prop = CRMProperty.objects.filter(
        user=user,
        source_platform=platform,
        source_external_id=external_id,
    ).first()
    if prop:
        return prop
    if platform == DIVAR_SOURCE_PLATFORM:
        return CRMProperty.objects.filter(
            user=user,
            token=external_id,
            source_external_id='',
        ).first()
    return None


def is_user_source_listing_integrity_error(exc: BaseException) -> bool:
    """True if IntegrityError matches uniq_crmproperty_user_source_listing."""
    if not isinstance(exc, IntegrityError):
        return False
    chain = exc
    parts = []
    while chain is not None:
        parts.append(str(chain))
        chain = getattr(chain, '__cause__', None)
    blob = ' '.join(parts).lower()
    if 'uniq_crmproperty_user_source_listing' in blob:
        return True
    return (
        'source_external_id' in blob
        and 'source_platform' in blob
        and ('user_id' in blob or 'key (user_id' in blob)
    )


def get_crm_property_by_source(
    user,
    platform: str,
    external_id: str,
) -> Optional[CRMProperty]:
    platform = str(platform or '').strip()
    external_id = str(external_id or '').strip()
    if not platform or not external_id:
        return None
    prop = properties_qs(user).filter(
        source_platform=platform,
        source_external_id=external_id,
    ).first()
    if prop:
        return prop
    # legacy: قبل از migration فقط token پر شده
    if platform == DIVAR_SOURCE_PLATFORM:
        return properties_qs(user).filter(token=external_id).first()
    return None


def personal_property_ids_by_tokens(user, tokens: Iterable[str]) -> Dict[str, int]:
    """bulk lookup: token → CRMProperty.pk (فقط active، per-user)."""
    token_list: List[str] = []
    seen = set()
    for raw in tokens:
        token = str(raw or '').strip()
        if not token or token in seen:
            continue
        seen.add(token)
        token_list.append(token)
    if not token_list:
        return {}

    result: Dict[str, int] = {}
    qs = properties_qs(user).filter(source_platform=DIVAR_SOURCE_PLATFORM)
    for external_id, pk in qs.filter(source_external_id__in=token_list).values_list(
        'source_external_id', 'pk',
    ):
        result[external_id] = pk

    missing = [t for t in token_list if t not in result]
    if missing:
        for token, pk in properties_qs(user).filter(
            token__in=missing,
            source_external_id='',
        ).values_list('token', 'pk'):
            if token and token not in result:
                result[token] = pk
    return result


def annotate_listings_personal_status(qs, user):
    """Annotate Listing queryset with personal_property_id (no N+1)."""
    personal_pk = Subquery(
        properties_qs(user).filter(
            source_platform=DIVAR_SOURCE_PLATFORM,
            source_external_id=OuterRef('token'),
        ).values('pk')[:1],
    )
    legacy_pk = Subquery(
        properties_qs(user).filter(
            token=OuterRef('token'),
            source_external_id='',
        ).values('pk')[:1],
    )
    from django.db.models import Case, IntegerField, Value, When

    return qs.annotate(
        personal_property_id=Case(
            When(token='', then=Value(None)),
            default=personal_pk,
            output_field=IntegerField(null=True),
        ),
        legacy_personal_property_id=Case(
            When(token='', then=Value(None)),
            default=legacy_pk,
            output_field=IntegerField(null=True),
        ),
    )


def personal_status_for_listing(listing) -> Tuple[bool, Optional[int]]:
    """Read annotated fields from a Listing instance."""
    pk = getattr(listing, 'personal_property_id', None)
    if pk is None:
        pk = getattr(listing, 'legacy_personal_property_id', None)
    if pk:
        return True, int(pk)
    return False, None


def personal_status_payload(listing) -> dict:
    added, prop_id = personal_status_for_listing(listing)
    return {
        'is_added_to_personal': added,
        'personal_property_id': prop_id,
    }
