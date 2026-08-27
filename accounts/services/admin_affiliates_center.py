"""مرکز همکاری در فروش — KPI، مشاوران، فروش و برداشت."""
from __future__ import annotations

from typing import Any, Dict, List

from django.db.models import Min, Sum
from django.urls import reverse

from accounts.services.admin_dashboard import (
    TABLE_PREVIEW_ROWS,
    _date_range,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
    get_affiliate_partners,
    get_pending_withdrawals,
    get_recent_affiliate_sales,
)
from affiliates.models import Affiliate, AffiliateSale, Withdrawal


def _safe_user_display(user) -> str:
    return user.get_full_name() or user.username or 'کاربر'


def _admin_affiliate_url(pk: int) -> str:
    return reverse('admin:affiliates_affiliate_change', args=[pk])


def _admin_sale_url(pk: int) -> str:
    return reverse('admin:affiliates_affiliatesale_change', args=[pk])


def _admin_withdrawal_url(pk: int) -> str:
    return reverse('admin:affiliates_withdrawal_change', args=[pk])


def _snapshot_counts() -> Dict[str, int]:
    commissions_total = int(
        AffiliateSale.objects.filter(status='paid').aggregate(
            total=Sum('commission_amount'),
        )['total'] or 0
    )
    pending_commission = int(
        AffiliateSale.objects.filter(status='pending').aggregate(
            total=Sum('commission_amount'),
        )['total'] or 0
    )
    return {
        'affiliates_active': Affiliate.objects.filter(is_active=True).count(),
        'affiliates_total': Affiliate.objects.count(),
        'commissions_total': commissions_total,
        'pending_commission': pending_commission,
        'pending_withdrawals': Withdrawal.objects.filter(status='pending').count(),
    }


def _sales_paid_between(start, end) -> int:
    return AffiliateSale.objects.filter(
        status='paid',
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _commission_between(start, end) -> int:
    return int(
        AffiliateSale.objects.filter(
            status='paid',
            created_at__date__gte=start,
            created_at__date__lte=end,
        ).aggregate(total=Sum('commission_amount'))['total'] or 0
    )


def _new_affiliates_between(start, end) -> int:
    return Affiliate.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _withdrawals_between(start, end) -> int:
    return Withdrawal.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _build_snapshot_kpi_cards(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'affiliates_active',
            'label': 'مشاور فعال',
            'value': snapshot['affiliates_active'],
            'format': 'count',
            'delta': None,
            'delta_label': f"{snapshot['affiliates_total']} کل",
            'sublabel': 'وضعیت فعلی',
            'icon': 'fa-handshake',
            'accent': 'violet',
            'status': 'ok',
        },
        {
            'key': 'commissions_total',
            'label': 'کمیسیون پرداخت‌شده',
            'value': snapshot['commissions_total'],
            'format': 'money',
            'delta': None,
            'delta_label': 'تجمعی',
            'sublabel': 'وضعیت فعلی',
            'icon': 'fa-coins',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'pending_commission',
            'label': 'کمیسیون معلق',
            'value': snapshot['pending_commission'],
            'format': 'money',
            'delta': None,
            'delta_label': 'در انتظار تسویه',
            'sublabel': 'وضعیت فعلی',
            'icon': 'fa-hourglass-half',
            'accent': 'amber',
            'status': 'warn' if snapshot['pending_commission'] else 'ok',
        },
        {
            'key': 'pending_withdrawals',
            'label': 'برداشت معلق',
            'value': snapshot['pending_withdrawals'],
            'format': 'count',
            'delta': None,
            'delta_label': 'نیاز به تأیید',
            'sublabel': 'وضعیت فعلی',
            'icon': 'fa-wallet',
            'accent': 'rose',
            'status': 'warn' if snapshot['pending_withdrawals'] else 'ok',
        },
    ]


def _build_range_kpi_cards(
    *,
    days: int,
    sales_paid: int,
    prev_sales_paid: int,
    commission: int,
    prev_commission: int,
    new_affiliates: int,
    prev_new_affiliates: int,
    withdrawals: int,
    prev_withdrawals: int,
) -> List[Dict[str, Any]]:
    range_label = _range_label_fa(days)

    def card(key, label, value, prev, icon, accent, fmt='count'):
        return {
            'key': key,
            'kind': 'range',
            'label': label,
            'sublabel': range_label,
            'value': value,
            'format': fmt,
            'delta': _pct_change(value, prev),
            'delta_label': 'نسبت دوره قبل',
            'icon': icon,
            'accent': accent,
            'status': 'ok',
        }

    return [
        card('sales_paid_period', 'فروش پرداخت‌شده', sales_paid, prev_sales_paid, 'fa-circle-check', 'emerald'),
        card('commission_period', 'کمیسیون بازه', commission, prev_commission, 'fa-sack-dollar', 'cyan', 'money'),
        card('new_affiliates_period', 'مشاور جدید', new_affiliates, prev_new_affiliates, 'fa-user-plus', 'blue'),
        card('withdrawals_period', 'درخواست برداشت', withdrawals, prev_withdrawals, 'fa-money-bill-transfer', 'violet'),
    ]


def build_affiliate_action_items(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    pending = snapshot.get('pending_withdrawals', 0)
    if not pending:
        return items

    oldest = (
        Withdrawal.objects.filter(status='pending')
        .aggregate(oldest=Min('created_at'))['oldest']
    )
    detail = f'{pending} درخواست'
    if oldest:
        from accounts.services.admin_support_center import _age_label

        if age := _age_label(oldest):
            detail += f' · قدیمی‌ترین {age}'

    items.append({
        'key': 'pending_withdrawals',
        'priority': 'high',
        'title': 'برداشت در انتظار تأیید',
        'count': pending,
        'detail': detail,
        'icon': 'fa-wallet',
        'accent': 'rose',
        'cta': 'بررسی',
        'href': '#affiliate-withdrawals',
    })
    return items


def _serialize_partners(partners) -> List[Dict[str, Any]]:
    rows = []
    for partner in partners:
        rows.append({
            'id': partner.pk,
            'code': partner.code,
            'user_display': _safe_user_display(partner.user),
            'sales_paid': int(partner.sales_paid or 0),
            'commission_total': int(partner.commission_total or 0),
            'commission_pending': int(partner.commission_pending or 0),
            'is_active': partner.is_active,
            'admin_url': _admin_affiliate_url(partner.pk),
        })
    return rows


def _serialize_sales(sales) -> List[Dict[str, Any]]:
    rows = []
    for sale in sales:
        rows.append({
            'id': sale.pk,
            'affiliate_code': sale.affiliate.code,
            'affiliate_display': _safe_user_display(sale.affiliate.user),
            'order_amount': int(sale.order.amount or 0),
            'commission_amount': int(sale.commission_amount or 0),
            'status_label': sale.get_status_display(),
            'created_at': sale.created_at,
            'admin_url': _admin_sale_url(sale.pk),
        })
    return rows


def _serialize_withdrawals(items) -> List[Dict[str, Any]]:
    rows = []
    for withdrawal in items:
        rows.append({
            'id': withdrawal.pk,
            'user_display': _safe_user_display(withdrawal.wallet.user),
            'amount': int(withdrawal.amount),
            'bank_name': withdrawal.bank_name or '—',
            'status_label': withdrawal.get_status_display(),
            'created_at': withdrawal.created_at,
            'admin_url': _admin_withdrawal_url(withdrawal.pk),
        })
    return rows


def get_affiliates_center_context(*, days: int = 30, compare: bool = False) -> Dict[str, Any]:
    del compare

    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    range_label = _range_label_fa(days)
    snapshot = _snapshot_counts()

    return {
        'range_label': range_label,
        'days': days,
        'snapshot_counts': snapshot,
        'snapshot_kpi_cards': _build_snapshot_kpi_cards(snapshot),
        'range_kpi_cards': _build_range_kpi_cards(
            days=days,
            sales_paid=_sales_paid_between(start, end),
            prev_sales_paid=_sales_paid_between(prev_start, prev_end),
            commission=_commission_between(start, end),
            prev_commission=_commission_between(prev_start, prev_end),
            new_affiliates=_new_affiliates_between(start, end),
            prev_new_affiliates=_new_affiliates_between(prev_start, prev_end),
            withdrawals=_withdrawals_between(start, end),
            prev_withdrawals=_withdrawals_between(prev_start, prev_end),
        ),
        'action_items': build_affiliate_action_items(snapshot),
        'partner_rows': _serialize_partners(get_affiliate_partners(limit=TABLE_PREVIEW_ROWS)),
        'sale_rows': _serialize_sales(get_recent_affiliate_sales(limit=TABLE_PREVIEW_ROWS)),
        'withdrawal_rows': _serialize_withdrawals(get_pending_withdrawals(limit=TABLE_PREVIEW_ROWS)),
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'export_urls': {
            'affiliate_sales': reverse('admin_panel_export', args=['affiliate_sales']) + '?format=xlsx',
            'pending_withdrawals': reverse('admin_panel_export', args=['pending_withdrawals']) + '?format=xlsx',
        },
        'admin_list_urls': {
            'affiliates': reverse('admin:affiliates_affiliate_changelist'),
            'sales': reverse('admin:affiliates_affiliatesale_changelist'),
            'withdrawals': reverse('admin:affiliates_withdrawal_changelist') + '?status__exact=pending',
        },
    }
