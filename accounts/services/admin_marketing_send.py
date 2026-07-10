"""ارسال دسته‌ای کمپین بازاریابی پیامکی."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from accounts.models import MarketingCampaign, MarketingCampaignRecipient
from accounts.services.admin_marketing import (
    MARKETING_BATCH_LIMIT,
    SEGMENT_DEFAULT_TEMPLATES,
    SEGMENT_REGISTRY,
    build_segment_recipients,
    create_shared_discount,
    create_unique_discount,
    recently_marketed_phones,
    render_message,
)
from accounts.services.notifications import notify_marketing
from accounts.services.sms import get_sms_balance_snapshot

logger = logging.getLogger(__name__)


class MarketingSendError(Exception):
    def __init__(self, message: str, *, code: str = 'marketing_error'):
        self.message = message
        self.code = code
        super().__init__(message)


def create_campaign_draft(
    *,
    name: str,
    segment_key: str,
    message_template: str,
    discount_mode: str,
    created_by,
    stale_hours: Optional[int] = None,
    days_lookback: Optional[int] = None,
    product_id: Optional[int] = None,
    dedupe_days: int = 7,
    discount_type: str = 'percentage',
    discount_value: Optional[Decimal] = None,
    discount_valid_days: Optional[int] = None,
    shared_code: str = '',
) -> MarketingCampaign:
    if segment_key not in SEGMENT_REGISTRY:
        raise MarketingSendError('سگمنت نامعتبر است.', code='bad_segment')

    mode = discount_mode if discount_mode in (
        MarketingCampaign.DiscountMode.NONE,
        MarketingCampaign.DiscountMode.SHARED,
        MarketingCampaign.DiscountMode.UNIQUE,
    ) else MarketingCampaign.DiscountMode.NONE

    template = (message_template or '').strip() or SEGMENT_DEFAULT_TEMPLATES.get(segment_key, '')
    if not template:
        raise MarketingSendError('متن پیام خالی است.', code='empty_message')

    if mode != MarketingCampaign.DiscountMode.NONE:
        if discount_value is None or Decimal(discount_value) <= 0:
            raise MarketingSendError('مقدار تخفیف نامعتبر است.', code='bad_discount')
        if not discount_valid_days or discount_valid_days < 1:
            raise MarketingSendError('مدت اعتبار تخفیف نامعتبر است.', code='bad_discount_days')

    campaign = MarketingCampaign.objects.create(
        name=(name or '').strip() or f'کمپین {SEGMENT_REGISTRY[segment_key]["title"]}',
        segment_key=segment_key,
        status=MarketingCampaign.Status.DRAFT,
        message_template=template,
        discount_mode=mode,
        stale_hours=stale_hours or None,
        days_lookback=days_lookback or None,
        product_id=product_id or None,
        dedupe_days=max(0, int(dedupe_days or 0)),
        discount_type=discount_type if mode != MarketingCampaign.DiscountMode.NONE else '',
        discount_value=discount_value if mode != MarketingCampaign.DiscountMode.NONE else None,
        discount_valid_days=discount_valid_days if mode != MarketingCampaign.DiscountMode.NONE else None,
        created_by=created_by,
    )

    if mode == MarketingCampaign.DiscountMode.SHARED:
        recipients_preview = build_segment_recipients(
            segment_key,
            stale_hours=stale_hours,
            days_lookback=days_lookback,
            product_id=product_id,
            limit=MARKETING_BATCH_LIMIT,
        )
        max_uses = max(len(recipients_preview) * 2, 10)
        try:
            shared = create_shared_discount(
                code=shared_code,
                discount_type=discount_type,
                discount_value=discount_value,
                max_uses=max_uses,
                valid_days=int(discount_valid_days),
                description=f'کمپین #{campaign.pk}: {campaign.name}',
            )
        except ValueError as exc:
            campaign.delete()
            raise MarketingSendError(str(exc), code='discount_exists') from exc
        campaign.shared_discount = shared
        campaign.save(update_fields=['shared_discount'])

    return campaign


def run_campaign_send(campaign: MarketingCampaign) -> MarketingCampaign:
    """ساخت گیرندگان و ارسال پیامک تا سقف batch."""
    if campaign.status not in (
        MarketingCampaign.Status.DRAFT,
        MarketingCampaign.Status.FAILED,
    ):
        raise MarketingSendError('این کمپین قابل ارسال مجدد نیست.', code='bad_status')

    balance = get_sms_balance_snapshot(use_cache=False)
    if balance.get('error') and balance.get('provider') == 'faraz':
        # فقط هشدار — ارسال را متوقف نکن مگر auth fail واضح
        if 'احراز' in (balance.get('error') or '') or 'Api-Key' in (balance.get('error') or ''):
            raise MarketingSendError(balance['error'], code='sms_auth')

    recipients = build_segment_recipients(
        campaign.segment_key,
        stale_hours=campaign.stale_hours,
        days_lookback=campaign.days_lookback,
        product_id=campaign.product_id,
        limit=MARKETING_BATCH_LIMIT,
    )
    if not recipients:
        raise MarketingSendError('گیرنده‌ای برای این سگمنت یافت نشد.', code='empty_segment')

    phones = [r.phone for r in recipients]
    recently = recently_marketed_phones(phones, days=campaign.dedupe_days)

    campaign.status = MarketingCampaign.Status.SENDING
    campaign.recipients_total = len(recipients)
    campaign.sent_count = 0
    campaign.failed_count = 0
    campaign.skipped_count = 0
    campaign.save(update_fields=[
        'status', 'recipients_total', 'sent_count', 'failed_count', 'skipped_count',
    ])

    shared_code = ''
    if campaign.discount_mode == MarketingCampaign.DiscountMode.SHARED and campaign.shared_discount_id:
        shared_code = campaign.shared_discount.code

    for item in recipients:
        ctx = dict(item.context or {})
        if shared_code:
            ctx['code'] = shared_code

        with transaction.atomic():
            recipient, created = MarketingCampaignRecipient.objects.get_or_create(
                campaign=campaign,
                phone=item.phone,
                defaults={
                    'user': item.user,
                    'context_json': ctx,
                    'status': MarketingCampaignRecipient.Status.PENDING,
                },
            )
            if not created and recipient.status == MarketingCampaignRecipient.Status.SENT:
                campaign.skipped_count += 1
                continue

            if item.phone in recently:
                recipient.status = MarketingCampaignRecipient.Status.SKIPPED
                recipient.skip_reason = f'پیام بازاریابی در {campaign.dedupe_days} روز اخیر'
                recipient.context_json = ctx
                recipient.save(update_fields=['status', 'skip_reason', 'context_json', 'updated_at'])
                campaign.skipped_count += 1
                continue

            discount_obj = None
            if campaign.discount_mode == MarketingCampaign.DiscountMode.UNIQUE:
                discount_obj = create_unique_discount(
                    discount_type=campaign.discount_type or 'percentage',
                    discount_value=campaign.discount_value or 0,
                    valid_days=int(campaign.discount_valid_days or 7),
                    description=f'کمپین #{campaign.pk} / {item.phone}',
                )
                ctx['code'] = discount_obj.code
                recipient.discount_code = discount_obj
            elif shared_code:
                ctx['code'] = shared_code
                recipient.discount_code = campaign.shared_discount

            # اگر قالب به {code} نیاز دارد ولی کد نداریم
            if '{code}' in campaign.message_template and not ctx.get('code'):
                ctx['code'] = '—'

            text = render_message(campaign.message_template, ctx)
            recipient.context_json = ctx
            recipient.user = item.user
            recipient.save()

        ok, sms_log = notify_marketing(
            item.phone,
            text=text,
            attributes={
                'code': ctx.get('code', ''),
                'product': ctx.get('product', ''),
                'link': ctx.get('link', ''),
                'name': ctx.get('name', ''),
                'message': text[:200],
            },
        )
        recipient.sms_log = sms_log
        if ok:
            recipient.status = MarketingCampaignRecipient.Status.SENT
            recipient.skip_reason = ''
            campaign.sent_count += 1
        else:
            recipient.status = MarketingCampaignRecipient.Status.FAILED
            recipient.skip_reason = (sms_log.error_message if sms_log else 'ارسال ناموفق')[:200]
            campaign.failed_count += 1
        recipient.save(update_fields=[
            'status', 'skip_reason', 'sms_log', 'discount_code', 'context_json', 'updated_at',
        ])

    campaign.status = MarketingCampaign.Status.COMPLETED
    campaign.completed_at = timezone.now()
    campaign.save(update_fields=[
        'status', 'sent_count', 'failed_count', 'skipped_count', 'completed_at',
    ])
    logger.info(
        'Marketing campaign #%s done sent=%s failed=%s skipped=%s',
        campaign.pk, campaign.sent_count, campaign.failed_count, campaign.skipped_count,
    )
    return campaign


def campaign_report(campaign: MarketingCampaign) -> Dict[str, Any]:
    return {
        'id': campaign.pk,
        'name': campaign.name,
        'segment_key': campaign.segment_key,
        'segment_title': SEGMENT_REGISTRY.get(campaign.segment_key, {}).get('title', campaign.segment_key),
        'status': campaign.status,
        'status_label': campaign.get_status_display(),
        'discount_mode': campaign.discount_mode,
        'shared_code': campaign.shared_discount.code if campaign.shared_discount_id else '',
        'recipients_total': campaign.recipients_total,
        'sent_count': campaign.sent_count,
        'failed_count': campaign.failed_count,
        'skipped_count': campaign.skipped_count,
        'message_template': campaign.message_template,
        'created_at': campaign.created_at,
        'completed_at': campaign.completed_at,
    }
