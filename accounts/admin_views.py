"""ویوهای پنل مدیریت سیستم — فقط برای کاربران staff."""
import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import DetailView, TemplateView

from accounts.models import MarketingCampaign, MarketingCampaignRecipient
from accounts.services.admin_dashboard import get_admin_dashboard_context
from accounts.services.admin_exports import EXPORT_REGISTRY, build_export
from accounts.services.admin_marketing import (
    SEGMENT_DEFAULT_TEMPLATES,
    SEGMENT_REGISTRY,
    active_products_for_filter,
    get_marketing_dashboard_stats,
    get_segment_catalog,
    preview_segment,
    render_message,
)
from accounts.services.admin_marketing_send import (
    MarketingSendError,
    campaign_report,
    create_campaign_draft,
    run_campaign_send,
)
from accounts.services.admin_phonebook_sync import (
    PhonebookSyncError,
    get_phonebook_sync_status,
    phonebook_users_id,
    sync_users_to_phonebook,
)
from accounts.services.admin_system_summary import system_summary_json_response
from accounts.services.sms import get_sms_balance_snapshot


class StaffRequiredMixin(UserPassesTestMixin, LoginRequiredMixin):
    """دسترسی فقط برای مدیر سیستم (is_staff)."""

    def test_func(self):
        return self.request.user.is_staff


class AdminDashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days = self.request.GET.get('days', '30')
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30
        days = max(7, min(days, 365))

        dashboard = get_admin_dashboard_context(days=days)
        for card in dashboard.get('kpi_cards', []):
            card['sparkline_json'] = json.dumps(card.get('sparkline', []))
        ctx.update(dashboard)
        ctx['charts_json'] = json.dumps(dashboard['charts'], ensure_ascii=False)
        return ctx


class AdminExportView(StaffRequiredMixin, View):
    """دانلود گزارش Excel یا CSV."""

    def get(self, request, export_key):
        if export_key not in EXPORT_REGISTRY:
            return HttpResponseNotFound('گزارش یافت نشد')

        fmt = request.GET.get('format', 'xlsx').lower()
        if fmt not in ('xlsx', 'csv'):
            fmt = 'xlsx'

        days = request.GET.get('days')
        days_int = None
        if days:
            try:
                days_int = max(1, min(int(days), 365))
            except (TypeError, ValueError):
                days_int = None

        meta = EXPORT_REGISTRY[export_key]
        if meta.get('supports_days') and days_int is None:
            days_int = 30

        return build_export(export_key, fmt=fmt, days=days_int)


class AdminSystemSummaryView(StaffRequiredMixin, View):
    """خروجی JSON خلاصه کامل سیستم."""

    def get(self, request):
        days = request.GET.get('days', '30')
        try:
            days = max(7, min(int(days), 90))
        except (TypeError, ValueError):
            days = 30

        limit = request.GET.get('limit', '50')
        try:
            limit = max(10, min(int(limit), 200))
        except (TypeError, ValueError):
            limit = 50

        download = request.GET.get('download', '1') not in ('0', 'false', 'no')
        return system_summary_json_response(days=days, detail_limit=limit, download=download)


def _parse_int(raw, default=None, *, minimum=None, maximum=None):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


class AdminMarketingView(StaffRequiredMixin, TemplateView):
    """صفحه ساخت و مدیریت کمپین بازاریابی پیامکی."""

    template_name = 'accounts/admin_marketing.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        segment = self.request.GET.get('segment') or 'pending_orders'
        catalog = get_segment_catalog()
        if segment not in {c['key'] for c in catalog}:
            segment = 'pending_orders'

        stale_hours = _parse_int(self.request.GET.get('stale_hours'), None, minimum=1, maximum=720)
        days_lookback = _parse_int(self.request.GET.get('days_lookback'), 14, minimum=1, maximum=90)
        product_id = _parse_int(self.request.GET.get('product_id'), None, minimum=1)
        dedupe_days = _parse_int(self.request.GET.get('dedupe_days'), 7, minimum=0, maximum=90)

        preview = preview_segment(
            segment,
            stale_hours=stale_hours,
            days_lookback=days_lookback,
            product_id=product_id,
        )
        sample_ctx = {
            'name': '',
            'name_part': '',
            'product': 'محصول',
            'plan': '',
            'amount': '',
            'link': 'https://divarfiling.ir/',
            'code': 'SAMPLE15',
        }
        if preview['recipients']:
            s0 = preview['recipients'][0]
            sample_ctx = {
                'name': s0.get('name') or '',
                'name_part': s0.get('name_part') or (f" {s0['name']}" if s0.get('name') else ''),
                'product': s0.get('product') or 'محصول',
                'plan': s0.get('plan') or '',
                'amount': s0.get('amount') or '',
                'link': s0.get('link') or '',
                'code': 'SAMPLE15',
            }
        template = SEGMENT_DEFAULT_TEMPLATES.get(segment, '')
        recent_campaigns = list(
            MarketingCampaign.objects.select_related('shared_discount', 'created_by')[:12]
        )
        for campaign in recent_campaigns:
            attempted = campaign.sent_count + campaign.failed_count
            campaign.success_pct = (
                round(100 * campaign.sent_count / attempted) if attempted else None
            )
            seg_meta = SEGMENT_REGISTRY.get(campaign.segment_key, {})
            campaign.segment_icon = seg_meta.get('icon', 'fa-bullhorn')
            campaign.segment_accent = seg_meta.get('accent', 'violet')
            campaign.segment_title = seg_meta.get('title', campaign.segment_key)

        ctx.update({
            'segments': catalog,
            'selected_segment': segment,
            'preview': preview,
            'stale_hours': stale_hours or '',
            'days_lookback': days_lookback,
            'product_id': product_id or '',
            'dedupe_days': dedupe_days,
            'products': active_products_for_filter(),
            'default_template': template,
            'sample_message': render_message(template, sample_ctx) if sample_ctx else template,
            'sample_context': sample_ctx,
            'sms_balance': get_sms_balance_snapshot(),
            'phonebook_id': phonebook_users_id(),
            'marketing_stats': get_marketing_dashboard_stats(),
            'recent_campaigns': recent_campaigns,
            'segment_meta': next((c for c in catalog if c['key'] == segment), catalog[0]),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        if request.POST.get('confirm_send') != '1':
            messages.error(request, 'برای ارسال، تأیید قطعی را فعال کنید.')
            return redirect('admin_panel_marketing')

        selected_phones = [
            p.strip() for p in request.POST.getlist('selected_phones') if (p or '').strip()
        ]
        if not selected_phones:
            messages.error(request, 'حداقل یک گیرنده را برای ارسال انتخاب کنید.')
            return redirect('admin_panel_marketing')

        segment = request.POST.get('segment_key') or 'pending_orders'
        discount_mode = request.POST.get('discount_mode') or 'none'
        discount_type = request.POST.get('discount_type') or 'percentage'
        discount_value = None
        raw_value = (request.POST.get('discount_value') or '').strip()
        if discount_mode != 'none' and raw_value:
            try:
                discount_value = Decimal(raw_value)
            except (InvalidOperation, ValueError):
                messages.error(request, 'مقدار تخفیف نامعتبر است.')
                return redirect('admin_panel_marketing')

        try:
            campaign = create_campaign_draft(
                name=request.POST.get('name') or '',
                segment_key=segment,
                message_template=request.POST.get('message_template') or '',
                discount_mode=discount_mode,
                created_by=request.user,
                stale_hours=_parse_int(request.POST.get('stale_hours'), None, minimum=1, maximum=720),
                days_lookback=_parse_int(request.POST.get('days_lookback'), None, minimum=1, maximum=90),
                product_id=_parse_int(request.POST.get('product_id'), None, minimum=1),
                dedupe_days=_parse_int(request.POST.get('dedupe_days'), 7, minimum=0, maximum=90) or 0,
                discount_type=discount_type,
                discount_value=discount_value,
                discount_valid_days=_parse_int(
                    request.POST.get('discount_valid_days'), 7, minimum=1, maximum=90,
                ),
                shared_code=request.POST.get('shared_code') or '',
            )
            run_campaign_send(campaign, selected_phones=selected_phones)
        except MarketingSendError as exc:
            messages.error(request, exc.message)
            return redirect('admin_panel_marketing')
        except Exception:
            messages.error(request, 'خطای غیرمنتظره در ارسال کمپین.')
            return redirect('admin_panel_marketing')

        messages.success(
            request,
            f'کمپین ارسال شد: {campaign.sent_count} موفق، '
            f'{campaign.failed_count} ناموفق، {campaign.skipped_count} ردشده.',
        )
        return redirect('admin_panel_marketing_detail', pk=campaign.pk)


class AdminMarketingPreviewView(StaffRequiredMixin, View):
    """پیش‌نمایش AJAX سگمنت."""

    def get(self, request):
        segment = request.GET.get('segment') or 'pending_orders'
        try:
            data = preview_segment(
                segment,
                stale_hours=_parse_int(request.GET.get('stale_hours'), None, minimum=1, maximum=720),
                days_lookback=_parse_int(request.GET.get('days_lookback'), 14, minimum=1, maximum=90),
                product_id=_parse_int(request.GET.get('product_id'), None, minimum=1),
            )
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, **data})


class AdminMarketingDetailView(StaffRequiredMixin, DetailView):
    model = MarketingCampaign
    template_name = 'accounts/admin_marketing_detail.html'
    context_object_name = 'campaign'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campaign = self.object
        ctx['report'] = campaign_report(campaign)
        ctx['recipients'] = (
            MarketingCampaignRecipient.objects
            .filter(campaign=campaign)
            .select_related('user', 'discount_code', 'sms_log')
            .order_by('id')[:300]
        )
        ctx['sms_balance'] = get_sms_balance_snapshot()
        return ctx


class AdminPhonebookStatusView(StaffRequiredMixin, View):
    """وضعیت همگام‌سازی دفترچه تلفن فراز."""

    def get(self, request):
        status = get_phonebook_sync_status()
        return JsonResponse({'ok': status.ok, **status.to_dict()})


class AdminPhonebookSyncView(StaffRequiredMixin, View):
    """همگام‌سازی یک‌کلیکی کاربران با دفترچه تلفن فراز."""

    def post(self, request):
        try:
            result = sync_users_to_phonebook()
        except PhonebookSyncError as exc:
            return JsonResponse({'ok': False, 'error': exc.message, 'code': exc.code}, status=400)
        except Exception:
            return JsonResponse(
                {'ok': False, 'error': 'خطای غیرمنتظره در همگام‌سازی دفترچه تلفن.'},
                status=500,
            )
        return JsonResponse({'ok': True, **result.to_dict()})
