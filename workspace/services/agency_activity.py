"""رویدادهای کسب‌وکار آژانس — centralized, non-blocking."""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Event types (business only — no page/click tracking)
EVENT_CONTACT_CREATED = 'contact_created'
EVENT_PROPERTY_CREATED = 'personal_property_created'
EVENT_DATASET_CREATED = 'dataset_created'
EVENT_EXTRACTION_COMPLETED = 'extraction_completed'
EVENT_DEAL_CREATED = 'deal_created'
EVENT_DEAL_STAGE_CHANGED = 'deal_stage_changed'
EVENT_FOLLOW_UP = 'follow_up'
EVENT_CALL = 'call'
EVENT_VISIT = 'visit'
EVENT_CONTRACT_CREATED = 'contract_created'
EVENT_LICENSE_ASSIGNED = 'license_assigned'
EVENT_LICENSE_UNASSIGNED = 'license_unassigned'
EVENT_ADVISOR_DATA_EXPORT = 'advisor_data_export'
EVENT_SPACE_ITEM_PUBLISHED = 'space_item_published'

OBJECT_TYPE_LABELS = {
    'customer': 'مخاطب',
    'customer_activity': 'مخاطب',
    'property': 'فایل',
    'property_visit': 'بازدید ملک',
    'deal': 'معامله',
    'deal_followup': 'معامله',
    'contract': 'قرارداد',
    'dataset': 'فایلینگ',
}


def object_type_label(object_type: str) -> str:
    key = (object_type or '').strip().lower()
    if not key:
        return ''
    return OBJECT_TYPE_LABELS.get(key, '')


EVENT_TYPE_LABELS = {
    EVENT_CONTACT_CREATED: 'مخاطب جدید',
    EVENT_PROPERTY_CREATED: 'فایل شخصی جدید',
    EVENT_DATASET_CREATED: 'فایلینگ جدید',
    EVENT_EXTRACTION_COMPLETED: 'استخراج تکمیل شد',
    EVENT_DEAL_CREATED: 'معامله جدید',
    EVENT_DEAL_STAGE_CHANGED: 'تغییر مرحله معامله',
    EVENT_FOLLOW_UP: 'پیگیری مشتری',
    EVENT_CALL: 'تماس با مشتری',
    EVENT_VISIT: 'بازدید ملک',
    EVENT_CONTRACT_CREATED: 'قرارداد جدید',
    EVENT_LICENSE_ASSIGNED: 'تخصیص لایسنس',
    EVENT_LICENSE_UNASSIGNED: 'لغو لایسنس',
    EVENT_ADVISOR_DATA_EXPORT: 'خروجی داده مشاور',
    EVENT_SPACE_ITEM_PUBLISHED: 'انتشار در فضای آژانس',
}


def event_type_label(event_type: str) -> str:
    key = (event_type or '').strip()
    if not key:
        return 'رویداد'
    return EVENT_TYPE_LABELS.get(key, key.replace('_', ' '))


def emit_agency_activity(
    agency,
    actor,
    event_type: str,
    *,
    object_type: str = '',
    object_id: int | None = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """ثبت رویداد — هرگز عملیات اصلی را fail نمی‌کند."""
    if not agency or not actor or not event_type:
        return
    try:
        from workspace.models import AgencyActivityEvent
        AgencyActivityEvent.objects.create(
            agency=agency,
            actor=actor,
            event_type=event_type,
            object_type=object_type or '',
            object_id=object_id,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception(
            'agency activity emit failed type=%s agency=%s',
            event_type,
            getattr(agency, 'pk', None),
        )


def emit_for_user_record(user, event_type: str, **kwargs) -> None:
    """اگر user عضو آژانس است، رویداد ثبت شود."""
    if not user:
        return
    try:
        from workspace.models import CRMAgencyMember
        membership = (
            CRMAgencyMember.objects.filter(user=user, is_active=True)
            .select_related('agency')
            .first()
        )
        if membership and membership.agency_id:
            emit_agency_activity(membership.agency, user, event_type, **kwargs)
    except Exception:
        logger.exception('agency activity emit_for_user_record failed')
