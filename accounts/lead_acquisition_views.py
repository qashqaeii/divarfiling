"""ویوهای عمومی و ادمین مرکز جذب سرنخ."""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
    LeadCampaignError,
    create_acquisition_campaign,
    enroll_pilot,
    send_campaign_step,
)
from accounts.services.lead_funnel import campaign_funnel, overview_stats
from accounts.services.lead_import import (
    LeadImportError,
    commit_import_batch,
    create_preview_batch,
    preview_phone_detector_json,
)
from accounts.services.lead_tokens import COOKIE_NAME, cookie_secure_kwargs, hash_ip, truncate_user_agent

logger = logging.getLogger(__name__)

SESSION_PREVIEW_KEY = 'lead_import_preview_rows'


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
        ctx.update({
            'overview': overview_stats(),
            'batches': LeadImportBatch.objects.order_by('-created_at')[:20],
            'lists': LeadList.objects.order_by('-created_at')[:20],
            'campaigns': campaigns,
            'funnels': funnels,
            'preview': self.request.session.get(SESSION_PREVIEW_KEY),
            'leads_sample': MarketingLead.objects.order_by('-updated_at')[:25],
        })
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action') or ''
        try:
            if action == 'import_preview':
                return self._import_preview(request)
            if action == 'import_commit':
                return self._import_commit(request)
            if action == 'create_campaign':
                return self._create_campaign(request)
            if action == 'enroll_pilot':
                return self._enroll_pilot(request)
            if action == 'send_step':
                return self._send_step(request)
        except (LeadImportError, LeadCampaignError) as exc:
            messages.error(request, exc.message)
        except Exception as exc:  # noqa: BLE001
            logger.exception('lead acquisition admin error')
            messages.error(request, f'خطا: {exc}')
        return redirect('admin_panel_lead_acquisition')

    def _import_preview(self, request):
        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.error(request, 'فایل انتخاب نشده است.')
            return redirect('admin_panel_lead_acquisition')
        raw = uploaded.read()
        preview = preview_phone_detector_json(raw, filename=uploaded.name)
        if preview.duplicate_file:
            messages.error(request, 'این فایل قبلاً commit شده است (hash تکراری).')
            return redirect('admin_panel_lead_acquisition')
        batch = create_preview_batch(preview, uploaded_by=request.user)
        # ذخیره ردیف‌ها در session برای commit
        request.session[SESSION_PREVIEW_KEY] = {
            'batch_id': batch.pk,
            'file_hash': preview.file_hash,
            'stats': preview.stats,
            'metadata': preview.metadata,
            'rows': [
                {
                    'phone': r.phone,
                    'name': r.name,
                    'district': r.district,
                    'category': r.category,
                    'outcome': r.outcome,
                    'lead_type': r.lead_type,
                    'confidence': str(r.confidence),
                }
                for r in preview.rows
            ],
        }
        messages.success(
            request,
            f'پیش‌نمایش آماده است — قابل ورود: {preview.stats.get("eligible", 0)}',
        )
        return redirect('admin_panel_lead_acquisition')

    def _import_commit(self, request):
        from decimal import Decimal

        from accounts.services.lead_import import PreviewRow

        payload = request.session.get(SESSION_PREVIEW_KEY) or {}
        batch_id = payload.get('batch_id')
        if not batch_id:
            messages.error(request, 'پیش‌نمایش فعالی نیست.')
            return redirect('admin_panel_lead_acquisition')
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
        request.session.pop(SESSION_PREVIEW_KEY, None)
        messages.success(
            request,
            f'ایمپورت ثبت شد — ایجاد: {result["created"]}، به‌روزرسانی: {result["updated"]}، '
            f'کاربر موجود: {result["existing_user_marked"]}، عضو لیست: {result["members_added"]}',
        )
        return redirect('admin_panel_lead_acquisition')

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
        return redirect('admin_panel_lead_acquisition')

    def _enroll_pilot(self, request):
        campaign = get_object_or_404(LeadCampaign, pk=int(request.POST.get('campaign_id') or 0))
        result = enroll_pilot(campaign)
        messages.success(
            request,
            f'پایلوت: enrolled={result["enrolled"]} held={result["held"]} variants={result["per_variant"]}',
        )
        return redirect('admin_panel_lead_acquisition')

    def _send_step(self, request):
        campaign = get_object_or_404(LeadCampaign, pk=int(request.POST.get('campaign_id') or 0))
        step_number = int(request.POST.get('step_number') or 1)
        stats = send_campaign_step(campaign, step_number, request=request)
        messages.success(request, f'ارسال مرحله {step_number}: {stats}')
        return redirect('admin_panel_lead_acquisition')


class AdminLeadCampaignDetailView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_lead_campaign_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campaign = get_object_or_404(LeadCampaign, pk=kwargs['pk'])
        ctx['campaign'] = campaign
        ctx['funnel'] = campaign_funnel(campaign)
        ctx['messages_recent'] = (
            CampaignMessage.objects.filter(campaign=campaign)
            .select_related('lead', 'variant', 'step')
            .order_by('-requested_at')[:100]
        )
        return ctx


class AdminLeadFunnelJsonView(StaffRequiredMixin, View):
    def get(self, request, pk: int):
        campaign = get_object_or_404(LeadCampaign, pk=pk)
        return JsonResponse(campaign_funnel(campaign), json_dumps_params={'ensure_ascii': False})
