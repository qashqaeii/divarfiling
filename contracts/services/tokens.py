"""مدیریت امن توکن‌های bearer — فقط hash در DB ذخیره می‌شود."""
from __future__ import annotations

import hashlib
import secrets
from typing import Optional, Tuple

from contracts.models import Contract, ContractAccessToken, ContractInvitation


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def generate_bearer_token() -> Tuple[str, str]:
    """برگرداند (raw_token, token_hash) — raw فقط یک‌بار به کاربر ارسال شود."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def lookup_invitation(raw_token: str) -> Optional[ContractInvitation]:
    if not raw_token:
        return None
    return (
        ContractInvitation.objects.select_related(
            'contract', 'version', 'party', 'witness',
        )
        .filter(token_hash=hash_token(raw_token), is_revoked=False)
        .first()
    )


def lookup_access_token(raw_token: str) -> Optional[ContractAccessToken]:
    if not raw_token:
        return None
    return (
        ContractAccessToken.objects.select_related('contract', 'party', 'witness')
        .filter(token_hash=hash_token(raw_token), is_revoked=False)
        .first()
    )


def lookup_contract_by_verify_token(raw_token: str) -> Optional[Contract]:
    if not raw_token:
        return None
    return Contract.objects.filter(verification_token_hash=hash_token(raw_token)).first()


def lookup_by_hash(model, field_name: str, raw_token: str):
    if not raw_token:
        return None
    return model.objects.filter(**{field_name: hash_token(raw_token), 'is_revoked': False}).first()
