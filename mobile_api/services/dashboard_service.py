"""داشبورد موبایل — تجمیع آمار و پیش‌نمایش."""
from __future__ import annotations

from typing import Any, Dict

from django.utils import timezone

from mobile_api.services.crm_service import today_payload
from mobile_api.services.filing_service import list_datasets
from mobile_api.services.license_service import license_status_payload
from mobile_api.services.notification_service import dismiss_stale_license_alerts, list_notifications, unread_count
from workspace.models import CRMDeal, Dataset
from workspace.services.crm import get_dashboard_stats
from workspace.services.access import has_active_bot_license


def dashboard_payload(user) -> Dict[str, Any]:
    stats = get_dashboard_stats(user)
    today = today_payload(user)
    datasets, _ = list_datasets(user, page=1, page_size=8)
    license_info = license_status_payload(user)
    dismiss_stale_license_alerts(user, license_status=license_info)
    notifications = list_notifications(user, limit=5)
    today_date = timezone.now().date()

    new_files_today = 0
    if has_active_bot_license(user):
        new_files_today = Dataset.objects.filter(
            user=user, is_active=True, created_at__date=today_date,
        ).count()

    deals_count = CRMDeal.objects.filter(user=user).count()
    # CRM today queue contains only unfinished items; completed reminders are
    # counted separately. The progress denominator must include both.
    open_tasks = today['stats']['total']
    completed_tasks = today['stats']['done']

    return {
        'stats': {
            'contacts': stats['total_contacts'],
            'contacts_new': stats['new_contacts'],
            'contacts_in_progress': stats['in_progress'],
            'deals': deals_count,
            'properties': stats['total_properties'],
            'new_files_today': new_files_today,
            'today_tasks_total': open_tasks + completed_tasks,
            'today_tasks_done': completed_tasks,
            'overdue_count': len(today['overdue']),
            'active_reminders': stats['active_reminders'],
            'overdue_followups': stats['overdue_followups'],
        },
        'today_preview': (today['overdue'][:3] + today['today'][:5])[:8],
        'notifications': notifications,
        'notifications_unread': unread_count(user),
        'latest_datasets': datasets,
        'license': license_info,
    }
