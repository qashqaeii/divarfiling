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
    CampaignMessage,
    LeadCampaign,
    LeadImportBatch,
    LeadList,
    LeadTouchpoint,
    MarketingLead,
)
from accounts.services.lead_attribution import record_touchpoint
from accounts.services.lead_campaign_send import (
    DEFAULT_STEP1_A,
    DEFAULT_STEP1_B,
    LeadCampaignError,
    auto_create_campaign_for_import,
    create_acquisition_campaign,
    delete_lead_campaign,
    enroll_pilot,
    get_step1_variant_templates,
    reset_campaign_for_retry,
    send_campaign_step,
    update_acquisition_campaign,
)
from accounts.services.lead_funnel import campaign_funnel, overview_stats
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
            LeadCampaign.objects.select_related('lead_list', 'created_by').order_by('-created_at')[:30]
        )
        funnels = [campaign_funnel(c) for c in campaigns[:10]]
        campaign_edit = {}
        for c in campaigns[:15]:
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
            'default_variant_a': (
                get_step1_variant_templates(campaigns[0])['A'] if campaigns else DEFAULT_STEP1_A
            ),
            'default_variant_b': (
                get_step1_variant_templates(campaigns[0])['B'] if campaigns else DEFAULT_STEP1_B
            ),
            'campaign_edit_json': json.dumps(campaign_edit, ensure_ascii=False),
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
        except (LeadImportError, LeadCampaignError) as exc:
            messages.error(request, exc.message)
        except Exception as exc:  # noqa: BLE001
            logger.exception('lead acquisition admin error')
            messages.error(request, f'خطا: {exc}')
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
        last_preview = None

        for uploaded in uploads[:20]:
            raw = uploaded.read()
            preview = preview_phone_detector_json(raw, filename=uploaded.name)
            if preview.duplicate_file:
                skipped_dup += 1
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
            messages.warning(request, f'{skipped_dup} فایل تکراری (قبلاً commit شده) رد شد.')
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
        if auto_campaign:
            from accounts.models import LeadList

            lead_list = LeadList.objects.get(pk=result['list_id'])
            eligible = result.get('members_added', 0) or payload.get('stats', {}).get('eligible', 0)
            campaign = auto_create_campaign_for_import(
                lead_list=lead_list,
                batch_id=result['batch_id'],
                eligible_count=eligible,
                created_by=request.user,
            )
        result['campaign'] = campaign
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
        messages.success(request, msg)
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
