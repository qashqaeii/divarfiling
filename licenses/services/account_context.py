"""خلاصه حساب کاربر و املاک برای کلاینت دسکتاپ — فیلد اختیاری account."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model

from workspace.mixins import get_or_create_settings
from workspace.models import CRMProperty
from workspace.services.crm_scope import get_membership

User = get_user_model()

MAX_ACCOUNT_PROPERTIES = 8


def _display_name(user) -> str:
    full = (user.get_full_name() or "").strip()
    if full:
        return full
    if getattr(user, "phone", None):
        return str(user.phone)
    return user.username or "کاربر"


def _property_price_fields(prop: CRMProperty) -> Dict[str, Any]:
    if prop.deal_mode == "اجاره" or prop.monthly_rent or prop.deposit:
        return {
            "sale_price": None,
            "deposit": prop.deposit,
            "monthly_rent": prop.monthly_rent,
        }
    return {
        "sale_price": prop.sale_price,
        "deposit": None,
        "monthly_rent": None,
    }


def _serialize_property(prop: CRMProperty) -> Dict[str, Any]:
    location_parts = [p for p in (prop.city, prop.district, prop.neighborhood) if p]
    amenities = []
    if prop.has_parking:
        amenities.append("پارکینگ")
    if prop.has_storage:
        amenities.append("انباری")
    if prop.has_elevator:
        amenities.append("آسانسور")
    return {
        "id": prop.pk,
        "title": prop.title or f"ملک #{prop.pk}",
        "deal_mode": prop.deal_mode or "",
        "property_type": prop.property_type or "",
        "transaction_status": prop.transaction_status or "",
        "publish_status": prop.publish_status or "",
        "city": prop.city or "",
        "district": prop.district or "",
        "neighborhood": prop.neighborhood or "",
        "location": " · ".join(location_parts),
        "area": prop.area,
        "rooms": prop.rooms or "",
        "floor": prop.floor,
        "amenities": amenities,
        **_property_price_fields(prop),
    }


def build_license_account_payload(license_obj) -> Dict[str, Any]:
    """ساخت payload اختیاری account — کلاینت‌های قدیمی نادیده می‌گیرند."""
    order = getattr(license_obj, "order", None)
    user = getattr(order, "user", None) if order else None
    if user is None:
        return {}

    try:
        ws = get_or_create_settings(user)
    except Exception:
        ws = None

    profile = getattr(user, "profile", None)
    membership = get_membership(user)
    agency = membership.agency if membership else None

    agency_name = ""
    agency_city = ""
    if agency:
        agency_name = agency.name or ""
    elif ws and ws.agency_name:
        agency_name = ws.agency_name
    if ws and ws.agency_city:
        agency_city = ws.agency_city

    props_qs = (
        CRMProperty.objects.filter(user=user, deleted_at__isnull=True)
        .order_by("-updated_at")
    )
    total_count = props_qs.count()
    sale_count = props_qs.filter(deal_mode="فروش").count()
    rent_count = props_qs.filter(deal_mode="اجاره").count()
    active_count = props_qs.filter(transaction_status="فعال").count()

    properties: List[Dict[str, Any]] = [
        _serialize_property(p)
        for p in props_qs[:MAX_ACCOUNT_PROPERTIES]
    ]

    payload: Dict[str, Any] = {
        "display_name": _display_name(user),
        "phone": getattr(user, "phone", "") or "",
        "email": user.email or "",
        "city": (profile.city if profile else "") or (ws.agency_city if ws else "") or "",
        "agency_name": agency_name,
        "agency_city": agency_city,
        "role": membership.get_role_display() if membership else "",
        "has_profile": bool(
            (profile and (profile.city or profile.address or profile.bio))
            or (ws and (ws.agency_name or ws.agency_address))
            or agency
        ),
        "stats": {
            "total": total_count,
            "sale": sale_count,
            "rent": rent_count,
            "active": active_count,
        },
        "properties": properties,
        "properties_truncated": total_count > len(properties),
    }
    return payload
