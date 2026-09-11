"""اقدام‌های پیشنهادی میزکار — فقط از شمارنده‌های موجود، بدون موتور Match زنده."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.urls import reverse
from django.utils import timezone

from workspace.models import PropertyMatchAlert
from workspace.services.crm_scope import can_view_team_inbox, team_inbox_qs

NBA_LIMIT = 3


def _card(
    *,
    key: str,
    title: str,
    count: int,
    desc: str,
    cta: str,
    url_name: str,
    query: str = '',
    url_id: Optional[int] = None,
    tone: str = 'info',
) -> Dict[str, Any]:
    if url_id is not None:
        path = reverse(url_name, kwargs={'customer_id': url_id})
    else:
        path = reverse(url_name)
    if query:
        path = f'{path}?{query}'
    return {
        'key': key,
        'title': title,
        'count': count,
        'desc': desc,
        'cta': cta,
        'url': path,
        'tone': tone,
    }


def _match_opportunity(user) -> Optional[Dict[str, Any]]:
    qs = PropertyMatchAlert.objects.filter(
        user=user,
        status__in=[
            PropertyMatchAlert.STATUS_PENDING,
            PropertyMatchAlert.STATUS_NOTIFIED,
        ],
    )
    count = qs.values('customer_id').distinct().count()
    if not count:
        return None
    if count == 1:
        customer_id = qs.values_list('customer_id', flat=True).first()
        if not customer_id:
            return None
        return _card(
            key='matches',
            title='مخاطب فایل پیشنهادی دارد',
            count=1,
            desc='فایل‌های مناسب آماده بررسی‌اند',
            cta='مشاهده پیشنهادها',
            url_name='workspace:crm_detail',
            url_id=customer_id,
            query='tab=matches',
            tone='info',
        )
    return _card(
        key='matches',
        title='مخاطب فایل پیشنهادی دارند',
        count=count,
        desc='فایل‌های مناسب آماده بررسی‌اند',
        cta='مشاهده مخاطبین',
        url_name='workspace:crm_contacts',
        query='match_alerts=1',
        tone='info',
    )


def build_home_nba(
    user,
    *,
    crm_nav_counts: Dict[str, Any],
    datasets_qs,
    has_bot_license: bool,
    contact_count: int = 0,
    dataset_count: int = 0,
) -> List[Dict[str, Any]]:
    """حداکثر ۳ کارت؛ اولویت Overdue > Agency inbox > Today > Match alerts > پوشه تازه."""
    actions: List[Dict[str, Any]] = []
    overdue = int(crm_nav_counts.get('today_overdue') or crm_nav_counts.get('overdue') or 0)
    today_due = int(crm_nav_counts.get('today_due') or 0)

    if overdue:
        actions.append(_card(
            key='overdue',
            title='پیگیری معوق',
            count=overdue,
            desc='بهتر است از قدیمی‌ترین مورد شروع کنید',
            cta='شروع پیگیری',
            url_name='workspace:crm_today',
            tone='warn',
        ))

    if len(actions) < NBA_LIMIT and can_view_team_inbox(user):
        inbox_count = team_inbox_qs(user).count()
        if inbox_count:
            actions.append(_card(
                key='agency_inbox',
                title='مخاطب در انتظار تخصیص',
                count=inbox_count,
                desc='صندوق آژانس مخاطب تخصیص‌نیافته دارد',
                cta='مشاهده صندوق آژانس',
                url_name='workspace:agency_hub_dashboard',
                query='tab=inbox',
                tone='info',
            ))

    if len(actions) < NBA_LIMIT and today_due:
        actions.append(_card(
            key='today',
            title='کار امروز',
            count=today_due,
            desc='پیگیری و یادآورهای امروز آماده انجام‌اند',
            cta='باز کردن کارهای امروز',
            url_name='workspace:crm_today',
            tone='info',
        ))

    if len(actions) < NBA_LIMIT and contact_count:
        match_card = _match_opportunity(user)
        if match_card:
            actions.append(match_card)

    if len(actions) < NBA_LIMIT and has_bot_license and dataset_count:
        cutoff = timezone.now() - timedelta(hours=24)
        new_folders = datasets_qs.filter(created_at__gte=cutoff).count()
        if new_folders:
            actions.append(_card(
                key='new_filing',
                title='پوشه استخراج تازه',
                count=new_folders,
                desc='در ۲۴ ساعت گذشته به فایلینگ اضافه شده',
                cta='مشاهده آگهی‌ها',
                url_name='workspace:dataset_list',
                tone='info',
            ))

    return actions[:NBA_LIMIT]
