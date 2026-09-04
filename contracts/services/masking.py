"""ماسک اطلاعات حساس."""
from __future__ import annotations


def mask_national_id(nid: str) -> str:
    nid = (nid or '').strip()
    if len(nid) < 5:
        return '***'
    return f'{nid[:3]}******{nid[-2:]}'


def mask_phone(phone: str) -> str:
    phone = (phone or '').strip()
    if len(phone) < 6:
        return '***'
    return f'{phone[:4]}***{phone[-4:]}'
