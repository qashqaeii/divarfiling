"""وضعیت عملیاتی پایدار خطوط استخراج — همگام با phone-detector و worker."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from accounts.models import AcquisitionRun, PhoneDetectorExtractionLine
from accounts.services.phone_detector_lines import (
    PhoneDetectorLineError,
    _load_index,
    resolve_phone_detector_dir,
    sessions_root,
)

logger = logging.getLogger(__name__)

OPS = PhoneDetectorExtractionLine.OperationalStatus
BLOCK = PhoneDetectorExtractionLine.BlockScope

_PHONE_RE = re.compile(r'^09\d{9}$')


def normalize_line_phone(phone: str) -> str:
    raw = (phone or '').strip().replace(' ', '').replace('-', '')
    if raw.startswith('+98'):
        raw = '0' + raw[3:]
    return raw


def _sessions_index_phones() -> list[str]:
    pd = resolve_phone_detector_dir()
    if not pd:
        return []
    try:
        root = sessions_root()
    except PhoneDetectorLineError:
        return []
    index = _load_index(root)
    return [normalize_line_phone(p) for p in index.get('phones') or [] if normalize_line_phone(p)]


def recover_stale_running_lines() -> int:
    """پس از crash worker، خطوط RUNNING را آزاد کن اگر اجرای فعالی نیست."""
    active = AcquisitionRun.objects.filter(
        status__in=(
            AcquisitionRun.Status.QUEUED,
            AcquisitionRun.Status.RUNNING,
        ),
    ).exists()
    if active:
        return 0
    return PhoneDetectorExtractionLine.objects.filter(
        operational_status=OPS.RUNNING,
    ).update(
        operational_status=OPS.ACTIVE,
        status_detail='آزادسازی خودکار پس از توقف worker',
        updated_at=timezone.now(),
    )


def _expire_cooldown_lines() -> None:
    now = timezone.now()
    PhoneDetectorExtractionLine.objects.filter(
        operational_status=OPS.COOLDOWN,
        blocked_until__lte=now,
    ).update(
        operational_status=OPS.ACTIVE,
        blocked_until=None,
        status_detail='پایان دوره استراحت — آماده انتخاب',
        updated_at=now,
    )


@transaction.atomic
def sync_lines_from_sessions() -> int:
    """ردیف DB را با فایل‌های sessions همگام کن."""
    recover_stale_running_lines()
    _expire_cooldown_lines()

    phones = _sessions_index_phones()
    existing = {
        normalize_line_phone(row.phone): row
        for row in PhoneDetectorExtractionLine.objects.all()
    }
    touched = 0
    for idx, phone in enumerate(phones, start=1):
        if not _PHONE_RE.match(phone):
            continue
        row = existing.get(phone)
        if row is None:
            PhoneDetectorExtractionLine.objects.create(
                phone=phone,
                line_index=idx,
                operational_status=OPS.ACTIVE,
            )
            touched += 1
        elif row.line_index != idx:
            row.line_index = idx
            row.save(update_fields=['line_index', 'updated_at'])
            touched += 1
    return touched


def schedulable_lines_qs():
    sync_lines_from_sessions()
    now = timezone.now()
    return PhoneDetectorExtractionLine.objects.filter(
        Q(operational_status=OPS.ACTIVE)
        | Q(
            operational_status=OPS.COOLDOWN,
            blocked_until__isnull=True,
        )
        | Q(
            operational_status=OPS.COOLDOWN,
            blocked_until__lte=now,
        ),
    )


def count_schedulable_lines() -> int:
    return schedulable_lines_qs().count()


def excluded_phones_for_extraction() -> set[str]:
    """خطوطی که نباید در rotation این اجرا شرکت کنند."""
    sync_lines_from_sessions()
    now = timezone.now()
    phones: set[str] = set()
    for row in PhoneDetectorExtractionLine.objects.all():
        if row.operational_status in (
            OPS.BLOCKED_CAPTCHA,
            OPS.PAUSED,
            OPS.ERROR,
            OPS.RUNNING,
        ):
            phones.add(row.phone)
        elif row.operational_status == OPS.COOLDOWN:
            if row.blocked_until and row.blocked_until > now:
                phones.add(row.phone)
    return phones


def line_label(phone: str) -> str:
    phone = normalize_line_phone(phone)
    row = PhoneDetectorExtractionLine.objects.filter(phone=phone).first()
    if row and row.line_index:
        return f'خط استخراج شماره {row.line_index}'
    return f'خط {phone[-4:]}'


@transaction.atomic
def mark_lines_run_started(*, run_id: int) -> None:
    sync_lines_from_sessions()
    schedulable = list(schedulable_lines_qs().select_for_update())
    now = timezone.now()
    for row in schedulable:
        row.operational_status = OPS.RUNNING
        row.last_run_id = run_id
        row.status_detail = f'در حال استفاده در اجرای #{run_id}'
        row.updated_at = now
        row.save(
            update_fields=[
                'operational_status',
                'last_run_id',
                'status_detail',
                'updated_at',
            ],
        )


def _is_captcha_hip(hip_status: Optional[str]) -> bool:
    if not hip_status:
        return False
    hip = str(hip_status).lower()
    if hip in ('captcha_blocked', 'captcha_skipped'):
        return True
    return hip.startswith('captcha')


def _infer_block_scope(account: dict) -> str:
    if account.get('shared_block'):
        return BLOCK.SHARED_IP
    return BLOCK.LINE


@transaction.atomic
def apply_run_outcome_from_engine(
    *,
    run_id: int,
    accounts: list[dict],
    hip: dict,
    phones_extracted: int,
    worker_status: str,
) -> dict[str, Any]:
    """پس از worker، وضعیت خطوط را از deck_state به‌روز کن."""
    sync_lines_from_sessions()
    now = timezone.now()
    by_phone = {
        normalize_line_phone(a.get('phone') or ''): a
        for a in accounts
        if normalize_line_phone(a.get('phone') or '')
    }

    blocked_this_run: list[str] = []
    healthy_remaining = 0
    used_success: list[str] = []

    for phone, acc in by_phone.items():
        row = (
            PhoneDetectorExtractionLine.objects.select_for_update()
            .filter(phone=phone)
            .first()
        )
        if not row:
            row = PhoneDetectorExtractionLine.objects.create(phone=phone)

        if acc.get('hip_blocked') or _is_captcha_hip(acc.get('last_hip_status')):
            blocked_this_run.append(phone)
            row.operational_status = OPS.BLOCKED_CAPTCHA
            row.block_scope = _infer_block_scope(acc)
            row.last_error_at = now
            row.last_error_reason = 'محدودیت کپچا/HIP دیوار'
            row.error_count = (row.error_count or 0) + 1
            row.status_detail = (
                f'محدودیت کپچا — از چرخه اتوماسیون خارج شد (اجرای #{run_id})'
            )
            row.last_checked_at = now
            row.last_run_id = run_id
            row.save()
            continue

        if acc.get('needs_relogin') or acc.get('ok') is False:
            row.operational_status = OPS.ERROR
            row.last_error_at = now
            row.last_error_reason = 'نشست منقضی — نیاز به ورود مجدد'
            row.error_count = (row.error_count or 0) + 1
            row.status_detail = 'ورود مجدد OTP لازم است'
            row.last_checked_at = now
            row.last_run_id = run_id
            row.save()
            continue

        if row.operational_status == OPS.PAUSED:
            continue

        if row.operational_status in (OPS.RUNNING, OPS.BLOCKED_CAPTCHA, OPS.ERROR):
            row.operational_status = OPS.ACTIVE
            row.status_detail = 'آماده استخراج'
            row.last_checked_at = now
            row.save()

        if row.operational_status == OPS.ACTIVE:
            healthy_remaining += 1
            if phones_extracted > 0:
                used_success.append(phone)

    PhoneDetectorExtractionLine.objects.filter(
        operational_status=OPS.RUNNING,
        last_run_id=run_id,
    ).exclude(phone__in=by_phone.keys()).update(
        operational_status=OPS.ACTIVE,
        status_detail='پایان اجرا — بدون استفاده مستقیم',
        updated_at=now,
    )

    if used_success:
        PhoneDetectorExtractionLine.objects.filter(phone__in=used_success).update(
            last_success_at=now,
            success_extract_count=F('success_extract_count') + 1,
            updated_at=now,
        )

    schedulable = count_schedulable_lines()
    all_blocked = schedulable == 0 and bool(by_phone)
    return {
        'blocked_lines': blocked_this_run,
        'blocked_labels': [line_label(p) for p in blocked_this_run],
        'healthy_lines_remaining': max(healthy_remaining, schedulable),
        'all_lines_blocked': all_blocked,
        'captcha_triggered': int(hip.get('captcha_triggered') or 0),
    }


def build_run_summary_message(
    *,
    outcome: dict[str, Any],
    phones_extracted: int,
    worker_status: str,
) -> str:
    blocked_labels = outcome.get('blocked_labels') or []
    healthy = int(outcome.get('healthy_lines_remaining') or 0)
    all_blocked = bool(outcome.get('all_lines_blocked'))

    if all_blocked:
        return (
            'تمام خطوط استخراج در حال حاضر غیرفعال یا محدود هستند. '
            'جمع‌آوری تا زمان آماده‌شدن خط سالم متوقف شده است.'
        )

    if blocked_labels and worker_status in ('rate_limited', 'completed'):
        joined = '، '.join(blocked_labels)
        if phones_extracted > 0:
            return (
                f'{joined} به محدودیت کپچا برخورد کرد و موقتاً از چرخه خارج شد. '
                f'جمع‌آوری با خطوط سالم ادامه یافت — '
                f'{phones_extracted} شماره استخراج شد.'
            )
        if healthy > 0:
            return (
                f'{joined} به محدودیت کپچا برخورد کرد و موقتاً از چرخه خارج شد. '
                'جمع‌آوری با خطوط سالم ادامه دارد.'
            )

    if worker_status == 'rate_limited' and phones_extracted > 0:
        return f'محدودیت جزئی — {phones_extracted} شماره قبل از توقف ذخیره شد.'

    return ''


def merge_operational_fields(row: dict[str, Any]) -> dict[str, Any]:
    phone = normalize_line_phone(row.get('phone') or '')
    db = PhoneDetectorExtractionLine.objects.filter(phone=phone).first()
    if not db:
        row['operational_status'] = OPS.ACTIVE
        row['operational_status_label'] = 'فعال'
        row['line_index'] = row.get('line_index') or 0
        return row

    status = db.operational_status
    labels = dict(OPS.choices)
    row['line_index'] = db.line_index
    row['operational_status'] = status
    row['operational_status_label'] = labels.get(status, status)
    row['last_success_at'] = db.last_success_at.isoformat() if db.last_success_at else None
    row['last_error_at'] = db.last_error_at.isoformat() if db.last_error_at else None
    row['last_error_reason'] = db.last_error_reason or ''
    row['error_count'] = db.error_count
    row['success_extract_count'] = db.success_extract_count
    row['status_detail'] = db.status_detail or ''
    row['block_scope'] = db.block_scope or ''
    row['last_checked_at'] = db.last_checked_at.isoformat() if db.last_checked_at else None
    row['admin_paused'] = status == OPS.PAUSED
    row['captcha_blocked'] = status == OPS.BLOCKED_CAPTCHA

    if status == OPS.BLOCKED_CAPTCHA:
        row['status'] = 'blocked_captcha'
        row['status_label'] = 'محدودیت کپچا'
        row['ok'] = False
        row['hip_blocked'] = True
    elif status == OPS.PAUSED:
        row['status'] = 'paused'
        row['status_label'] = 'متوقف توسط مدیر'
        row['in_rotation'] = False
    elif status == OPS.RUNNING:
        row['status'] = 'running'
        row['status_label'] = 'در حال استخراج'
    return row


def set_line_paused(phone: str, *, paused: bool) -> PhoneDetectorExtractionLine:
    phone = normalize_line_phone(phone)
    sync_lines_from_sessions()
    row = PhoneDetectorExtractionLine.objects.filter(phone=phone).first()
    if not row:
        raise PhoneDetectorLineError('خط یافت نشد.', code='line_not_found')
    now = timezone.now()
    if paused:
        row.operational_status = OPS.PAUSED
        row.status_detail = 'متوقف توسط مدیر — در زمان‌بندی انتخاب نمی‌شود'
    else:
        row.operational_status = OPS.ACTIVE
        row.status_detail = 'فعال‌سازی توسط مدیر'
    row.last_checked_at = now
    row.save()
    return row


def probe_and_reactivate_line(phone: str) -> dict[str, Any]:
    """بررسی واقعی سشن قبل از بازگرداندن خط به چرخه."""
    from accounts.services.phone_detector_lines import _get_engine, list_lines

    phone = normalize_line_phone(phone)
    sync_lines_from_sessions()
    row = PhoneDetectorExtractionLine.objects.filter(phone=phone).first()
    if not row:
        raise PhoneDetectorLineError('خط یافت نشد.', code='line_not_found')
    if row.operational_status == OPS.PAUSED:
        raise PhoneDetectorLineError(
            'خط توسط مدیر متوقف شده — ابتدا «فعال‌سازی» را بزنید.',
            code='line_paused',
        )

    now = timezone.now()
    row.last_checked_at = now
    try:
        engine = _get_engine()
        info = engine.list_accounts()
    except Exception as exc:
        row.status_detail = f'بررسی ناموفق: {exc}'
        row.save(update_fields=['last_checked_at', 'status_detail', 'updated_at'])
        raise PhoneDetectorLineError(
            f'بررسی وضعیت ممکن نشد: {exc}',
            code='probe_failed',
        ) from exc

    acc = next(
        (
            a
            for a in info.get('accounts') or []
            if normalize_line_phone(a.get('phone') or '') == phone
        ),
        None,
    )
    if not acc:
        row.status_detail = 'حساب در engine یافت نشد'
        row.save(update_fields=['last_checked_at', 'status_detail', 'updated_at'])
        raise PhoneDetectorLineError('خط در phone-detector یافت نشد.', code='line_missing')

    if acc.get('hip_blocked'):
        slot = engine.accounts.get(phone)
        if slot:
            slot.hip_blocked = False
            slot.consecutive_hip = 0
            engine.scraper.reset_hip_gate()
            if engine._ensure_slot_fresh(slot):
                info = engine.list_accounts()
                acc = next(
                    (
                        a
                        for a in info.get('accounts') or []
                        if normalize_line_phone(a.get('phone') or '') == phone
                    ),
                    acc,
                )
        if acc.get('hip_blocked'):
            row.operational_status = OPS.BLOCKED_CAPTCHA
            row.last_error_at = now
            row.last_error_reason = 'هنوز محدودیت کپچا/HIP فعال است'
            row.status_detail = 'بررسی شد — محدودیت هنوز برقرار است'
            row.save()
            raise PhoneDetectorLineError(
                'محدودیت کپچا هنوز برقرار است — بعداً دوباره بررسی کنید.',
                code='still_blocked',
            )

    if acc.get('needs_relogin') or not acc.get('ok'):
        row.operational_status = OPS.ERROR
        row.last_error_at = now
        row.last_error_reason = 'نشست نامعتبر — ورود مجدد لازم'
        row.status_detail = 'بررسی شد — نیاز به OTP'
        row.save()
        raise PhoneDetectorLineError(
            'نشست معتبر نیست — «ورود مجدد» را انجام دهید.',
            code='needs_relogin',
        )

    row.operational_status = OPS.ACTIVE
    row.block_scope = ''
    row.blocked_until = None
    row.last_error_reason = ''
    row.status_detail = 'بررسی موفق — خط به چرخه بازگشت'
    row.save()

    payload = list_lines(probe=True)
    return {
        'reactivated': True,
        'phone': phone,
        'message': 'خط پس از بررسی فعال شد.',
        **payload,
    }


def operational_summary() -> dict[str, Any]:
    sync_lines_from_sessions()
    total = PhoneDetectorExtractionLine.objects.count()
    schedulable = count_schedulable_lines()
    blocked = PhoneDetectorExtractionLine.objects.filter(
        operational_status=OPS.BLOCKED_CAPTCHA,
    ).count()
    paused = PhoneDetectorExtractionLine.objects.filter(
        operational_status=OPS.PAUSED,
    ).count()
    return {
        'total_lines': total,
        'schedulable_lines': schedulable,
        'blocked_captcha_lines': blocked,
        'paused_lines': paused,
        'waiting_for_healthy_line': total > 0 and schedulable == 0,
    }
