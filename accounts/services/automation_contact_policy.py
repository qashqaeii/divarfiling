"""سیاست مرکزی تماس — جلوگیری از spam چند Rule."""
from __future__ import annotations

from datetime import timedelta
from typing import Tuple

from django.utils import timezone

from accounts.models import ManagementAutomationRecipient, ManagementAutomationRule
from accounts.services.discount_engine import get_discount_policy_config
from accounts.services.growth_suppression import (
    PURPOSE_LICENSE_RENEWAL,
    PURPOSE_RECOVERY,
)

# اولویت بالاتر = عدد بزرگتر
RULE_PRIORITY = {
    'license_expiring_3d': 100,
    'failed_payment_followup': 95,
    'pending_recovery': 90,
    'pending_recovery_discount': 88,
    'expired_renewal_campaign': 85,
    'returning_customer_renewal': 80,
    'sms_balance_low': 70,
    'stale_tickets_alert': 70,
}


def _cooldown_hours() -> int:
    config = get_discount_policy_config()
    global_settings = config.get('global') or {}
    return max(1, int(global_settings.get('marketing_cooldown_hours') or 72))


def _is_transactional_rule(rule: ManagementAutomationRule) -> bool:
    return rule.key in (
        'sms_balance_low',
        'stale_tickets_alert',
        'churn_risk_alert',
        'revenue_drop_alert',
        'sms_failure_alert',
    )


def _purpose_for_rule(rule: ManagementAutomationRule) -> str:
    if rule.key in ('pending_recovery', 'pending_recovery_discount', 'failed_payment_followup'):
        return PURPOSE_RECOVERY
    if rule.key in ('license_expiring_3d', 'expired_renewal_campaign', 'returning_customer_renewal'):
        return PURPOSE_LICENSE_RENEWAL
    return 'marketing'


def check_global_contact_policy(
    rule: ManagementAutomationRule,
    *,
    user_id: int | None,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """
    حداکثر یک پیام بازاریابی/بازیابی (غیر هشدار) در بازه cooldown.
    پیام‌های تراکنشی/هشدار مدیریت مستثنی‌اند.
    """
    if dry_run or not user_id:
        return True, ''
    if _is_transactional_rule(rule):
        return True, ''
    purpose = _purpose_for_rule(rule)
    if purpose in (PURPOSE_RECOVERY, PURPOSE_LICENSE_RENEWAL):
        # همچنان تحت سقف global، مگر Rule با اولویت بالاتر اخیراً ارسال شده باشد
        pass

    since = timezone.now() - timedelta(hours=_cooldown_hours())
    recent = (
        ManagementAutomationRecipient.objects.filter(
            user_id=user_id,
            status=ManagementAutomationRecipient.Status.SENT,
            sent_at__gte=since,
            execution__dry_run=False,
        )
        .select_related('rule', 'execution')
        .order_by('-sent_at')
    )
    for rec in recent[:5]:
        other = rec.rule
        if _is_transactional_rule(other):
            continue
        other_priority = RULE_PRIORITY.get(other.key, 50)
        my_priority = RULE_PRIORITY.get(rule.key, 50)
        if other.pk == rule.pk:
            continue
        if my_priority <= other_priority:
            return False, 'global_cooldown'
    return True, ''
