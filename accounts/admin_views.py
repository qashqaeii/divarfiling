"""ویوهای پنل مدیریت سیستم — فقط برای کاربران staff."""
import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponseNotFound, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from accounts.models import MarketingCampaign, MarketingCampaignRecipient
from accounts.services.admin_database_backup import (
    DatabaseBackupError,
    create_database_backup,
    get_database_backup_info,
    iter_backup_file_chunks,
)
from accounts.services.admin_dashboard import get_command_center_context
from accounts.services.admin_panel_shell import parse_admin_panel_range
from accounts.services.admin_exports import EXPORT_REGISTRY, build_export
from accounts.services.admin_export_permissions import can_export_report
from accounts.services.admin_marketing import (
    AUTOMATION_FLOWS,
    MESSAGE_TEMPLATE_CATALOG,
    SEGMENT_DEFAULT_TEMPLATES,
    SEGMENT_REGISTRY,
    active_products_for_filter,
    campaign_timeline_events,
    enrich_campaign_row,
    get_ai_campaign_suggestion,
    get_all_segment_insights,
    get_marketing_analytics,
    get_marketing_dashboard_stats,
    get_recovery_flow_bridge_stats,
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
from accounts.services.admin_blog import (
    build_blog_stats_json,
    get_blog_analytics_chart,
    get_blog_dashboard_stats,
    get_blog_posts_table,
)
from blog.services.market_article_eligibility import count_eligible_datasets
from accounts.services.admin_academy import (
    build_academy_stats_json,
    get_academy_analytics_chart,
    get_academy_dashboard_stats,
    get_academy_videos_table,
)
from accounts.services.admin_plan_conversion import (
    build_plan_conversion_json,
    get_plan_conversion_context,
)
from accounts.services.admin_recovery_center import (
    build_recovery_center_json,
    get_recovery_center_context,
)
from accounts.services.admin_sales_center import get_sales_center_context
from accounts.services.admin_users_center import get_users_center_context
from accounts.services.admin_licenses_center import get_licenses_center_context
from accounts.services.admin_operations_center import get_operations_center_context
from accounts.services.admin_support_center import get_support_center_context
from accounts.services.admin_activity_center import get_activity_center_context
from accounts.services.admin_android_center import get_android_center_context
from accounts.services.admin_windows_center import get_windows_center_context
from accounts.services.admin_crm_center import get_crm_center_context
from accounts.services.admin_ai_center import build_ai_center_context, build_ai_stats_json
from accounts.services.admin_affiliates_center import get_affiliates_center_context
from accounts.services.admin_exports_center import get_exports_center_context
from accounts.services.admin_management_assistant import (
    get_assistant_preview,
    get_automation_rule_detail,
    get_management_assistant_context,
    preview_automation_rule,
    preview_insight_recipients,
    preview_rule_message,
    run_automation_rule_now,
    send_automation_test_message,
    send_insight_campaign,
    toggle_automation_rule,
    update_automation_rule_settings,
)
from accounts.services.admin_phonebook_sync import (
    PhonebookSyncError,
    get_phonebook_sync_status,
    phonebook_users_id,
    sync_users_to_phonebook,
)
from accounts.services.admin_system_summary import system_summary_json_response
from accounts.services.admin_users_management import (
    get_user_management_detail,
    list_users_management,
)
from accounts.services.sms import get_sms_balance_snapshot
from blog.services.article_import import (
    ArticleImportError,
    import_article_from_payload,
    validate_article_payload,
)

logger = logging.getLogger(__name__)


class StaffRequiredMixin(UserPassesTestMixin, LoginRequiredMixin):
    """دسترسی فقط برای مدیر سیستم (is_staff)."""

    def test_func(self):
        return self.request.user.is_staff


class AdminDashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)

        dashboard = get_command_center_context(days=days)
        for card in dashboard.get('kpi_cards', []):
            spark = card.get('sparkline')
            card['sparkline_json'] = json.dumps(spark) if spark else ''
        ctx.update(dashboard)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['charts_json'] = json.dumps(dashboard['charts'], ensure_ascii=False)
        ctx['assistant_preview'] = get_assistant_preview()
        return ctx


class SuperuserRequiredMixin(StaffRequiredMixin):
    """Restrict sensitive full-database operations to system owners."""

    def test_func(self):
        return super().test_func() and self.request.user.is_superuser


class AdminDatabaseBackupView(SuperuserRequiredMixin, View):
    """دانلود بک‌آپ کامل دیتابیس — فقط مدیر ارشد (superuser)."""

    def get(self, request):
        fmt = (request.GET.get('format') or 'auto').lower().strip()
        allowed = {'auto', 'pg_dump', 'custom', 'dumpdata', 'sqlite'}
        if fmt not in allowed:
            fmt = 'auto'

        try:
            result = create_database_backup(fmt=fmt)
        except DatabaseBackupError as exc:
            messages.error(request, exc.message)
            return redirect('admin_panel')
        except Exception:
            logger.exception('Unexpected database backup failure (format=%s)', fmt)
            messages.error(
                request,
                'خطای غیرمنتظره هنگام بک‌آپ. لاگ سرور را بررسی کنید یا از فرمت JSON امتحان کنید.',
            )
            return redirect('admin_panel')

        response = StreamingHttpResponse(
            iter_backup_file_chunks(result),
            content_type=result.content_type,
        )
        response['Content-Disposition'] = f'attachment; filename="{result.filename}"'
        response['X-Backup-Method'] = result.method
        if result.size_bytes:
            response['Content-Length'] = str(result.size_bytes)
        return response


class AdminExportView(StaffRequiredMixin, View):
    """دانلود گزارش Excel یا CSV."""

    def get(self, request, export_key):
        if export_key not in EXPORT_REGISTRY:
            return HttpResponseNotFound('گزارش یافت نشد')
        if not can_export_report(request.user, export_key):
            raise PermissionDenied('مجوز دریافت این گزارش را ندارید.')

        fmt = request.GET.get('format', 'xlsx').lower()
        if fmt not in ('xlsx', 'csv'):
            fmt = 'xlsx'

        days = request.GET.get('days')
        days_int = None
        if days:
            if str(days).strip().lower() == 'all':
                from accounts.services.admin_dashboard import ALL_TIME_DAYS
                days_int = ALL_TIME_DAYS
            else:
                try:
                    days_int = max(1, min(int(days), 365))
                except (TypeError, ValueError):
                    days_int = None

        meta = EXPORT_REGISTRY[export_key]
        if meta.get('supports_days') and days_int is None:
            from accounts.services.admin_dashboard import ALL_TIME_DAYS
            days_int = ALL_TIME_DAYS

        stage = (request.GET.get('stage') or '').strip() or None
        if stage and meta.get('supports_stage'):
            from accounts.models import GrowthJourney

            valid_stages = {choice[0] for choice in GrowthJourney.Stage.choices}
            if stage not in valid_stages:
                stage = None

        response = build_export(export_key, fmt=fmt, days=days_int, stage=stage)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


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


class AdminUsersManagementListView(StaffRequiredMixin, View):
    """JSON لیست مدیریت کاربران — جستجو، فیلتر، صفحه‌بندی."""

    def get(self, request):
        filters = {
            'license': (request.GET.get('license') or '').strip(),
            'windows': (request.GET.get('windows') or '').strip(),
            'android': (request.GET.get('android') or '').strip(),
            'datasets': (request.GET.get('datasets') or '').strip(),
            'crm': (request.GET.get('crm') or '').strip(),
            'paid': (request.GET.get('paid') or '').strip(),
        }
        payload = list_users_management(
            q=(request.GET.get('q') or '').strip(),
            page=_parse_int(request.GET.get('page'), 1, minimum=1, maximum=9999) or 1,
            page_size=_parse_int(request.GET.get('page_size'), 25, minimum=1, maximum=100) or 25,
            sort=(request.GET.get('sort') or '-date_joined').strip(),
            filters=filters,
        )
        return JsonResponse(
            payload,
            encoder=DjangoJSONEncoder,
            json_dumps_params={'ensure_ascii': False},
        )


class AdminUsersManagementDetailView(StaffRequiredMixin, View):
    """JSON جزئیات یک کاربر برای پنل مدیریت."""

    def get(self, request, user_id):
        data = get_user_management_detail(user_id)
        if not data:
            return JsonResponse({'ok': False, 'error': 'کاربر یافت نشد'}, status=404)
        return JsonResponse(
            {'ok': True, 'user': data},
            encoder=DjangoJSONEncoder,
            json_dumps_params={'ensure_ascii': False},
        )


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
        if segment == 'abandoned_checkout' and not stale_hours:
            stale_hours = 2
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
            enrich_campaign_row(campaign)

        sms_balance = get_sms_balance_snapshot()
        sms_credit = None
        if sms_balance.get('ok'):
            sms_credit = sms_balance.get('sms_count') or sms_balance.get('credit')

        analytics = get_marketing_analytics(days=30)
        timeline_campaign = recent_campaigns[0] if recent_campaigns else None
        timeline_events = (
            campaign_timeline_events(timeline_campaign) if timeline_campaign else []
        )

        ctx.update({
            'segments': catalog,
            'segment_insights': get_all_segment_insights(),
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
            'sms_balance': sms_balance,
            'phonebook_id': phonebook_users_id(),
            'marketing_stats': get_marketing_dashboard_stats(sms_credit=sms_credit),
            'recovery_flow_bridge': get_recovery_flow_bridge_stats(days=30),
            'marketing_analytics': analytics,
            'message_templates': MESSAGE_TEMPLATE_CATALOG,
            'automation_flows': AUTOMATION_FLOWS,
            'ai_suggestion': get_ai_campaign_suggestion(
                segment, count=preview.get('count', 0),
            ),
            'recent_campaigns': recent_campaigns,
            'timeline_events': timeline_events,
            'timeline_campaign': timeline_campaign,
            'segment_meta': next((c for c in catalog if c['key'] == segment), catalog[0]),
            'marketing_analytics_json': json.dumps(
                analytics, ensure_ascii=False, default=str,
            ),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        if request.POST.get('confirm_send') != '1':
            messages.error(request, 'برای ارسال، تأیید قطعی را فعال کنید.')
            return redirect('admin_panel_marketing')

        segment = request.POST.get('segment_key') or 'pending_orders'
        seg_meta = SEGMENT_REGISTRY.get(segment) or {}
        if seg_meta.get('preview_only') or not seg_meta.get('send_enabled', True):
            messages.error(request, 'این سگمنت فقط پیش‌نمایش است؛ ارسال فعال نیست.')
            return redirect(f'{reverse("admin_panel_marketing")}?segment={segment}')

        selected_phones = [
            p.strip() for p in request.POST.getlist('selected_phones') if (p or '').strip()
        ]
        if not selected_phones:
            messages.error(request, 'حداقل یک گیرنده را برای ارسال انتخاب کنید.')
            return redirect('admin_panel_marketing')
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
        return JsonResponse(
            {'ok': True, **data},
            encoder=DjangoJSONEncoder,
            json_dumps_params={'ensure_ascii': False},
        )


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


class AdminAcademyView(StaffRequiredMixin, TemplateView):
    """آمار ویدیوهای آکادمی — بازدید، تکمیل و مسیرها."""

    template_name = 'accounts/admin_academy.html'

    def get_context_data(self, **kwargs):
        from django.db.models import Sum

        from workspace.academy.models import AcademyVideo, UserVideoProgress
        from workspace.academy.services.backfill_views import backfill_academy_views

        # یک‌بار: اگر views_count هنوز خالی است ولی پیشرفت تاریخی داریم، بازسازی کن
        views_sum = AcademyVideo.objects.aggregate(t=Sum('views_count'))['t'] or 0
        if views_sum == 0 and UserVideoProgress.objects.exists():
            backfill_academy_views(replace_daily=True)

        ctx = super().get_context_data(**kwargs)
        status = self.request.GET.get('status', 'all')
        if status not in ('all', 'public', 'private', 'inactive'):
            status = 'all'

        days = _parse_int(self.request.GET.get('days'), 30, minimum=7, maximum=90)
        stats = get_academy_dashboard_stats()
        analytics = get_academy_analytics_chart(days=days)
        ctx.update({
            'academy_stats': stats,
            'academy_videos': get_academy_videos_table(limit=80, status=status),
            'status_filter': status,
            'analytics_days': days,
            'academy_pulse': analytics.get('pulse') or {},
            'academy_traffic': analytics.get('traffic') or {},
            'academy_analytics_json': json.dumps(analytics, ensure_ascii=False, default=str),
        })
        return ctx


class AdminAcademyAnalyticsJsonView(StaffRequiredMixin, View):
    """داده JSON نمودارهای Analytics آکادمی."""

    def get(self, request):
        days = _parse_int(request.GET.get('days'), 30, minimum=7, maximum=90)
        payload = get_academy_analytics_chart(days=days)
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


class AdminAcademyJsonView(StaffRequiredMixin, View):
    """خروجی JSON آمار آکادمی."""

    def get(self, request):
        days = _parse_int(request.GET.get('days'), 30, minimum=7, maximum=90)
        status = request.GET.get('status', 'all')
        if status not in ('all', 'public', 'private', 'inactive'):
            status = 'all'
        videos_limit = _parse_int(request.GET.get('videos_limit'), 1000, minimum=1, maximum=5000)

        payload = build_academy_stats_json(days=days, status=status, videos_limit=videos_limit)
        download = request.GET.get('download', '0') not in ('0', 'false', 'no', '')
        response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False, 'indent': 2})
        if download:
            stamp = timezone.now().strftime('%Y%m%d_%H%M')
            response['Content-Disposition'] = (
                f'attachment; filename="academy-stats-{days}d-{stamp}.json"'
            )
        return response


class AdminBlogView(StaffRequiredMixin, TemplateView):
    """مدیریت مقالات، آمار بازدید و درون‌ریزی JSON."""

    template_name = 'accounts/admin_blog.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        status = self.request.GET.get('status', 'all')
        if status not in ('all', 'published', 'draft'):
            status = 'all'

        days = _parse_int(self.request.GET.get('days'), 30, minimum=7, maximum=90)
        stats = get_blog_dashboard_stats()
        analytics = get_blog_analytics_chart(days=days)
        ctx.update({
            'blog_stats': stats,
            'blog_posts': get_blog_posts_table(limit=80, status=status),
            'status_filter': status,
            'analytics_days': days,
            'blog_pulse': analytics.get('pulse') or {},
            'blog_traffic': analytics.get('traffic') or {},
            'blog_analytics_json': json.dumps(analytics, ensure_ascii=False, default=str),
            'sample_json_url': '/static/samples/article-import-sample.json',
            'systematic_eligible_count': count_eligible_datasets(),
        })
        return ctx


class AdminBlogAnalyticsJsonView(StaffRequiredMixin, View):
    """داده JSON نمودارهای Analytics — برای تغییر بازه بدون reload."""

    def get(self, request):
        days = _parse_int(request.GET.get('days'), 30, minimum=7, maximum=90)
        payload = get_blog_analytics_chart(days=days)
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


class AdminBlogJsonView(StaffRequiredMixin, View):
    """خروجی JSON آمار مقالات."""

    def get(self, request):
        days = _parse_int(request.GET.get('days'), 30, minimum=7, maximum=90)
        status = request.GET.get('status', 'all')
        if status not in ('all', 'published', 'draft'):
            status = 'all'
        posts_limit = _parse_int(request.GET.get('posts_limit'), 1000, minimum=1, maximum=5000)

        payload = build_blog_stats_json(days=days, status=status, posts_limit=posts_limit)
        download = request.GET.get('download', '0') not in ('0', 'false', 'no', '')
        response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False, 'indent': 2})
        if download:
            stamp = timezone.now().strftime('%Y%m%d_%H%M')
            response['Content-Disposition'] = (
                f'attachment; filename="blog-stats-{days}d-{stamp}.json"'
            )
        return response


class AdminBlogImportPreviewView(StaffRequiredMixin, View):
    """اعتبارسنجی JSON مقاله قبل از درون‌ریزی."""

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'errors': ['JSON نامعتبر است.']}, status=400)

        preview = validate_article_payload(payload)
        return JsonResponse({
            'ok': preview.ok,
            'errors': preview.errors,
            'warnings': preview.warnings,
            'action': preview.action,
            'existing_slug': preview.existing_slug,
            'article': {
                'slug_base': (preview.article or {}).get('slug_base'),
                'title': (preview.article or {}).get('title'),
                'excerpt': (preview.article or {}).get('excerpt'),
                'tag_count': len((preview.article or {}).get('tags') or []),
                'category': (preview.article or {}).get('category', {}).get('name'),
            } if preview.article else None,
        })


class AdminBlogImportView(StaffRequiredMixin, View):
    """درون‌ریزی مقاله از JSON."""

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'errors': ['JSON نامعتبر است.']}, status=400)

        try:
            post, action = import_article_from_payload(payload)
        except ArticleImportError as exc:
            return JsonResponse({'ok': False, 'errors': [str(exc)]}, status=400)

        action_labels = {
            'created': 'ایجاد شد',
            'updated': 'به‌روزرسانی شد',
            'skipped': 'رد شد (از قبل موجود)',
        }
        return JsonResponse({
            'ok': True,
            'action': action,
            'action_label': action_labels.get(action, action),
            'post': {
                'id': post.id,
                'title': post.title,
                'slug': post.slug,
                'url': post.get_absolute_url(),
                'is_published': post.is_published,
                'admin_edit_url': f'/admin/blog/post/{post.id}/change/',
            },
        })


class AdminPlanConversionView(StaffRequiredMixin, TemplateView):
    """آنالیز نرخ تبدیل پلن‌ها — قیف خرید، کوهورت و سهم فروش."""

    template_name = 'accounts/admin_plan_conversion.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        data = get_plan_conversion_context(days=days)
        ctx.update(data)
        ctx['summary'] = data['summary']
        chart_payload = dict(data['charts'])
        chart_payload['behavior'] = data.get('behavior') or {}
        chart_payload['predictive'] = data.get('predictive') or {}
        chart_payload['time_intelligence'] = {
            k: v for k, v in (data.get('time_intelligence') or {}).items()
            if k != 'series'
        }
        ctx['plan_conversion_json'] = json.dumps(chart_payload, ensure_ascii=False, default=str)
        ctx['admin_panel_range_key'] = range_key
        return ctx


class AdminPlanConversionJsonView(StaffRequiredMixin, View):
    """خروجی JSON کامل آنالیز تبدیل پلن‌ها."""

    def get(self, request):
        days, _range_key = parse_admin_panel_range(request)
        payload = build_plan_conversion_json(days=days)
        download = request.GET.get('download', '0') not in ('0', 'false', 'no', '')
        response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False, 'indent': 2})
        if download:
            stamp = timezone.now().strftime('%Y%m%d_%H%M')
            response['Content-Disposition'] = (
                f'attachment; filename="plan-conversion-{days}d-{stamp}.json"'
            )
        return response


class AdminRecoveryCenterView(StaffRequiredMixin, TemplateView):
    """Recovery Center — قیف بازیابی، Journey، Health و Explorer."""

    template_name = 'accounts/admin_recovery_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        page = _parse_int(self.request.GET.get('page'), 1, minimum=1, maximum=9999)
        data = get_recovery_center_context(days=days, page=page)
        ctx.update(data)
        ctx['recovery_center_json'] = json.dumps(
            build_recovery_center_json(days=days, page=page),
            ensure_ascii=False,
            default=str,
        )
        ctx['page'] = page
        ctx['admin_panel_range_key'] = range_key
        return ctx


class AdminRecoveryCenterJsonView(StaffRequiredMixin, View):
    """JSON data product — Recovery Center."""

    def get(self, request):
        days, _range_key = parse_admin_panel_range(request)
        page = _parse_int(request.GET.get('page'), 1, minimum=1, maximum=9999)
        payload = build_recovery_center_json(days=days, page=page)
        download = request.GET.get('download', '0') not in ('0', 'false', 'no', '')
        response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False, 'indent': 2})
        if download:
            stamp = timezone.now().strftime('%Y%m%d_%H%M')
            response['Content-Disposition'] = (
                f'attachment; filename="recovery-center-{days}d-{stamp}.json"'
            )
        return response


class AdminSalesCenterView(StaffRequiredMixin, TemplateView):
    """مرکز فروش — KPI، روند، ترکیب و جداول سفارش."""

    template_name = 'accounts/admin_sales_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        focus = (self.request.GET.get('focus') or '').strip() or None
        data = get_sales_center_context(days=days, compare=compare, focus=focus)
        data['export_links'] = [item for item in data.get('export_links', []) if can_export_report(self.request.user, item['key'])]
        for card in data.get('kpi_cards', []):
            spark = card.get('sparkline')
            card['sparkline_json'] = json.dumps(spark) if spark else ''
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['charts_json'] = json.dumps(data['charts'], ensure_ascii=False)
        return ctx


def _card_transfer_redirect(request):
    next_url = (request.POST.get('next') or '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(reverse('admin_panel_sales') + '#sales-card-transfers')


class AdminCardTransferApproveView(StaffRequiredMixin, View):
    """تأیید پرداخت کارت‌به‌کارت از پنل مدیریت — POST only."""

    http_method_names = ['post']

    def post(self, request, pk):
        from shop.models import CardTransferSubmission
        from shop.services.card_transfer_workflow import CardTransferWorkflowError
        from shop.services.order_fulfillment import approve_card_transfer

        submission = get_object_or_404(
            CardTransferSubmission.objects.select_related('order'),
            pk=pk,
        )
        try:
            approve_card_transfer(submission, request.user)
            messages.success(
                request,
                'پرداخت تأیید شد و لایسنس کاربر به‌صورت خودکار فعال شد.',
            )
        except CardTransferWorkflowError as exc:
            messages.error(request, exc.message)
        except Exception:
            logger.exception('card transfer approve failed submission_id=%s', pk)
            messages.error(
                request,
                'فعال‌سازی انجام نشد؛ تغییری ثبت نشد. دوباره تلاش کنید یا لاگ را بررسی کنید.',
            )
        return _card_transfer_redirect(request)


class AdminCardTransferRejectView(StaffRequiredMixin, View):
    """رد پرداخت کارت‌به‌کارت از پنل مدیریت — POST only."""

    http_method_names = ['post']

    def post(self, request, pk):
        from shop.models import CardTransferSubmission
        from shop.services.card_transfer_workflow import CardTransferWorkflowError
        from shop.services.order_fulfillment import reject_card_transfer

        submission = get_object_or_404(
            CardTransferSubmission.objects.select_related('order'),
            pk=pk,
        )
        admin_note = (request.POST.get('admin_note') or '').strip()
        try:
            reject_card_transfer(submission, request.user, admin_note)
            messages.warning(request, 'پرداخت کارت‌به‌کارت رد شد.')
        except CardTransferWorkflowError as exc:
            messages.error(request, exc.message)
        except Exception:
            logger.exception('card transfer reject failed submission_id=%s', pk)
            messages.error(request, 'رد پرداخت انجام نشد. دوباره تلاش کنید.')
        return _card_transfer_redirect(request)


class AdminUsersCenterView(StaffRequiredMixin, TemplateView):
    """مرکز کاربران — KPI، روند و مدیریت AJAX."""

    template_name = 'accounts/admin_users_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        data = get_users_center_context(days=days, compare=compare)
        data['export_links'] = [item for item in data.get('export_links', []) if can_export_report(self.request.user, item['key'])]
        for card in data.get('kpi_cards', []):
            card['sparkline_json'] = json.dumps(card.get('sparkline', []))
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['charts_json'] = json.dumps(data['charts'], ensure_ascii=False)
        return ctx


class AdminLicensesCenterView(StaffRequiredMixin, TemplateView):
    """مرکز لایسنس — KPI، تمدید و جداول."""

    template_name = 'accounts/admin_licenses_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        data = get_licenses_center_context(days=days, compare=compare)
        data['export_links'] = [item for item in data.get('export_links', []) if can_export_report(self.request.user, item['key'])]
        for card in data.get('kpi_cards', []):
            card['sparkline_json'] = json.dumps(card.get('sparkline', []))
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['charts_json'] = json.dumps(data['charts'], ensure_ascii=False)
        return ctx


class AdminDivarContactSettingsView(StaffRequiredMixin, View):
    """ذخیره وضعیت انتشار دریافت شماره از دیوار — فقط Superuser."""

    def post(self, request):
        from accounts.services.divar_contact_admin import save_divar_contact_rollout

        rollout_mode = (request.POST.get('rollout_mode') or '').strip()
        result = save_divar_contact_rollout(rollout_mode=rollout_mode, user=request.user)
        if result.get('ok'):
            messages.success(request, 'تنظیمات دریافت شماره از دیوار ذخیره شد.')
        else:
            messages.error(request, result.get('error') or 'ذخیره ناموفق بود.')
        return redirect('admin_panel_operations')


class AdminOperationsCenterView(StaffRequiredMixin, TemplateView):
    """مرکز عملیات — سلامت سیستم، SMS و بک‌آپ."""

    template_name = 'accounts/admin_operations_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        data = get_operations_center_context(days=days, compare=compare)
        for card in data.get('kpi_cards', []):
            card['sparkline_json'] = json.dumps(card.get('sparkline', []))
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['charts_json'] = json.dumps(data['charts'], ensure_ascii=False)
        return ctx


class AdminSupportCenterView(StaffRequiredMixin, TemplateView):
    """مرکز پشتیبانی — تیکت و امور مالی معلق."""

    template_name = 'accounts/admin_support_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        focus = (self.request.GET.get('focus') or '').strip() or None
        data = get_support_center_context(days=days, compare=compare, focus=focus)
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['charts_json'] = json.dumps(data['charts'], ensure_ascii=False)
        return ctx


class AdminActivityCenterView(StaffRequiredMixin, TemplateView):
    """مرکز فعالیت — Timeline رویدادهای سیستم."""

    template_name = 'accounts/admin_activity_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        activity_type = self.request.GET.get('type', 'all')
        try:
            page = max(1, int(self.request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        data = get_activity_center_context(
            days=days,
            activity_type=activity_type,
            page=page,
            compare=compare,
        )
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['admin_panel_compare'] = compare
        return ctx


class AdminWindowsCenterView(StaffRequiredMixin, TemplateView):
    """مرکز ویندوز — Funnel نصب و فعال‌سازی."""

    template_name = 'accounts/admin_windows_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        try:
            page = max(1, int(self.request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        data = get_windows_center_context(days=days, page=page, compare=compare)
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['admin_panel_compare'] = compare
        return ctx


class AdminAndroidCenterView(StaffRequiredMixin, TemplateView):
    """مرکز اندروید — Funnel نصب، فعال‌سازی و استفاده."""

    template_name = 'accounts/admin_android_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        try:
            page = max(1, int(self.request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        data = get_android_center_context(days=days, page=page, compare=compare)
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['admin_panel_compare'] = compare
        return ctx


class AdminAndroidSmsPreviewView(StaffRequiredMixin, View):
    """پیش‌نمایش گیرندگان نسخه قدیمی اندروید."""

    def get(self, request):
        try:
            data = preview_segment('android_outdated', sample_size=10)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse(
            {'ok': True, **data},
            encoder=DjangoJSONEncoder,
            json_dumps_params={'ensure_ascii': False},
        )


class AdminAndroidSmsSendView(StaffRequiredMixin, View):
    """ارسال پیامک Faraz به کاربران با نسخه قدیمی اندروید."""

    def post(self, request):
        if request.POST.get('confirm_send') != '1':
            messages.error(request, 'برای ارسال، تأیید قطعی را فعال کنید.')
            return redirect('admin_panel_android')

        selected_phones = [
            p.strip() for p in request.POST.getlist('selected_phones') if (p or '').strip()
        ]
        if not selected_phones:
            messages.error(request, 'حداقل یک گیرنده را برای ارسال انتخاب کنید.')
            return redirect('admin_panel_android')

        message_template = (
            request.POST.get('message_template')
            or SEGMENT_DEFAULT_TEMPLATES.get('android_outdated', '')
        )
        dedupe_days = _parse_int(request.POST.get('dedupe_days'), 7, minimum=0, maximum=90) or 0

        try:
            campaign = create_campaign_draft(
                name=request.POST.get('name') or 'یادآوری آپدیت اندروید',
                segment_key='android_outdated',
                message_template=message_template,
                discount_mode='none',
                created_by=request.user,
                dedupe_days=dedupe_days,
            )
            run_campaign_send(campaign, selected_phones=selected_phones)
        except MarketingSendError as exc:
            messages.error(request, exc.message)
            return redirect('admin_panel_android')
        except Exception:
            messages.error(request, 'خطای غیرمنتظره در ارسال پیامک.')
            return redirect('admin_panel_android')

        messages.success(
            request,
            f'پیامک آپدیت اندروید ارسال شد: {campaign.sent_count} موفق، '
            f'{campaign.failed_count} ناموفق، {campaign.skipped_count} ردشده.',
        )
        return redirect('admin_panel_marketing_detail', pk=campaign.pk)


class AdminAiCenterView(StaffRequiredMixin, TemplateView):
    """مرکز هوش مصنوعی — مصرف و observability."""

    template_name = 'accounts/admin_ai_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        top_mode = (self.request.GET.get('top_mode') or 'tokens').strip()
        log_filters = {
            'feature': (self.request.GET.get('feature') or '').strip() or None,
            'status': (self.request.GET.get('status') or '').strip() or None,
            'provider': (self.request.GET.get('provider') or '').strip() or None,
        }
        data = build_ai_center_context(
            days=days,
            compare=compare,
            top_mode=top_mode,
            log_filters=log_filters,
        )
        for card in data.get('range_kpi_cards', []):
            card['sparkline_json'] = '[]'
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['admin_panel_compare'] = compare
        ctx['charts_json'] = json.dumps(data['charts'], ensure_ascii=False, default=str)
        return ctx


class AdminAiStatsJsonView(StaffRequiredMixin, View):
    """JSON آمار مرکز AI — با cache کوتاه."""

    def get(self, request):
        days, _range_key = parse_admin_panel_range(request)
        compare = request.GET.get('compare') == '1'
        top_mode = (request.GET.get('top_mode') or 'tokens').strip()
        log_filters = {
            'feature': (request.GET.get('feature') or '').strip() or None,
            'status': (request.GET.get('status') or '').strip() or None,
            'provider': (request.GET.get('provider') or '').strip() or None,
        }
        payload = build_ai_stats_json(
            days=days,
            compare=compare,
            top_mode=top_mode,
            log_filters=log_filters,
        )
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


class AdminCrmCenterView(StaffRequiredMixin, TemplateView):
    """مرکز CRM — Adoption و عملیات فایلینگ."""

    template_name = 'accounts/admin_crm_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        data = get_crm_center_context(days=days, compare=compare)
        for card in data.get('range_kpi_cards', []):
            card['sparkline_json'] = '[]'
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['admin_panel_compare'] = compare
        ctx['charts_json'] = json.dumps(data['charts'], ensure_ascii=False)
        return ctx


class AdminAffiliatesCenterView(StaffRequiredMixin, TemplateView):
    """مرکز همکاری در فروش — مشاوران، کمیسیون و برداشت."""

    template_name = 'accounts/admin_affiliates_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        data = get_affiliates_center_context(days=days, compare=compare)
        for card in data.get('range_kpi_cards', []) + data.get('snapshot_kpi_cards', []):
            card['sparkline_json'] = '[]'
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['admin_panel_compare'] = compare
        return ctx


class AdminExportsCenterView(StaffRequiredMixin, TemplateView):
    """مرکز خروجی — کاتالوگ گزارش‌های Excel."""

    template_name = 'accounts/admin_exports_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        compare = self.request.GET.get('compare') == '1'
        category = self.request.GET.get('category', 'all') or 'all'
        data = get_exports_center_context(days=days, category=category, compare=compare, user=self.request.user)
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['admin_panel_compare'] = compare
        return ctx


class AdminManagementAssistantView(StaffRequiredMixin, TemplateView):
    """دستیار مدیریت — پیشنهادها، خودکارسازی و تاریخچه."""

    template_name = 'accounts/admin_management_assistant.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days, range_key = parse_admin_panel_range(self.request)
        tab = self.request.GET.get('tab', 'suggestions')
        data = get_management_assistant_context(tab=tab)
        ctx.update(data)
        ctx['chart_days'] = days
        ctx['admin_panel_range_key'] = range_key
        ctx['automation_rules_json'] = json.dumps(
            data.get('automation_rules', []),
            ensure_ascii=False,
            default=str,
        )
        return ctx


class AdminManagementAssistantPreviewView(StaffRequiredMixin, View):
    """پیش‌نمایش گیرندگان یک پیشنهاد."""

    def get(self, request):
        insight_key = (request.GET.get('insight') or '').strip()
        payload = preview_insight_recipients(insight_key)
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


class AdminManagementAssistantSendView(StaffRequiredMixin, View):
    """ارسال پیام برای یک پیشنهاد مدیریتی."""

    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

        insight_key = (body.get('insight_key') or '').strip()
        message_template = (body.get('message_template') or '').strip()
        selected_phones = body.get('selected_phones') or None
        if selected_phones is not None:
            selected_phones = [str(p).strip() for p in selected_phones if str(p).strip()]

        if body.get('confirm_send') != '1':
            return JsonResponse({'ok': False, 'error': 'تأیید ارسال لازم است.'}, status=400)

        try:
            result = send_insight_campaign(
                insight_key=insight_key,
                message_template=message_template,
                created_by=request.user,
                selected_phones=selected_phones,
            )
        except MarketingSendError as exc:
            return JsonResponse({'ok': False, 'error': exc.message}, status=400)

        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})


class AdminManagementAssistantAutomationView(StaffRequiredMixin, View):
    """فعال/غیرفعال کردن خودکارسازی."""

    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

        rule_key = (body.get('rule_key') or '').strip()
        active = bool(body.get('active'))
        result = toggle_automation_rule(rule_key=rule_key, active=active, user=request.user)
        status = 200 if result.get('ok') else 400
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False}, status=status)


class AdminManagementAssistantAutomationDetailView(StaffRequiredMixin, View):
    """جزئیات کامل یک Rule — مرکز کنترل Automation."""

    def get(self, request):
        rule_key = (request.GET.get('rule_key') or '').strip()
        payload = get_automation_rule_detail(rule_key)
        status = 200 if payload.get('ok') else 404
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False}, status=status)


class AdminManagementAssistantAutomationPreviewView(StaffRequiredMixin, View):
    """پیش‌نمایش مخاطبان یک Rule."""

    def get(self, request):
        rule_key = (request.GET.get('rule_key') or '').strip()
        payload = preview_automation_rule(rule_key)
        status = 200 if payload.get('ok') else 404
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False}, status=status)


class AdminManagementAssistantAutomationRunView(StaffRequiredMixin, View):
    """اجرای دستی یا Dry Run یک Rule."""

    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

        rule_key = (body.get('rule_key') or '').strip()
        dry_run = bool(body.get('dry_run'))
        force = body.get('force', True)
        if body.get('confirm_run') != '1':
            return JsonResponse({'ok': False, 'error': 'تأیید اجرا لازم است.'}, status=400)

        result = run_automation_rule_now(rule_key=rule_key, dry_run=dry_run, force=bool(force))
        status = 200 if result.get('ok') else 400
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False}, status=status)


class AdminManagementAssistantAutomationSettingsView(StaffRequiredMixin, View):
    """ذخیره تنظیمات Safe یک Rule."""

    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

        rule_key = (body.get('rule_key') or '').strip()
        if body.get('confirm_save') != '1':
            return JsonResponse({'ok': False, 'error': 'تأیید ذخیره لازم است.'}, status=400)

        fields = {}
        for key in (
            'message_template',
            'cooldown_days',
            'max_recipients_per_run',
            'cadence',
            'quiet_hours_start',
            'quiet_hours_end',
        ):
            if key in body:
                fields[key] = body[key]

        result = update_automation_rule_settings(
            rule_key=rule_key,
            reset_template=bool(body.get('reset_template')),
            updated_by=request.user,
            **fields,
        )
        status = 200 if result.get('ok') else 400
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False}, status=status)


class AdminManagementAssistantAutomationMessagePreviewView(StaffRequiredMixin, View):
    """پیش‌نمایش متن پیام Rule."""

    def get(self, request):
        rule_key = (request.GET.get('rule_key') or '').strip()
        message_template = (request.GET.get('message_template') or '').strip()
        mode = (request.GET.get('mode') or 'sample').strip()
        try:
            recipient_index = int(request.GET.get('recipient_index') or 0)
        except (TypeError, ValueError):
            recipient_index = 0
        payload = preview_rule_message(
            rule_key,
            message_template=message_template,
            mode=mode,
            recipient_index=recipient_index,
        )
        status = 200 if payload.get('ok') else 400
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False}, status=status)


class AdminManagementAssistantAutomationTestSendView(StaffRequiredMixin, View):
    """ارسال آزمایشی پیام Rule به staff."""

    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

        rule_key = (body.get('rule_key') or '').strip()
        message_template = (body.get('message_template') or '').strip()
        if body.get('confirm_send') != '1':
            return JsonResponse({'ok': False, 'error': 'تأیید ارسال لازم است.'}, status=400)

        result = send_automation_test_message(
            rule_key=rule_key,
            user=request.user,
            message_template=message_template,
        )
        status = 200 if result.get('ok') else 400
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False}, status=status)
