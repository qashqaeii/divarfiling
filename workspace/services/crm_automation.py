"""اتوماسیون CRM — قوانین خودکار."""
from __future__ import annotations

from datetime import timedelta
from typing import List, Tuple

from django.db.models import Max
from django.utils import timezone

from workspace.constants import CRM_STATUSES
from workspace.models import CRMAutomationRule, Customer, CustomerActivity, Reminder
from workspace.services.crm import log_activity, update_customer_status


def ensure_default_rules(user) -> None:
    if CRMAutomationRule.objects.filter(user=user).exists():
        return
    CRMAutomationRule.objects.create(
        user=user,
        name='پیگیری پس از ۳ روز سکون',
        trigger='inactive_days',
        trigger_days=3,
        trigger_statuses='جدید,در حال پیگیری',
        action='create_reminder',
        action_reminder_title='پیگیری — بدون فعالیت اخیر',
        action_reminder_days=0,
    )


def _customer_last_touch(customer: Customer):
    last_act = (
        CustomerActivity.objects.filter(customer=customer)
        .aggregate(m=Max('created_at'))['m']
    )
    candidates = [customer.updated_at, customer.created_at]
    if last_act:
        candidates.append(last_act)
    return max(c for c in candidates if c)


def _inactive_customers(user, days: int, statuses: List[str]):
    cutoff = timezone.now() - timedelta(days=days)
    qs = Customer.objects.filter(user=user, status__in=statuses)
    for c in qs.iterator():
        if _customer_last_touch(c) < cutoff:
            yield c


def _has_open_automation_reminder(user, customer: Customer, title: str) -> bool:
    return Reminder.objects.filter(
        user=user, customer=customer, is_done=False, title=title,
    ).exists()


def apply_rule(rule: CRMAutomationRule, customer: Customer) -> bool:
    """اعمال قانون روی یک مخاطب. True اگر تغییری ایجاد شد."""
    if rule.trigger != 'inactive_days':
        return False

    if rule.action == 'set_status' and rule.action_status in CRM_STATUSES:
        old = customer.status
        update_customer_status(customer, rule.action_status, user=rule.user)
        log_activity(
            customer, 'وظیفه',
            content=f'قانون «{rule.name}»: وضعیت به «{rule.action_status}» تغییر کرد.',
            title='اتوماسیون',
        )
        return old != customer.status

    if rule.action == 'create_reminder':
        title = rule.action_reminder_title or 'پیگیری خودکار'
        if _has_open_automation_reminder(rule.user, customer, title):
            return False
        due = timezone.now() + timedelta(days=rule.action_reminder_days)
        Reminder.objects.create(
            user=rule.user,
            customer=customer,
            title=title,
            note=f'ایجاد خودکار توسط قانون: {rule.name}',
            due_at=due,
        )
        log_activity(
            customer, 'یادآور',
            content=f'یادآور «{title}» توسط اتوماسیون ایجاد شد.',
            title='اتوماسیون',
        )
        return True

    return False


def run_automation_for_user(user, *, min_interval_hours: int = 1) -> Tuple[int, int]:
    """
    اجرای قوانین فعال کاربر.
    برمی‌گرداند: (تعداد مخاطبین تحت تأثیر, تعداد قوانین اجراشده)
    """
    ensure_default_rules(user)
    now = timezone.now()
    affected = 0
    rules_run = 0

    for rule in CRMAutomationRule.objects.filter(user=user, is_active=True):
        if rule.last_run_at and (now - rule.last_run_at).total_seconds() < min_interval_hours * 3600:
            continue
        hits = run_single_rule(rule, update_last_run=True)
        if hits:
            rules_run += 1
            affected += hits

    return affected, rules_run


def count_rule_matches(rule: CRMAutomationRule) -> int:
    """تعداد مخاطبینی که هم‌اکنون شرط قانون را برآورده می‌کنند."""
    if rule.trigger != 'inactive_days':
        return 0
    statuses = rule.status_list() or ['جدید', 'در حال پیگیری']
    return sum(1 for _ in _inactive_customers(rule.user, rule.trigger_days, statuses))


def run_single_rule(rule: CRMAutomationRule, *, update_last_run: bool = True) -> int:
    """اجرای یک قانون روی مخاطبین واجد شرایط."""
    if not rule.is_active:
        return 0
    statuses = rule.status_list() or ['جدید', 'در حال پیگیری']
    hits = 0
    for customer in _inactive_customers(rule.user, rule.trigger_days, statuses):
        if apply_rule(rule, customer):
            hits += 1
    if update_last_run:
        rule.last_run_at = timezone.now()
        rule.save(update_fields=['last_run_at', 'updated_at'])
    return hits


AUTOMATION_PRESETS = [
    {
        'id': 'followup_3d',
        'name': 'پیگیری ۳ روزه',
        'desc': 'یادآور برای مخاطبین جدید بدون فعالیت',
        'icon': 'fa-bell',
        'tone': 'reminder',
        'trigger_days': 3,
        'trigger_statuses': 'جدید,در حال پیگیری',
        'action': 'create_reminder',
        'action_reminder_title': 'پیگیری — بدون فعالیت اخیر',
        'action_reminder_days': 0,
    },
    {
        'id': 'followup_7d',
        'name': 'پیگیری هفتگی',
        'desc': 'یادآور برای سرنخ‌های راکد',
        'icon': 'fa-calendar-check',
        'tone': 'reminder',
        'trigger_days': 7,
        'trigger_statuses': 'جدید,در حال پیگیری',
        'action': 'create_reminder',
        'action_reminder_title': 'پیگیری خودکار — غیرفعال',
        'action_reminder_days': 1,
    },
    {
        'id': 'archive_30d',
        'name': 'بایگانی خودکار',
        'desc': 'انتقال سرنخ‌های قدیمی به بایگانی',
        'icon': 'fa-box-archive',
        'tone': 'status',
        'trigger_days': 30,
        'trigger_statuses': 'جدید',
        'action': 'set_status',
        'action_status': 'بایگانی',
    },
]
