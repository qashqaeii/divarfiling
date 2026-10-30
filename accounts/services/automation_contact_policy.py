"""سیاست مرکزی تماس — جلوگیری از spam چند Rule."""
from __future__ import annotations

from datetime import timedelta
from typing import Tuple

from django.utils import timezone

from accounts.models import ManagementAutomationRecipient, ManagementAutomationRule
from accounts.services.discount_engine import get_discount_policy_config

TRANSACTIONAL_RULE_KEYS = frozenset({
    'sms_balance_low',
    'stale_tickets_alert',
    'churn_risk_alert',
    'revenue_drop_alert',
    'sms_failure_alert',
})


def _cooldown_hours() -> int:
    config = get_discount_policy_config()
    global_settings = config.get('global') or {}
    return max(1, int(global_settings.get('marketing_cooldown_hours') or 72))


def _is_transactional_rule(rule: ManagementAutomationRule) -> bool:
    return rule.key in TRANSACTIONAL_RULE_KEYS


def check_global_contact_policy(
    rule: ManagementAutomationRule,
    *,
    user_id: int | None,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """
    حداکثر یک پیام بازاریابی/بازیابی/تمدید در بازه cooldown (پیش‌فرض ۷۲h).
    هشدارهای مدیریتی مستثنی‌اند.
    """
    if dry_run or not user_id:
        return True, ''
    if _is_transactional_rule(rule):
        return True, ''

    since = timezone.now() - timedelta(hours=_cooldown_hours())
    has_recent = ManagementAutomationRecipient.objects.filter(
        user_id=user_id,
        status=ManagementAutomationRecipient.Status.SENT,
        sent_at__gte=since,
        execution__dry_run=False,
    ).exclude(
        rule__key__in=TRANSACTIONAL_RULE_KEYS,
    ).exists()
    if has_recent:
        return False, 'global_cooldown'
    return True, ''
