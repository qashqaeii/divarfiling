"""Serialize dashboard order details for the order detail modal."""
from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

import jdatetime

from licenses.models import License
from shop.models import Order
from shop.services.downloads import get_order_download_filename, order_can_download


def _jalali(dt, fmt: str = '%Y/%m/%d %H:%M') -> str | None:
    if not dt:
        return None
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return jdatetime.datetime.fromgregorian(datetime=dt).strftime(fmt)


def _format_amount(value) -> str:
    if value is None:
        return '0'
    try:
        return f'{int(float(value)):,}'
    except (TypeError, ValueError):
        return str(value)


def _status_meta(status: str) -> dict:
    mapping = {
        'paid': {'label': 'پرداخت شده', 'tone': 'success', 'icon': 'check-circle'},
        'pending': {'label': 'در انتظار پرداخت', 'tone': 'warning', 'icon': 'clock'},
        'pending_verification': {'label': 'در انتظار تایید پرداخت', 'tone': 'info', 'icon': 'hourglass-half'},
        'failed': {'label': 'ناموفق', 'tone': 'danger', 'icon': 'circle-xmark'},
        'cancelled': {'label': 'لغو شده', 'tone': 'muted', 'icon': 'ban'},
    }
    return mapping.get(status, {'label': status, 'tone': 'muted', 'icon': 'circle-info'})


def _payment_method_label(method: str) -> str:
    return {
        'zibal': 'درگاه زیبال',
        'card_transfer': 'کارت به کارت',
    }.get(method, method)


def _build_actions(order: Order, *, android_available: bool) -> list[dict]:
    actions: list[dict] = []
    oid = str(order.id)

    if order.status == 'paid':
        actions.append({
            'kind': 'primary',
            'label': 'مشاهده لایسنس',
            'url': reverse('payment:success', kwargs={'order_id': oid}),
            'icon': 'key',
        })
        if order_can_download(order):
            actions.append({
                'kind': 'accent',
                'label': 'دانلود ربات ویندوز',
                'url': reverse('payment:download', kwargs={'order_id': oid}),
                'icon': 'download',
            })
        if android_available:
            actions.append({
                'kind': 'ghost',
                'label': 'دانلود اپ اندروید',
                'url': reverse('android_app_download'),
                'icon': 'android',
                'icon_style': 'fab',
            })
    elif order.status == 'pending_verification':
        actions.append({
            'kind': 'warning',
            'label': 'پیگیری پرداخت کارت به کارت',
            'url': reverse('payment:card_pending', kwargs={'order_id': oid}),
            'icon': 'hourglass-half',
        })
    elif order.status == 'pending':
        if order.payment_method == 'card_transfer':
            actions.append({
                'kind': 'primary',
                'label': 'تکمیل پرداخت کارت به کارت',
                'url': reverse('payment:card_transfer', kwargs={'order_id': oid}),
                'icon': 'credit-card',
            })
        else:
            actions.append({
                'kind': 'primary',
                'label': 'پرداخت آنلاین',
                'url': reverse('payment:checkout', kwargs={'order_id': oid}),
                'icon': 'credit-card',
            })
    elif order.status == 'failed':
        actions.append({
            'kind': 'primary',
            'label': 'تلاش مجدد پرداخت',
            'url': reverse('payment:checkout', kwargs={'order_id': oid}),
            'icon': 'rotate-right',
        })

    actions.append({
        'kind': 'ghost',
        'label': 'کپی شماره سفارش',
        'action': 'copy_order_id',
        'icon': 'copy',
    })
    return actions


def serialize_order_detail(order: Order, *, android_available: bool = False) -> dict:
    status = _status_meta(order.status)
    licenses = list(
        License.objects.filter(order=order).order_by('sequence', 'pk').values('license_key', 'plan__name')
    )
    if order.renewal_license_id:
        licenses = [{
            'license_key': order.renewal_license.license_key,
            'plan__name': order.renewal_license.plan.name if order.renewal_license.plan_id else '',
        }]

    transaction = getattr(order, 'transaction', None)
    card_transfer = getattr(order, 'card_transfer', None)

    timeline = [
        {
            'key': 'created',
            'label': 'ثبت سفارش',
            'at': _jalali(order.created_at),
            'done': True,
        },
    ]
    if order.payment_method == 'card_transfer' and card_transfer:
        timeline.append({
            'key': 'card_submitted',
            'label': 'ثبت رسید کارت به کارت',
            'at': _jalali(card_transfer.created_at),
            'done': True,
        })
    if order.status == 'pending_verification':
        timeline.append({
            'key': 'verification',
            'label': 'بررسی پرداخت توسط تیم',
            'at': None,
            'done': False,
            'active': True,
        })
    if order.paid_at:
        timeline.append({
            'key': 'paid',
            'label': 'پرداخت تأیید شد',
            'at': _jalali(order.paid_at),
            'done': True,
        })
    elif order.status == 'failed':
        timeline.append({
            'key': 'failed',
            'label': 'پرداخت ناموفق',
            'at': _jalali(transaction.verified_at if transaction else None),
            'done': True,
            'tone': 'danger',
        })
    elif order.status == 'cancelled':
        timeline.append({
            'key': 'cancelled',
            'label': 'سفارش لغو شد',
            'at': None,
            'done': True,
            'tone': 'muted',
        })

    return {
        'id': str(order.id),
        'id_short': str(order.id)[:8],
        'product_title': order.product.title,
        'plan_name': order.plan.name,
        'quantity': order.quantity,
        'amount': str(int(order.amount)),
        'amount_display': _format_amount(order.amount),
        'original_price': _format_amount(order.original_price) if order.original_price else None,
        'discount_amount': _format_amount(order.discount_amount) if order.discount_amount else None,
        'discount_code': order.discount_code.code if order.discount_code_id else None,
        'status': order.status,
        'status_label': status['label'],
        'status_tone': status['tone'],
        'status_icon': status['icon'],
        'payment_method': order.payment_method,
        'payment_method_label': _payment_method_label(order.payment_method),
        'created_at': _jalali(order.created_at),
        'paid_at': _jalali(order.paid_at),
        'zibal_track_id': order.zibal_track_id or None,
        'is_renewal': bool(order.renewal_license_id),
        'can_download': order_can_download(order),
        'download_filename': get_order_download_filename(order) if order_can_download(order) else None,
        'licenses': [
            {'key': row['license_key'], 'plan': row.get('plan__name') or order.plan.name}
            for row in licenses
        ],
        'transaction': None if not transaction else {
            'track_id': transaction.zibal_track_id,
            'ref_number': transaction.zibal_ref_number,
            'status': transaction.status,
            'card_masked': transaction.card_number_masked or None,
            'verified_at': _jalali(transaction.verified_at),
            'gateway_message': transaction.gateway_message or None,
        },
        'card_transfer': None if not card_transfer else {
            'status': card_transfer.status,
            'status_label': card_transfer.get_status_display(),
            'reference_number': card_transfer.reference_number,
            'payer_name': card_transfer.payer_name or None,
            'transferred_at': _jalali(card_transfer.transferred_at),
            'user_note': card_transfer.user_note or None,
            'admin_note': card_transfer.admin_note or None,
            'reviewed_at': _jalali(card_transfer.reviewed_at),
        },
        'timeline': timeline,
        'actions': _build_actions(order, android_available=android_available),
    }
