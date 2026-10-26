"""اعتبارسنجی شماره تماس در Import مخاطبین."""
from __future__ import annotations

import math
import re
from typing import Optional, Tuple

from accounts.phone_utils import (
    extract_iran_mobiles_from_text,
    is_valid_crm_phone,
    normalize_phone,
)

_LETTERS_RE = re.compile(r'[A-Za-z\u0600-\u06FF]')


def coerce_phone_cell(val) -> str:
    """تبدیل سلول Excel/CSV به متن قابل پردازش."""
    if val is None:
        return ''
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return ''
        if val == int(val) and abs(val) < 1e15:
            return str(int(val))
        if abs(val) >= 1e10:
            return format(val, '.0f').strip()
        return str(val).strip()
    if isinstance(val, int):
        return str(val)
    return str(val).strip()


def _parse_one_phone(raw: str, label: str) -> Tuple[str, Optional[str]]:
    if not raw:
        return '', None
    s = coerce_phone_cell(raw)
    if not s:
        return '', None

    norm = normalize_phone(s)
    if is_valid_crm_phone(norm):
        return norm, None

    mobiles = extract_iran_mobiles_from_text(s)
    if len(mobiles) == 1:
        return mobiles[0], None
    if len(mobiles) >= 2:
        return '', f'{label} مبهم است (چند شماره در یک سلول)'

    compact = re.sub(r'[\s\-().]+', '', s)
    if _LETTERS_RE.search(compact):
        return '', f'{label} نامعتبر است'

    if norm and is_valid_crm_phone(norm):
        return norm, None

    digits = re.sub(r'\D', '', norm or s)
    if len(digits) >= 8:
        candidate = normalize_phone(digits)
        if is_valid_crm_phone(candidate):
            return candidate, None

    return '', f'{label} نامعتبر است'


def parse_import_phone_fields(
    phone_raw,
    phone_alt_raw,
) -> Tuple[str, str, Optional[str]]:
    """
    Returns: phone, phone_alt, error_message (فارسی) یا None
    """
    phone, err = _parse_one_phone(coerce_phone_cell(phone_raw) if phone_raw is not None else '', 'تلفن')
    if err:
        return '', '', err

    alt, alt_err = _parse_one_phone(
        coerce_phone_cell(phone_alt_raw) if phone_alt_raw is not None else '',
        'تلفن دوم',
    )
    if alt_err:
        return phone, '', alt_err

    if phone and alt and normalize_phone(phone) == normalize_phone(alt):
        return phone, '', 'تلفن و تلفن دوم یکسان هستند'

    return phone, alt, None
