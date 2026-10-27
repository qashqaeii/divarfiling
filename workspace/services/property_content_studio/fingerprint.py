"""نگاشت تغییرات ملک برای تشخیص پیش‌نویس قدیمی."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from workspace.models import CRMProperty


def _stable_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def property_content_fingerprint(prop: CRMProperty) -> str:
    """هش از فیلدهای مؤثر روی محتوای تبلیغاتی — بدون یادداشت داخلی."""
    blob = {
        'title': (prop.title or '').strip(),
        'property_type': prop.property_type,
        'deal_mode': prop.deal_mode,
        'area': prop.area,
        'rooms': (prop.rooms or '').strip(),
        'floor': prop.floor,
        'neighborhood': (prop.neighborhood or '').strip(),
        'city': (prop.city or '').strip(),
        'sale_price': prop.sale_price,
        'deposit': prop.deposit,
        'monthly_rent': prop.monthly_rent,
        'has_parking': prop.has_parking,
        'has_storage': prop.has_storage,
        'has_elevator': prop.has_elevator,
        'amenities': (prop.amenities or '').strip()[:500],
        'images': list(prop.images or [])[:12],
        'updated_at': prop.updated_at.isoformat() if prop.updated_at else '',
    }
    raw = _stable_json(blob)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]
