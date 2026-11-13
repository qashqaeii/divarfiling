"""پاداش تکمیل پروفایل تکمیلی — کد تخفیف ۱۰٪ یک‌بار مصرف."""
from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.advisor_profile_catalog import PROFILE_REWARD_FIELD_KEYS
from accounts.models import UserDiscountIssuance, UserProfile
from accounts.services.advisor_profile import (
    activity_scope_complete,
    agency_office_complete,
    is_advisor_profile_complete,
    job_role_complete,
    multi_choice_complete,
    years_experience_complete,
)
from accounts.services.discount_engine import (
    DEFAULT_POLICIES,
    DiscountIssueResult,
    POLICY_PROFILE_COMPLETE,
    _format_expiry,
    _unique_discount_code,
    checkout_link_with_code,
    get_discount_policy_config,
)
from shop.models import DiscountCode, Order

logger = logging.getLogger(__name__)
User = get_user_model()

PROFILE_COMPLETION_FIELDS: Tuple[Tuple[str, str], ...] = PROFILE_REWARD_FIELD_KEYS

PROFILE_REWARD_PERCENT = 10
_AUTO_USERNAME_RE = re.compile(r'^u\d{9,12}$', re.IGNORECASE)
CHECKLIST_ACTION_USER_INFO = 'userInfo'
CHECKLIST_ACTION_VERIFY_PHONE = 'verifyPhone'
CHECKLIST_ACTION_PROFILE = 'profile'


def is_default_phone_username(user) -> bool:
    """نام کاربری خودکار ثبت‌نام (مثلاً u9353556010 از موبایل)."""
    username = (getattr(user, 'username', None) or '').strip()
    if not username:
        return True
    phone = (getattr(user, 'phone', None) or '').strip()
    if phone:
        from accounts.phone_utils import phone_username

        if username.lower() == phone_username(phone).lower():
            return True
    if phone:
        return False
    return bool(_AUTO_USERNAME_RE.fullmatch(username))


def user_has_custom_username(user) -> bool:
    return not is_default_phone_username(user)


def user_phone_is_verified(user) -> bool:
    return bool(getattr(user, 'phone_verified', False))


def _profile_field_done(profile: Optional[UserProfile], field_key: str) -> bool:
    if not profile:
        return False
    if field_key == 'activity_scope':
        return activity_scope_complete(profile)
    if field_key == 'years_experience':
        return years_experience_complete(profile)
    if field_key == 'expertise_areas':
        return multi_choice_complete(profile, 'expertise_areas')
    if field_key == 'property_specialties':
        return multi_choice_complete(profile, 'property_specialties')
    if field_key == 'job_role':
        return job_role_complete(profile)
    if field_key == 'agency_office':
        return agency_office_complete(profile)
    return False


def is_supplementary_profile_complete(profile: Optional[UserProfile]) -> bool:
    return is_advisor_profile_complete(profile)


def is_profile_reward_eligible(user) -> bool:
    if not user_has_custom_username(user):
        return False
    if not user_phone_is_verified(user):
        return False
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None
    return is_supplementary_profile_complete(profile)


def _user_profile(user) -> Optional[UserProfile]:
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.filter(user_id=user.pk).first()


def profile_completion_checklist(user) -> List[Dict[str, Any]]:
    profile = _user_profile(user)
    items: List[Dict[str, Any]] = [
        {
            'key': 'username',
            'label': 'نام کاربری دلخواه',
            'done': user_has_custom_username(user),
            'action': CHECKLIST_ACTION_USER_INFO,
        },
        {
            'key': 'phone_verified',
            'label': 'تأیید موبایل',
            'done': user_phone_is_verified(user),
            'action': CHECKLIST_ACTION_VERIFY_PHONE,
        },
    ]
    for field_key, label in PROFILE_COMPLETION_FIELDS:
        items.append({
            'key': field_key,
            'label': label,
            'done': _profile_field_done(profile, field_key),
            'action': CHECKLIST_ACTION_PROFILE,
        })
    return items


def profile_completion_progress(user) -> Dict[str, Any]:
    checklist = profile_completion_checklist(user)
    missing = [item for item in checklist if not item['done']]
    done_count = sum(1 for item in checklist if item['done'])
    total = len(checklist)
    percent = round(100 * done_count / total) if total else 0
    return {
        'percent': percent,
        'is_complete': not missing,
        'missing': [{'key': i['key'], 'label': i['label']} for i in missing],
        'checklist': checklist,
        'done_count': done_count,
        'total': total,
    }


def _profile_reward_issuance(user) -> Optional[UserDiscountIssuance]:
    return (
        UserDiscountIssuance.objects.filter(
            user=user,
            policy_key=POLICY_PROFILE_COMPLETE,
        )
        .select_related('discount_code')
        .order_by('-issued_at')
        .first()
    )


def is_profile_reward_consumed(discount_code: DiscountCode, user) -> bool:
    if (discount_code.max_uses or 0) > 0 and discount_code.used_count >= discount_code.max_uses:
        return True
    if Order.objects.filter(user=user, discount_code=discount_code, status='paid').exists():
        return True
    is_valid, message = discount_code.is_valid(user=user)
    if not is_valid and 'قبلاً از این کد' in (message or ''):
        return True
    if not is_valid and (discount_code.max_uses or 0) > 0 and discount_code.used_count >= discount_code.max_uses:
        return True
    return False


def issue_profile_completion_discount(user) -> DiscountIssueResult:
    """صدور کد تخفیف تکمیل پروفایل — بدون سقف بازاریابی ۳۰ روزه."""
    user_id = getattr(user, 'pk', None)
    if not user_id:
        return DiscountIssueResult(ok=False, reason='کاربر نامعتبر')

    if not is_profile_reward_eligible(user):
        return DiscountIssueResult(ok=False, reason='profile_incomplete')

    config = get_discount_policy_config()
    policy = config['policies'].get(POLICY_PROFILE_COMPLETE) or DEFAULT_POLICIES.get(
        POLICY_PROFILE_COMPLETE, {}
    )
    if not policy.get('enabled', True):
        return DiscountIssueResult(ok=False, reason='سیاست غیرفعال')

    percent = int(policy.get('percent') or PROFILE_REWARD_PERCENT)
    prefix = (config['global'].get('code_prefix') or 'DF').strip().upper()

    try:
        with transaction.atomic():
            existing = (
                UserDiscountIssuance.objects.select_for_update()
                .filter(user_id=user_id, policy_key=POLICY_PROFILE_COMPLETE)
                .select_related('discount_code')
                .first()
            )
            if existing and existing.discount_code_id:
                dc = existing.discount_code
                if is_profile_reward_consumed(dc, user):
                    return DiscountIssueResult(ok=False, reason='already_used')
                return DiscountIssueResult(
                    ok=True,
                    code=dc.code,
                    discount_code_id=dc.pk,
                    discount_percent=str(int(dc.discount_value)) if dc.discount_type == 'percentage' else '',
                    discount_expiry=_format_expiry(dc.valid_until),
                    checkout_link=checkout_link_with_code(dc.code),
                    reused=True,
                )

            dc = DiscountCode.objects.create(
                code=_unique_discount_code(prefix),
                discount_type='percentage',
                discount_value=Decimal(percent),
                max_uses=1,
                valid_from=timezone.now(),
                valid_until=None,
                is_active=True,
                description=f'auto:{POLICY_PROFILE_COMPLETE}:user:{user_id}',
            )
            UserDiscountIssuance.objects.create(
                user_id=user_id,
                discount_code=dc,
                policy_key=POLICY_PROFILE_COMPLETE,
                source_rule='profile_complete',
                source_type=UserDiscountIssuance.SourceType.MANUAL,
                metadata={'reward': 'profile_completion'},
            )
    except Exception as exc:
        from django.db import IntegrityError

        if isinstance(exc, IntegrityError):
            existing = _profile_reward_issuance(user)
            if existing and existing.discount_code_id:
                dc = existing.discount_code
                if not is_profile_reward_consumed(dc, user):
                    return DiscountIssueResult(
                        ok=True,
                        code=dc.code,
                        discount_code_id=dc.pk,
                        discount_percent=str(int(dc.discount_value)) if dc.discount_type == 'percentage' else '',
                        discount_expiry=_format_expiry(dc.valid_until),
                        checkout_link=checkout_link_with_code(dc.code),
                        reused=True,
                    )
        logger.exception('profile completion discount failed user=%s', user_id)
        return DiscountIssueResult(ok=False, reason=str(exc)[:200])

    return DiscountIssueResult(
        ok=True,
        code=dc.code,
        discount_code_id=dc.pk,
        discount_percent=str(percent),
        checkout_link=checkout_link_with_code(dc.code),
        reused=False,
    )


def ensure_profile_completion_reward(user) -> Optional[DiscountIssueResult]:
    """اگر پروفایل کامل است و کد مصرف‌نشده ندارد، کد صادر می‌کند (idempotent)."""
    if not is_profile_reward_eligible(user):
        return None
    existing = _profile_reward_issuance(user)
    if existing and is_profile_reward_consumed(existing.discount_code, user):
        return None
    result = issue_profile_completion_discount(user)
    return result if result.ok else None


def build_profile_completion_reward_context(user) -> Dict[str, Any]:
    """Context قالب برای بنر پاداش در تب پروفایل."""
    from django.urls import reverse

    progress = profile_completion_progress(user)
    checklist = progress.get('checklist') or profile_completion_checklist(user)
    is_auto_username = is_default_phone_username(user)
    needs_phone_verify = not user_phone_is_verified(user)
    verify_phone_url = reverse('otp_verify_phone')
    issuance = _profile_reward_issuance(user)
    percent_off = PROFILE_REWARD_PERCENT

    if issuance and issuance.discount_code_id:
        if is_profile_reward_consumed(issuance.discount_code, user):
            return {
                'show': False,
                'state': 'consumed',
                'percent_off': percent_off,
                'progress': progress,
                'checklist': checklist,
                'is_auto_username': is_auto_username,
                'needs_phone_verify': needs_phone_verify,
                'verify_phone_url': verify_phone_url,
            }
        dc = issuance.discount_code
        return {
            'show': True,
            'state': 'ready',
            'percent_off': percent_off,
            'progress': progress,
            'checklist': checklist,
            'is_auto_username': False,
            'needs_phone_verify': False,
            'verify_phone_url': verify_phone_url,
            'code': dc.code,
            'checkout_url': checkout_link_with_code(dc.code),
            'expiry_display': _format_expiry(dc.valid_until) if dc.valid_until else '',
        }

    return {
        'show': True,
        'state': 'incomplete',
        'percent_off': percent_off,
        'progress': progress,
        'checklist': checklist,
        'missing_labels': [m['label'] for m in progress['missing']],
        'is_auto_username': is_auto_username,
        'needs_phone_verify': needs_phone_verify,
        'verify_phone_url': verify_phone_url,
        'code': '',
        'checkout_url': '',
        'expiry_display': '',
    }


def reward_payload_for_json(result: DiscountIssueResult) -> Dict[str, str]:
    if not result.ok:
        return {}
    return {
        'code': result.code,
        'discount_percent': result.discount_percent,
        'checkout_url': result.checkout_link,
        'newly_issued': '' if result.reused else '1',
    }
