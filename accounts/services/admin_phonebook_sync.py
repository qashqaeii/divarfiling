"""همگام‌سازی کاربران سایت با دفترچه تلفن فراز اس‌ام‌اس."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from django.conf import settings
from django.contrib.auth import get_user_model

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.sms.base import SmsConfigurationError, SmsError
from accounts.services.sms.faraz import (
    BULK_PHONEBOOK_LIMIT,
    bulk_upsert_phonebook_contacts,
    get_phonebook_contacts_page,
    iter_phonebook_contacts,
)

User = get_user_model()


class PhonebookSyncError(Exception):
    """خطای همگام‌سازی دفترچه تلفن."""

    def __init__(self, message: str, *, code: str = 'phonebook_sync_error'):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PhonebookSyncStatus:
    ok: bool
    phonebook_id: int
    phonebook_title: str
    site_users_total: int
    site_users_valid: int
    phonebook_total: int
    missing_in_phonebook: int
    extra_in_phonebook: int
    error: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PhonebookSyncResult:
    ok: bool
    phonebook_id: int
    synced: int
    batches: int
    site_users_valid: int
    phonebook_total_before: int
    phonebook_total_after: int
    skipped_invalid: int
    error: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


def phonebook_users_id() -> int:
    return int(getattr(settings, 'FARAZSMS_PHONEBOOK_USERS_ID', 0) or 0)


def _user_display_name(user) -> str:
    parts = [user.first_name or '', user.last_name or '']
    name = ' '.join(part.strip() for part in parts if part and part.strip()).strip()
    return name or (user.username or '').strip() or user.phone


def collect_site_users() -> tuple[list[dict[str, str]], int, int]:
    """
    کاربران سایت با موبایل معتبر.
    خروجی: (لیست آیتم‌های آماده bulk، تعداد کل، تعداد نامعتبر)
    """
    items: list[dict[str, str]] = []
    total = 0
    invalid = 0
    seen: set[str] = set()

    for user in User.objects.only('id', 'phone', 'first_name', 'last_name', 'username').iterator():
        total += 1
        phone = normalize_phone(user.phone or '')
        if not is_valid_iran_mobile(phone):
            invalid += 1
            continue
        if phone in seen:
            continue
        seen.add(phone)
        items.append({
            'prefix': 'man',
            'mobile': phone,
            'name': _user_display_name(user),
        })
    return items, total, invalid


def _phonebook_mobiles(phone_book_id: int) -> set[str]:
    mobiles: set[str] = set()
    for row in iter_phonebook_contacts(phone_book_id=phone_book_id):
        phone = normalize_phone(str(row.get('mobile') or ''))
        if is_valid_iran_mobile(phone):
            mobiles.add(phone)
    return mobiles


def get_phonebook_sync_status(*, phone_book_id: int | None = None) -> PhonebookSyncStatus:
    book_id = phone_book_id or phonebook_users_id()
    if not book_id:
        return PhonebookSyncStatus(
            ok=False,
            phonebook_id=0,
            phonebook_title='کاربران',
            site_users_total=0,
            site_users_valid=0,
            phonebook_total=0,
            missing_in_phonebook=0,
            extra_in_phonebook=0,
            error='شناسه دفترچه تلفن تنظیم نشده است.',
        )

    site_items, site_total, _invalid = collect_site_users()
    site_mobiles = {item['mobile'] for item in site_items}

    try:
        first_page = get_phonebook_contacts_page(phone_book_id=book_id, page=1, limit=1)
        phonebook_total = int(first_page.get('totalItems') or 0)
        phonebook_mobiles = _phonebook_mobiles(book_id)
    except (SmsConfigurationError, SmsError) as exc:
        return PhonebookSyncStatus(
            ok=False,
            phonebook_id=book_id,
            phonebook_title='کاربران',
            site_users_total=site_total,
            site_users_valid=len(site_mobiles),
            phonebook_total=0,
            missing_in_phonebook=len(site_mobiles),
            extra_in_phonebook=0,
            error=exc.message,
        )

    missing = len(site_mobiles - phonebook_mobiles)
    extra = len(phonebook_mobiles - site_mobiles)
    return PhonebookSyncStatus(
        ok=True,
        phonebook_id=book_id,
        phonebook_title='کاربران',
        site_users_total=site_total,
        site_users_valid=len(site_mobiles),
        phonebook_total=phonebook_total,
        missing_in_phonebook=missing,
        extra_in_phonebook=extra,
        error='',
    )


def sync_users_to_phonebook(*, phone_book_id: int | None = None) -> PhonebookSyncResult:
    """کاربران سایت را با bulk-upsert به دفترچه فراز وارد می‌کند."""
    book_id = phone_book_id or phonebook_users_id()
    if not book_id:
        raise PhonebookSyncError(
            'شناسه دفترچه تلفن (FARAZSMS_PHONEBOOK_USERS_ID) تنظیم نشده است.',
            code='phonebook_not_configured',
        )

    site_items, _site_total, skipped_invalid = collect_site_users()
    if not site_items:
        raise PhonebookSyncError(
            'هیچ کاربری با شماره موبایل معتبر برای همگام‌سازی یافت نشد.',
            code='phonebook_no_users',
        )

    try:
        before_page = get_phonebook_contacts_page(phone_book_id=book_id, page=1, limit=1)
        phonebook_total_before = int(before_page.get('totalItems') or 0)
    except (SmsConfigurationError, SmsError) as exc:
        raise PhonebookSyncError(exc.message, code=exc.code) from exc

    synced = 0
    batches = 0
    try:
        for offset in range(0, len(site_items), BULK_PHONEBOOK_LIMIT):
            chunk = site_items[offset:offset + BULK_PHONEBOOK_LIMIT]
            bulk_upsert_phonebook_contacts(phone_book_id=book_id, items=chunk)
            synced += len(chunk)
            batches += 1
    except (SmsConfigurationError, SmsError) as exc:
        raise PhonebookSyncError(exc.message, code=exc.code) from exc

    try:
        after_page = get_phonebook_contacts_page(phone_book_id=book_id, page=1, limit=1)
        phonebook_total_after = int(after_page.get('totalItems') or 0)
    except (SmsConfigurationError, SmsError):
        phonebook_total_after = phonebook_total_before

    return PhonebookSyncResult(
        ok=True,
        phonebook_id=book_id,
        synced=synced,
        batches=batches,
        site_users_valid=len(site_items),
        phonebook_total_before=phonebook_total_before,
        phonebook_total_after=phonebook_total_after,
        skipped_invalid=skipped_invalid,
        error='',
    )
