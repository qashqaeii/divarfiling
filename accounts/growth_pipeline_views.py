"""ویوهای ادمین پایپلاین رشد یکپارچه."""
from __future__ import annotations

import json

from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from accounts.admin_views import StaffRequiredMixin
from accounts.models import GrowthJourney
from accounts.services.growth_journey import (
    journeys_for_stage,
    pipeline_overview,
    summarize_last_run,
    transition,
)

STAGE_LABELS = dict(GrowthJourney.Stage.choices)

EVENT_LABELS = {
    'lead_imported': 'ورود سرنخ',
    'click_landing': 'کلیک روی لینک',
    'signup': 'ثبت‌نام',
    'signup_complete': 'ثبت‌نام',
    'workspace_login': 'ورود به میزکار',
    'checkout_start': 'شروع خرید / سبد',
    'no_purchase_window': 'یادآوری بدون خرید',
    'paid_licensed': 'خرید و لایسنس',
    'license_expiring': 'نزدیک انقضا',
    'repurchase': 'تمدید',
    'expired_no_renew': 'انقضا بدون تمدید',
    'opt_out': 'لغو دریافت',
    'suppressed': 'مسدود',
    'manual_set': 'تنظیم دستی / همگام‌سازی',
    'pause_nurture': 'توقف پیام‌ها',
    'resume_nurture': 'از سرگیری پیام‌ها',
}


class AdminGrowthPipelineView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_growth_pipeline.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        overview = pipeline_overview()
        stage = (self.request.GET.get('stage') or '').strip()
        detail_rows = []
        selected_meta = None
        if stage:
            for s in overview.get('stages') or []:
                if s['key'] == stage:
                    selected_meta = s
                    break
            for j in journeys_for_stage(stage, limit=80):
                detail_rows.append({
                    'id': j.pk,
                    'phone': j.phone_normalized,
                    'stage': j.stage,
                    'stage_label': j.get_stage_display(),
                    'source': j.get_source_display(),
                    'user_id': j.user_id,
                    'lead_id': j.lead_id,
                    'paused': j.nurture_paused,
                    'suppressed': j.suppressed,
                    'entered_at': j.stage_entered_at,
                    'last_touch_at': j.last_touch_at,
                })

        last_run = cache.get('growth_pipeline_last_run') or {}
        run_summary = summarize_last_run(last_run)

        recent_fa = []
        for ev in overview.get('recent_events') or []:
            recent_fa.append({
                **ev,
                'event_label': EVENT_LABELS.get(ev.get('event_type'), ev.get('event_type')),
                'stage_from_label': STAGE_LABELS.get(ev.get('stage_from') or '', ev.get('stage_from') or '—'),
                'stage_to_label': STAGE_LABELS.get(ev.get('stage_to') or '', ev.get('stage_to') or '—'),
            })

        ctx.update({
            'overview': overview,
            'summary': overview.get('summary') or {},
            'selected_stage': stage,
            'selected_meta': selected_meta,
            'detail_rows': detail_rows,
            'last_run': last_run,
            'run_summary': run_summary,
            'recent_events_fa': recent_fa,
            'last_run_json': json.dumps(last_run, ensure_ascii=False, default=str),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action') or ''
        journey_id = request.POST.get('journey_id')
        if action == 'backfill':
            from accounts.services.growth_journey import backfill_journeys
            stats = backfill_journeys(limit=5000)
            messages.success(
                request,
                f'همگام‌سازی انجام شد: {stats.get("leads")} سرنخ بررسی شد، '
                f'{stats.get("created")} پرونده جدید، {stats.get("updated")} به‌روز شد.',
            )
            return redirect('admin_panel_growth_pipeline')

        if action in ('pause', 'resume') and journey_id:
            journey = get_object_or_404(GrowthJourney, pk=journey_id)
            transition(
                phone=journey.phone_normalized,
                user=journey.user,
                lead=journey.lead,
                event_type='pause_nurture' if action == 'pause' else 'resume_nurture',
            )
            messages.success(
                request,
                'ارسال خودکار برای این شماره متوقف شد.'
                if action == 'pause'
                else 'ارسال خودکار دوباره فعال شد.',
            )
            url = reverse('admin_panel_growth_pipeline')
            if journey.stage:
                url += f'?stage={journey.stage}'
            return redirect(url)

        if action == 'suppress' and journey_id:
            journey = get_object_or_404(GrowthJourney, pk=journey_id)
            from accounts.services.growth_suppression import sync_opt_out_to_suppression
            sync_opt_out_to_suppression(
                journey.phone_normalized,
                reason='manual',
                notes='admin growth pipeline',
            )
            messages.success(request, 'این شماره دیگر پیام خودکار نمی‌گیرد.')
            return redirect(reverse('admin_panel_growth_pipeline') + f'?stage={journey.stage}')

        messages.error(request, 'اقدام نامعتبر.')
        return redirect('admin_panel_growth_pipeline')


class AdminGrowthPipelineJsonView(StaffRequiredMixin, View):
    def get(self, request):
        overview = pipeline_overview()
        recent = []
        for ev in overview.get('recent_events') or []:
            row = dict(ev)
            created = row.get('created_at')
            if created is not None:
                row['created_at'] = created.isoformat() if hasattr(created, 'isoformat') else str(created)
            recent.append(row)
        overview['recent_events'] = recent
        last_run = cache.get('growth_pipeline_last_run') or {}
        overview['last_run'] = last_run
        overview['run_summary'] = summarize_last_run(last_run)
        return JsonResponse({'ok': True, 'overview': overview})
