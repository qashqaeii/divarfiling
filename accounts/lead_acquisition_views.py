"""ویوهای عمومی و ادمین مرکز جذب سرنخ."""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.admin_views import StaffRequiredMixin
from accounts.models import (
    AcquisitionRun,
    CampaignMessage,
    LeadCampaign,
    LeadImportBatch,
    LeadList,
    LeadTouchpoint,
    MarketingLead,
)
from accounts.services.acquisition_automation import schedule_due_campaigns
from accounts.services.acquisition_automation_ui import (
    AutomationUIError,
    CATEGORY_CHOICES,
    automation_campaigns_for_ui,
    automation_overview_stats,
    automation_runs_for_ui,
    create_automation_campaign_from_form,
    list_automation_cities,
    list_districts_for_city,
    places_config_available,
    queue_automation_run_now,
    reset_automation_schedule,
    toggle_automation_campaign,
    update_automation_campaign_from_form,
)
from accounts.services.lead_attribution import record_touchpoint
from accounts.services.lead_campaign_send import (
    DEFAULT_STEP1_A,
    DEFAULT_STEP1_B,
    DEFAULT_STEP2,
    DEFAULT_STEP3,
    LeadCampaignError,
    auto_create_campaign_for_import,
    batches_pending_campaign,
    bulk_update_message_templates,
    create_acquisition_campaign,
    delete_lead_campaign,
    enroll_all_eligible,
    enroll_campaigns_for_full_send,
    enroll_pilot,
    ensure_campaign_for_batch,
    eligible_count_for_list,
    get_global_message_templates,
    get_step1_variant_templates,
    pending_totals_for_campaigns,
    reset_campaign_for_retry,
    save_global_variant_templates,
    send_batch_size,
    send_campaign_step,
    send_campaigns_step_chunk,
    sms_cost_per_part_rial,
    update_acquisition_campaign,
)
from accounts.services.lead_funnel import (
    acquisition_dashboard_charts,
    campaign_funnel,
    overview_stats,
)
from accounts.services.lead_import import (
    LeadImportError,
    commit_import_batch,
    create_preview_batch,
    preview_phone_detector_json,
    region_lists_with_batches,
)
from accounts.services.lead_tokens import COOKIE_NAME, cookie_secure_kwargs, hash_ip, truncate_user_agent

logger = logging.getLogger(__name__)

SESSION_PREVIEW_KEY = 'lead_import_preview_rows'
SESSION_BULK_PREVIEW_KEY = 'lead_import_bulk_previews'


def _serialize_preview_rows(preview_rows) -> list:
    return [
        {
            'phone': r.phone,
            'name': r.name,
            'district': r.district,
            'category': r.category,
            'outcome': r.outcome,
            'lead_type': r.lead_type,
            'confidence': str(r.confidence),
        }
        for r in preview_rows
    ]


def _preview_item_from_session(item: dict) -> dict:
    return {
        'batch_id': item.get('batch_id'),
        'file_hash': item.get('file_hash'),
        'stats': item.get('stats') or {},
        'metadata': item.get('metadata') or {},
        'filename': (item.get('metadata') or {}).get('original_filename') or item.get('filename') or '—',
    }


def _lac_redirect(fragment: str = ''):
    url = reverse('admin_panel_lead_acquisition')
    if fragment:
        url = f'{url}#{fragment.lstrip("#")}'
    return HttpResponseRedirect(url)


def _parse_campaign_ids_payload(payload) -> list[int]:
    raw = payload.get('campaign_ids') if hasattr(payload, 'get') else None
    if raw is None:
        return []
    if isinstance(raw, (str, int)):
        raw = [raw]
    ids: list[int] = []
    for item in raw:
        try:
            cid = int(item)
        except (TypeError, ValueError):
            continue
        if cid > 0:
            ids.append(cid)
    return list(dict.fromkeys(ids))


def _parse_json_or_post(request) -> dict:
    if request.content_type and 'application/json' in request.content_type:
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LeadCampaignError('درخواست JSON نامعتبر است.', code='bad_json') from exc
        if not isinstance(body, dict):
            raise LeadCampaignError('ساختار JSON نامعتبر است.', code='bad_json')
        return body
    return request.POST.dict() if hasattr(request.POST, 'dict') else dict(request.POST)


class LeadClickRedirectView(View):
    """ /s/t/<click_token>/ — ثبت کلیک + کوکی + redirect به لندینگ."""

    def get(self, request, click_token: str):
        msg = (
            CampaignMessage.objects.select_related(
                'lead', 'campaign', 'variant', 'step',
            )
            .filter(click_token=click_token)
            .first()
        )
        if not msg:
            raise Http404('لینک نامعتبر است')

        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        if not ip:
            ip = request.META.get('REMOTE_ADDR') or ''
        record_touchpoint(
            lead=msg.lead,
            event_type=LeadTouchpoint.EventType.CLICK,
            message=msg,
            user=request.user if request.user.is_authenticated else None,
            ip_hash=hash_ip(ip),
            user_agent=truncate_user_agent(request.META.get('HTTP_USER_AGENT')),
        )
        record_touchpoint(
            lead=msg.lead,
            event_type=LeadTouchpoint.EventType.LANDING_VIEW,
            message=msg,
            user=request.user if request.user.is_authenticated else None,
            ip_hash=hash_ip(ip),
            user_agent=truncate_user_agent(request.META.get('HTTP_USER_AGENT')),
        )

        target = (msg.campaign.landing_url or 'https://divarfiling.ir/').strip()
        response = HttpResponseRedirect(target)
        response.set_cookie(COOKIE_NAME, msg.click_token, **cookie_secure_kwargs())
        return response


class AdminLeadAcquisitionView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_lead_acquisition.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campaigns = list(
            LeadCampaign.objects.filter(kind=LeadCampaign.Kind.ACQUISITION)
            .select_related('lead_list', 'created_by')
            .order_by('-created_at')[:50]
        )
        funnels = [campaign_funnel(c) for c in campaigns]
        campaign_edit = {}
        for c in campaigns:
            tpl = get_step1_variant_templates(c)
            campaign_edit[str(c.pk)] = {
                'name': c.name,
                'landing_url': c.landing_url or '',
                'pilot_per_variant': c.pilot_per_variant,
                'is_pilot': c.is_pilot,
                'variant_a': tpl['A'],
                'variant_b': tpl['B'],
            }
        ctx.update({
            'overview': overview_stats(),
            'lac_charts_json': json.dumps(
                acquisition_dashboard_charts(campaigns, funnels),
                ensure_ascii=False,
            ),
            'batches': LeadImportBatch.objects.order_by('-created_at')[:30],
            'region_lists': region_lists_with_batches(limit=40),
            'lists': LeadList.objects.order_by('city', 'district', '-created_at')[:40],
            'campaigns': campaigns,
            'funnels': funnels,
            'preview': self.request.session.get(SESSION_PREVIEW_KEY),
            'bulk_previews': [
                _preview_item_from_session(i)
                for i in (self.request.session.get(SESSION_BULK_PREVIEW_KEY) or [])
            ],
            'leads_sample': MarketingLead.objects.order_by('-updated_at')[:25],
            'default_variant_a': get_global_message_templates()['A'],
            'default_variant_b': get_global_message_templates()['B'],
            'default_step_2': get_global_message_templates()['step_2'],
            'default_step_3': get_global_message_templates()['step_3'],
            'factory_templates_json': json.dumps({
                'variant_a': DEFAULT_STEP1_A,
                'variant_b': DEFAULT_STEP1_B,
                'step_2': DEFAULT_STEP2,
                'step_3': DEFAULT_STEP3,
            }, ensure_ascii=False),
            'sms_cost_per_part_rial': sms_cost_per_part_rial(),
            'campaign_edit_json': json.dumps(campaign_edit, ensure_ascii=False),
            'all_campaign_ids_json': json.dumps([c.pk for c in campaigns], ensure_ascii=False),
            'batches_pending_campaign': batches_pending_campaign(limit=20),
            'send_progress_start_url': reverse('admin_panel_lead_send_progress_start'),
            'send_progress_tick_url': reverse('admin_panel_lead_send_progress_tick'),
            'bulk_templates_url': reverse('admin_panel_lead_bulk_templates'),
            'automation_stats': automation_overview_stats(),
            'automation_campaigns': automation_campaigns_for_ui(limit=30),
            'automation_runs': automation_runs_for_ui(limit=25),
            'automation_cities': list_automation_cities(),
            'automation_category_choices': CATEGORY_CHOICES,
            'automation_places_url': reverse('admin_panel_lead_automation_places_json'),
            'automation_places_ok': places_config_available(),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action') or ''
        try:
            if action == 'import_preview':
                return self._import_preview(request)
            if action == 'import_commit':
                return self._import_commit(request)
            if action == 'import_commit_bulk':
                return self._import_commit_bulk(request)
            if action == 'import_discard':
                return self._import_discard(request)
            if action == 'create_campaign_from_batch':
                return self._create_campaign_from_batch(request)
            if action == 'create_campaigns_pending':
                return self._create_campaigns_pending(request)
            if action == 'create_campaign':
                return self._create_campaign(request)
            if action == 'update_campaign':
                return self._update_campaign(request)
            if action == 'enroll_pilot':
                return self._enroll_pilot(request)
            if action == 'send_step':
                return self._send_step(request)
            if action == 'retry_failed':
                return self._retry_failed(request)
            if action == 'reset_campaign':
                return self._reset_campaign(request)
            if action == 'delete_campaign':
                return self._delete_campaign(request)
            if action == 'bulk_campaigns':
                return self._bulk_campaigns(request)
            if action == 'create_automation_campaign':
                return self._create_automation_campaign(request)
            if action == 'update_automation_campaign':
                return self._update_automation_campaign(request)
            if action == 'toggle_automation_campaign':
                return self._toggle_automation_campaign(request)
            if action == 'queue_automation_run':
                return self._queue_automation_run(request)
            if action == 'reset_automation_schedule':
                return self._reset_automation_schedule(request)
            if action == 'run_automation_scheduler':
                return self._run_automation_scheduler(request)
        except (LeadImportError, LeadCampaignError, AutomationUIError) as exc:
            messages.error(request, exc.message)
        except Exception as exc:  # noqa: BLE001
            logger.exception('lead acquisition admin error')
            messages.error(request, f'خطا: {exc}')
        fragment = 'lac-automation' if (request.POST.get('action') or '').startswith(('create_automation', 'update_automation', 'toggle_automation', 'queue_automation', 'reset_automation', 'run_automation')) else ''
        if fragment:
            return _lac_redirect(fragment)
        return redirect('admin_panel_lead_acquisition')

    def _import_preview(self, request):
        uploads = request.FILES.getlist('files') or []
        single = request.FILES.get('file')
        if single and single not in uploads:
            uploads.insert(0, single)
        if not uploads:
            messages.error(request, 'فایلی انتخاب نشده است.')
            return redirect('admin_panel_lead_acquisition')

        bulk_items = list(request.session.get(SESSION_BULK_PREVIEW_KEY) or [])
        added = 0
        skipped_dup = 0
        duplicate_batches: list[dict] = []
        last_preview = None

        for uploaded in uploads[:20]:
            raw = uploaded.read()
            preview = preview_phone_detector_json(raw, filename=uploaded.name)
            if preview.duplicate_file:
                skipped_dup += 1
                if preview.existing_batch_id:
                    duplicate_batches.append({
                        'batch_id': preview.existing_batch_id,
                        'filename': uploaded.name,
                    })
                continue
            batch = create_preview_batch(preview, uploaded_by=request.user)
            item = {
                'batch_id': batch.pk,
                'file_hash': preview.file_hash,
                'stats': preview.stats,
                'metadata': preview.metadata,
                'filename': uploaded.name,
                'rows': _serialize_preview_rows(preview.rows),
            }
            bulk_items = [i for i in bulk_items if i.get('batch_id') != batch.pk]
            bulk_items.append(item)
            last_preview = item
            added += 1

        request.session[SESSION_BULK_PREVIEW_KEY] = bulk_items
        if last_preview:
            request.session[SESSION_PREVIEW_KEY] = last_preview

        if added == 0:
            messages.error(request, 'هیچ فایل جدیدی برای پیش‌نمایش نبود (تکراری یا نامعتبر).')
        elif added == 1:
            stats = last_preview['stats']
            messages.success(
                request,
                f'پیش‌نمایش آماده — قابل ورود: {stats.get("eligible", 0)}',
            )
        else:
            total_eligible = sum(i['stats'].get('eligible', 0) for i in bulk_items[-added:])
            messages.success(
                request,
                f'{added} فایل در صف پیش‌نمایش — مجموع قابل ورود: {total_eligible}',
            )
        if skipped_dup:
            messages.warning(
                request,
                f'{skipped_dup} فایل تکراری (قبلاً ثبت شده) — commit مجدد ممکن نیست؛ '
                f'از «ساخت کمپین برای فایل‌های بدون کمپین» استفاده کنید.',
            )
        if duplicate_batches and added == 0:
            request.session['lead_import_duplicate_batches'] = duplicate_batches
        return _lac_redirect('lac-import')

    def _commit_single_preview(self, request, payload: dict, *, auto_campaign: bool = True) -> dict:
        from decimal import Decimal

        from accounts.services.lead_import import PreviewRow

        batch_id = payload.get('batch_id')
        if not batch_id:
            raise LeadImportError('شناسه بچ نامعتبر است.', code='bad_batch')
        rows = [
            PreviewRow(
                phone=r['phone'],
                name=r['name'],
                district=r['district'],
                category=r['category'],
                outcome=r['outcome'],
                lead_type=r['lead_type'],
                confidence=Decimal(r.get('confidence') or '0'),
            )
            for r in payload.get('rows') or []
        ]
        result = commit_import_batch(batch_id, preview_rows=rows)
        campaign = None
        eligible = 0
        if auto_campaign:
            from accounts.models import LeadList

            lead_list = LeadList.objects.get(pk=result['list_id'])
            eligible = result.get('members_added', 0) or payload.get('stats', {}).get('eligible', 0)
            if eligible <= 0:
                eligible = eligible_count_for_list(lead_list)
            campaign = auto_create_campaign_for_import(
                lead_list=lead_list,
                batch_id=result['batch_id'],
                eligible_count=eligible,
                created_by=request.user,
            )
        result['campaign'] = campaign
        result['eligible_for_campaign'] = eligible if auto_campaign else 0
        return result

    def _import_commit(self, request):
        payload = request.session.get(SESSION_PREVIEW_KEY) or {}
        if not payload.get('batch_id'):
            messages.error(request, 'پیش‌نمایش فعالی نیست.')
            return redirect('admin_panel_lead_acquisition')
        result = self._commit_single_preview(request, payload)
        batch_id = payload.get('batch_id')
        bulk = request.session.get(SESSION_BULK_PREVIEW_KEY) or []
        request.session[SESSION_BULK_PREVIEW_KEY] = [
            i for i in bulk if i.get('batch_id') != batch_id
        ]
        request.session.pop(SESSION_PREVIEW_KEY, None)
        if request.session.get(SESSION_BULK_PREVIEW_KEY):
            request.session[SESSION_PREVIEW_KEY] = request.session[SESSION_BULK_PREVIEW_KEY][-1]

        msg = (
            f'ایمپورت ثبت شد — ایجاد: {result["created"]}، به‌روزرسانی: {result["updated"]}، '
            f'کاربر موجود: {result["existing_user_marked"]}، عضو لیست: {result["members_added"]}'
        )
        if result.get('campaign'):
            msg += f' · کمپین #{result["campaign"].pk} «{result["campaign"].name}» ساخته شد'
        elif result.get('eligible_for_campaign', 0) <= 0:
            msg += ' · کمپین ساخته نشد (سرنخ سرد/تعامل‌دار در لیست نیست)'
        messages.success(request, msg)
        return _lac_redirect('lac-campaigns')

    def _create_campaign_from_batch(self, request):
        batch_id = int(request.POST.get('batch_id') or 0)
        campaign = ensure_campaign_for_batch(batch_id, created_by=request.user)
        if campaign:
            messages.success(
                request,
                f'کمپین #{campaign.pk} «{campaign.name}» برای فایل #{batch_id} ساخته شد.',
            )
        else:
            messages.warning(
                request,
                f'کمپین برای فایل #{batch_id} ساخته نشد — سرنخ واجد شرایطی در لیست نیست.',
            )
        return _lac_redirect('lac-campaigns')

    def _create_campaigns_pending(self, request):
        pending = batches_pending_campaign(limit=50)
        if not pending:
            messages.info(request, 'همه فایل‌های ثبت‌شده کمپین دارند.')
            return _lac_redirect('lac-import')
        created = []
        skipped = 0
        for row in pending:
            try:
                campaign = ensure_campaign_for_batch(
                    row['batch'].pk,
                    created_by=request.user,
                )
            except LeadCampaignError as exc:
                messages.warning(request, f'بچ {row["batch"].pk}: {exc.message}')
                skipped += 1
                continue
            if campaign:
                created.append(campaign)
            else:
                skipped += 1
        if created:
            names = '، '.join(f'#{c.pk}' for c in created[:8])
            msg = f'{len(created)} کمپین ساخته شد: {names}'
            if skipped:
                msg += f' · {skipped} مورد رد شد'
            messages.success(request, msg)
        else:
            messages.warning(request, 'هیچ کمپین جدیدی ساخته نشد.')
        request.session.pop('lead_import_duplicate_batches', None)
        return _lac_redirect('lac-campaigns')

    def _import_commit_bulk(self, request):
        bulk = list(request.session.get(SESSION_BULK_PREVIEW_KEY) or [])
        if not bulk:
            messages.error(request, 'صف پیش‌نمایش خالی است.')
            return redirect('admin_panel_lead_acquisition')
        total_created = total_updated = total_members = 0
        campaigns_created = []
        for item in bulk:
            try:
                result = self._commit_single_preview(request, item)
            except LeadImportError as exc:
                messages.warning(request, f'بچ {item.get("batch_id")}: {exc.message}')
                continue
            total_created += result['created']
            total_updated += result['updated']
            total_members += result['members_added']
            if result.get('campaign'):
                campaigns_created.append(result['campaign'])
        request.session.pop(SESSION_BULK_PREVIEW_KEY, None)
        request.session.pop(SESSION_PREVIEW_KEY, None)
        msg = (
            f'ورود دسته‌ای — {len(bulk)} فایل · ایجاد: {total_created} · '
            f'به‌روز: {total_updated} · عضو لیست: {total_members}'
        )
        if campaigns_created:
            names = '، '.join(f'#{c.pk}' for c in campaigns_created[:5])
            msg += f' · کمپین‌های جدید: {names}'
        elif total_members == 0 and not campaigns_created:
            msg += ' · کمپین خودکار ساخته نشد (فایل تکراری یا بدون سرنخ جدید — از «ساخت کمپین» استفاده کنید)'
        messages.success(request, msg)
        return _lac_redirect('lac-campaigns')

    def _import_discard(self, request):
        batch_id = request.POST.get('batch_id')
        bulk = list(request.session.get(SESSION_BULK_PREVIEW_KEY) or [])
        if batch_id:
            bulk = [i for i in bulk if str(i.get('batch_id')) != str(batch_id)]
            request.session[SESSION_BULK_PREVIEW_KEY] = bulk
            if (request.session.get(SESSION_PREVIEW_KEY) or {}).get('batch_id') == int(batch_id or 0):
                request.session.pop(SESSION_PREVIEW_KEY, None)
                if bulk:
                    request.session[SESSION_PREVIEW_KEY] = bulk[-1]
        else:
            request.session.pop(SESSION_BULK_PREVIEW_KEY, None)
            request.session.pop(SESSION_PREVIEW_KEY, None)
        messages.info(request, 'پیش‌نمایش پاک شد.')
        return _lac_redirect('lac-import')

    def _create_campaign(self, request):
        list_id = int(request.POST.get('list_id') or 0)
        lead_list = get_object_or_404(LeadList, pk=list_id)
        name = (request.POST.get('name') or '').strip() or f'جذب {lead_list.name}'
        campaign = create_acquisition_campaign(
            name=name,
            lead_list=lead_list,
            created_by=request.user,
            landing_url=(request.POST.get('landing_url') or 'https://divarfiling.ir/').strip(),
            is_pilot=request.POST.get('is_pilot') == '1',
            pilot_per_variant=int(request.POST.get('pilot_per_variant') or 15),
        )
        messages.success(request, f'کمپین #{campaign.pk} ساخته شد.')
        return _lac_redirect('lac-campaigns')

    def _update_campaign(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        campaign = update_acquisition_campaign(
            campaign_id,
            name=(request.POST.get('name') or '').strip() or None,
            landing_url=(request.POST.get('landing_url') or '').strip() or None,
            pilot_per_variant=int(request.POST.get('pilot_per_variant') or 0) or None,
            is_pilot=request.POST.get('is_pilot') == '1' if 'is_pilot' in request.POST else None,
            variant_a_template=(request.POST.get('variant_a') or '').strip() or None,
            variant_b_template=(request.POST.get('variant_b') or '').strip() or None,
        )
        messages.success(request, f'کمپین «{campaign.name}» به‌روزرسانی شد.')
        next_url = (request.POST.get('next') or '').strip()
        if next_url.startswith('/'):
            return redirect(next_url)
        return redirect('admin_panel_lead_campaign_detail', pk=campaign.pk)

    def _reset_campaign(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        reset = reset_campaign_for_retry(campaign_id)
        messages.success(
            request,
            f'ریست کمپین — {reset["failed_freed"]} پیام ناموفق آزاد شد، '
            f'{reset["enrollments_reset"]} مخاطب برای ارسال مجدد آماده شد.',
        )
        return _lac_redirect('lac-campaigns')

    def _enroll_pilot(self, request):
        campaign = get_object_or_404(LeadCampaign, pk=int(request.POST.get('campaign_id') or 0))
        result = enroll_pilot(campaign)
        messages.success(
            request,
            f'ثبت در پایلوت انجام شد — واردشده: {result["enrolled"]}، نگه‌داشته: {result["held"]}، '
            f'نسخه‌ها: {result["per_variant"]}',
        )
        return redirect('admin_panel_lead_acquisition')

    def _send_step(self, request):
        campaign = get_object_or_404(LeadCampaign, pk=int(request.POST.get('campaign_id') or 0))
        step_number = int(request.POST.get('step_number') or 1)
        stats = send_campaign_step(campaign, step_number, request=request)
        msg = (
            f'ارسال مرحله {step_number} — پذیرفته: {stats["accepted"]}، ناموفق: {stats["failed"]}، '
            f'ردشده: {stats["skipped"]}، ارسال‌مجدد: {stats.get("retried", 0)}، '
            f'تکراری: {stats["idempotent"]}'
        )
        if stats.get('errors'):
            msg += f'، خطا: {stats["errors"]}'
        if stats.get('remaining'):
            msg += f' — {stats["remaining"]} مخاطب در صف؛ دوباره «ارسال مرحله {step_number}» را بزنید.'
        messages.success(request, msg)
        return redirect('admin_panel_lead_acquisition')

    def _retry_failed(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        reset = reset_campaign_for_retry(campaign_id)
        step_number = int(request.POST.get('step_number') or 1)
        campaign = get_object_or_404(LeadCampaign, pk=campaign_id)
        stats = send_campaign_step(campaign, step_number, request=request)
        messages.success(
            request,
            f'آماده‌سازی ارسال مجدد: {reset["failed_freed"]} پیام ناموفق آزاد شد، '
            f'{reset["enrollments_reset"]} مخاطب ریست شد. نتیجه ارسال مرحله {step_number}: '
            f'پذیرفته {stats["accepted"]} / ناموفق {stats["failed"]}',
        )
        return redirect('admin_panel_lead_acquisition')

    def _parse_campaign_ids(self, request) -> list[int]:
        ids: list[int] = []
        for raw in request.POST.getlist('campaign_ids'):
            try:
                cid = int(raw)
            except (TypeError, ValueError):
                continue
            if cid > 0:
                ids.append(cid)
        if ids:
            return list(dict.fromkeys(ids))
        return _parse_campaign_ids_payload(request.POST)

    def _bulk_campaigns(self, request):
        op = (request.POST.get('bulk_op') or '').strip()
        ids = self._parse_campaign_ids(request)
        if not ids:
            messages.error(request, 'حداقل یک کمپین را انتخاب کنید.')
            return _lac_redirect('lac-campaigns')

        ok_count = 0
        err_lines: list[str] = []
        summaries: list[str] = []

        for cid in ids:
            try:
                if op == 'enroll_pilot':
                    campaign = get_object_or_404(LeadCampaign, pk=cid)
                    result = enroll_pilot(campaign)
                    summaries.append(
                        f'#{cid}: {result["enrolled"]} ثبت · {result["held"]} نگه‌داشته',
                    )
                    ok_count += 1
                elif op == 'enroll_all':
                    result = enroll_all_eligible(get_object_or_404(LeadCampaign, pk=cid))
                    summaries.append(
                        f'#{cid}: {result["enrolled"]} جدید · {result["activated"]} فعال‌شده · '
                        f'کل {result["total_active"]}',
                    )
                    ok_count += 1
                elif op == 'send_step':
                    campaign = get_object_or_404(LeadCampaign, pk=cid)
                    step_number = int(request.POST.get('step_number') or 1)
                    stats = send_campaign_step(campaign, step_number, request=request)
                    summaries.append(
                        f'#{cid}: پذیرفته {stats["accepted"]} · ناموفق {stats["failed"]}',
                    )
                    ok_count += 1
                elif op == 'reset_campaign':
                    reset = reset_campaign_for_retry(cid)
                    summaries.append(
                        f'#{cid}: {reset["enrollments_reset"]} مخاطب ریست',
                    )
                    ok_count += 1
                elif op == 'delete_campaign':
                    result = delete_lead_campaign(cid, confirm=True)
                    summaries.append(f'#{cid}: «{result["name"]}» حذف شد')
                    ok_count += 1
                else:
                    messages.error(request, 'عملیات گروهی نامعتبر است.')
                    return _lac_redirect('lac-campaigns')
            except LeadCampaignError as exc:
                err_lines.append(f'#{cid}: {exc.message}')
            except Exception as exc:  # noqa: BLE001
                logger.exception('bulk campaign op failed campaign=%s op=%s', cid, op)
                err_lines.append(f'#{cid}: {exc}')

        labels = {
            'enroll_pilot': 'ثبت پایلوت گروهی',
            'enroll_all': 'ثبت همه سرنخ‌ها',
            'send_step': f'ارسال کامل مرحله {request.POST.get("step_number") or 1}',
            'reset_campaign': 'ریست گروهی',
            'delete_campaign': 'حذف گروهی',
        }
        label = labels.get(op, op)
        if ok_count:
            detail = ' · '.join(summaries[:6])
            if len(summaries) > 6:
                detail += f' · و {len(summaries) - 6} مورد دیگر'
            messages.success(request, f'{label} — {ok_count} از {len(ids)} کمپین · {detail}')
        if err_lines:
            messages.warning(request, 'خطا: ' + ' · '.join(err_lines[:8]))
        if not ok_count and not err_lines:
            messages.info(request, 'عملیاتی انجام نشد.')
        return _lac_redirect('lac-campaigns')

    def _delete_campaign(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        if request.POST.get('confirm_delete') != '1':
            messages.error(request, 'برای حذف کمپین باید تأیید را فعال کنید.')
            return redirect('admin_panel_lead_acquisition')
        result = delete_lead_campaign(campaign_id, confirm=True)
        messages.success(
            request,
            f'کمپین «{result["name"]}» حذف شد '
            f'(پیام‌ها: {result["messages_removed"]}، ثبت‌نام‌ها: {result["enrollments_removed"]}). '
            f'لیست سرنخ‌ها باقی ماند — می‌توانید کمپین جدید بسازید.',
        )
        return redirect('admin_panel_lead_acquisition')

    def _create_automation_campaign(self, request):
        campaign = create_automation_campaign_from_form(request.POST)
        messages.success(
            request,
            f'کمپین جمع‌آوری خودکار «{campaign.name}» ساخته شد — '
            f'اجرای بعدی با cron یا دکمه «اجرای فوری».',
        )
        return _lac_redirect('lac-automation')

    def _update_automation_campaign(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        campaign = update_automation_campaign_from_form(campaign_id, request.POST)
        messages.success(request, f'کمپین «{campaign.name}» به‌روزرسانی شد.')
        return _lac_redirect('lac-automation')

    def _toggle_automation_campaign(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        campaign = toggle_automation_campaign(campaign_id)
        state = 'فعال' if campaign.is_active else 'غیرفعال'
        messages.success(request, f'کمپین «{campaign.name}» {state} شد.')
        return _lac_redirect('lac-automation')

    def _queue_automation_run(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        run = queue_automation_run_now(campaign_id)
        messages.success(
            request,
            f'اجرای #{run.pk} برای «{run.district}» در صف worker قرار گرفت.',
        )
        return _lac_redirect('lac-automation')

    def _reset_automation_schedule(self, request):
        campaign_id = int(request.POST.get('campaign_id') or 0)
        campaign = reset_automation_schedule(campaign_id)
        messages.success(
            request,
            f'زمان‌بندی «{campaign.name}» ریست شد — cron در اولین فرصت queue می‌کند.',
        )
        return _lac_redirect('lac-automation')

    def _run_automation_scheduler(self, request):
        created = schedule_due_campaigns(max_jobs=1)
        if created:
            ids = ', '.join(str(r.pk) for r in created)
            messages.success(request, f'scheduler — {len(created)} اجرا در صف: {ids}')
        else:
            messages.info(request, 'scheduler — کمپین سررسیدی برای queue نبود.')
        return _lac_redirect('lac-automation')


class AdminLeadCampaignDetailView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_lead_campaign_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campaign = get_object_or_404(LeadCampaign, pk=kwargs['pk'])
        ctx['campaign'] = campaign
        ctx['funnel'] = campaign_funnel(campaign)
        ctx['variant_templates'] = get_step1_variant_templates(campaign)
        ctx['messages_recent'] = (
            CampaignMessage.objects.filter(campaign=campaign)
            .select_related('lead', 'variant', 'step')
            .order_by('-requested_at')[:100]
        )
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action') or ''
        try:
            if action == 'update_campaign':
                campaign_id = int(request.POST.get('campaign_id') or kwargs['pk'])
                update_acquisition_campaign(
                    campaign_id,
                    name=(request.POST.get('name') or '').strip() or None,
                    landing_url=(request.POST.get('landing_url') or '').strip() or None,
                    pilot_per_variant=int(request.POST.get('pilot_per_variant') or 0) or None,
                    is_pilot=request.POST.get('is_pilot') == '1' if 'is_pilot' in request.POST else None,
                    variant_a_template=(request.POST.get('variant_a') or '').strip() or None,
                    variant_b_template=(request.POST.get('variant_b') or '').strip() or None,
                )
                messages.success(request, 'کمپین و پیام‌های A/B به‌روزرسانی شد.')
            elif action == 'reset_campaign':
                reset = reset_campaign_for_retry(int(kwargs['pk']))
                messages.success(
                    request,
                    f'ریست انجام شد — {reset["enrollments_reset"]} مخاطب آماده ارسال مجدد.',
                )
        except LeadCampaignError as exc:
            messages.error(request, exc.message)
        return redirect('admin_panel_lead_campaign_detail', pk=kwargs['pk'])


class AdminLeadFunnelJsonView(StaffRequiredMixin, View):
    def get(self, request, pk: int):
        campaign = get_object_or_404(LeadCampaign, pk=pk)
        return JsonResponse(campaign_funnel(campaign), json_dumps_params={'ensure_ascii': False})


class AdminLeadSendProgressStartView(StaffRequiredMixin, View):
    """شمارش کل مخاطبان در صف ارسال — قبل از progress bar."""

    def post(self, request):
        try:
            payload = _parse_json_or_post(request)
            ids = _parse_campaign_ids_payload(payload)
            if not ids and request.POST.getlist('campaign_ids'):
                ids = [int(x) for x in request.POST.getlist('campaign_ids') if str(x).isdigit()]
            step_number = int(payload.get('step_number') or request.POST.get('step_number') or 1)
            if step_number not in (1, 2, 3):
                return JsonResponse({'ok': False, 'error': 'شماره مرحله نامعتبر است.'}, status=400)
            if not ids:
                return JsonResponse({'ok': False, 'error': 'حداقل یک کمپین انتخاب کنید.'}, status=400)
            # ثبت سرنخ فقط برای مرحله ۱ لازم است؛ ۲ و ۳ روی enroll فعلی کار می‌کنند
            enroll_summary = (
                enroll_campaigns_for_full_send(ids)
                if step_number == 1
                else {'campaigns': 0, 'enrolled': 0, 'activated': 0}
            )
            totals = pending_totals_for_campaigns(ids, step_number)
            return JsonResponse({
                'ok': True,
                'step_number': step_number,
                'campaign_ids': ids,
                'batch_size': send_batch_size(),
                'enroll': enroll_summary,
                **totals,
            }, json_dumps_params={'ensure_ascii': False})
        except LeadCampaignError as exc:
            return JsonResponse({'ok': False, 'error': exc.message}, status=400)


class AdminLeadSendProgressTickView(StaffRequiredMixin, View):
    """ارسال یک chunk و برگرداندن پیشرفت — برای polling از UI."""

    def post(self, request):
        try:
            payload = _parse_json_or_post(request)
            ids = _parse_campaign_ids_payload(payload)
            if not ids and request.POST.getlist('campaign_ids'):
                ids = [int(x) for x in request.POST.getlist('campaign_ids') if str(x).isdigit()]
            step_number = int(payload.get('step_number') or request.POST.get('step_number') or 1)
            if not ids:
                return JsonResponse({'ok': False, 'error': 'حداقل یک کمپین انتخاب کنید.'}, status=400)
            result = send_campaigns_step_chunk(ids, step_number, request=request)
            return JsonResponse({'ok': True, **result}, json_dumps_params={'ensure_ascii': False})
        except LeadCampaignError as exc:
            return JsonResponse({'ok': False, 'error': exc.message}, status=400)
        except Exception as exc:  # noqa: BLE001
            logger.exception('send progress tick failed')
            return JsonResponse({'ok': False, 'error': str(exc)}, status=500)


class AdminLeadBulkTemplatesView(StaffRequiredMixin, View):
    """ذخیره قالب سراسری مراحل ۱–۳ و اعمال روی کمپین‌های انتخاب‌شده یا همه."""

    def get(self, request):
        tpl = get_global_message_templates()
        return JsonResponse({
            'ok': True,
            'variant_a': tpl['A'],
            'variant_b': tpl['B'],
            'step_2': tpl['step_2'],
            'step_3': tpl['step_3'],
            'factory': {
                'variant_a': DEFAULT_STEP1_A,
                'variant_b': DEFAULT_STEP1_B,
                'step_2': DEFAULT_STEP2,
                'step_3': DEFAULT_STEP3,
            },
            'sms_cost_per_part_rial': sms_cost_per_part_rial(),
        }, json_dumps_params={'ensure_ascii': False})

    def post(self, request):
        try:
            payload = _parse_json_or_post(request)
            ids = _parse_campaign_ids_payload(payload)
            if not ids and request.POST.getlist('campaign_ids'):
                ids = [int(x) for x in request.POST.getlist('campaign_ids') if str(x).isdigit()]
            apply_all = payload.get('apply_all') in (True, '1', 1, 'true')
            variant_a = (payload.get('variant_a') or request.POST.get('variant_a') or '').strip()
            variant_b = (payload.get('variant_b') or request.POST.get('variant_b') or '').strip()
            step_2 = (payload.get('step_2') or request.POST.get('step_2') or '').strip()
            step_3 = (payload.get('step_3') or request.POST.get('step_3') or '').strip()

            if apply_all or not ids:
                result = save_global_variant_templates(
                    variant_a,
                    variant_b,
                    step_2=step_2,
                    step_3=step_3,
                    user=request.user,
                    apply_to_all=True,
                )
            else:
                save_global_variant_templates(
                    variant_a,
                    variant_b,
                    step_2=step_2,
                    step_3=step_3,
                    user=request.user,
                    apply_to_all=False,
                )
                result = bulk_update_message_templates(
                    ids,
                    variant_a=variant_a,
                    variant_b=variant_b,
                    step_2=step_2,
                    step_3=step_3,
                )
                result['saved'] = True
                result['variant_a'] = variant_a
                result['variant_b'] = variant_b
                result['step_2'] = step_2
                result['step_3'] = step_3

            return JsonResponse({
                'ok': True,
                'saved': True,
                'updated_count': result.get('updated_count', 0),
                'updated': result.get('updated', []),
                'errors': result.get('errors', []),
                'variant_a': result.get('variant_a', variant_a),
                'variant_b': result.get('variant_b', variant_b),
                'step_2': result.get('step_2', step_2),
                'step_3': result.get('step_3', step_3),
            }, json_dumps_params={'ensure_ascii': False})
        except LeadCampaignError as exc:
            return JsonResponse({'ok': False, 'error': exc.message}, status=400)


class AdminAutomationPlacesJsonView(StaffRequiredMixin, View):
    """مناطق یک شهر از places-web.json برای فرم اتوماسیون."""

    def get(self, request):
        city = (request.GET.get('city') or 'تهران').strip()
        districts = list_districts_for_city(city)
        return JsonResponse({
            'ok': True,
            'city': city,
            'districts': districts,
            'count': len(districts),
            'places_available': places_config_available(),
        }, json_dumps_params={'ensure_ascii': False})
