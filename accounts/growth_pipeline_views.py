"""ویوهای ادمین پایپلاین رشد یکپارچه."""
from __future__ import annotations

import json

from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.views import View
from django.views.generic import TemplateView

from accounts.admin_views import StaffRequiredMixin
from accounts.models import GrowthJourney
from accounts.services.growth_journey import (
    STAGE_RANK,
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

EVENT_TONES = {
    'lead_imported': 'neutral',
    'click_landing': 'info',
    'signup': 'success',
    'signup_complete': 'success',
    'workspace_login': 'info',
    'checkout_start': 'amber',
    'no_purchase_window': 'amber',
    'paid_licensed': 'success',
    'license_expiring': 'amber',
    'repurchase': 'success',
    'expired_no_renew': 'danger',
    'opt_out': 'danger',
    'suppressed': 'danger',
    'manual_set': 'neutral',
    'pause_nurture': 'amber',
    'resume_nurture': 'info',
}

EVENT_ICONS = {
    'lead_imported': 'fa-user-plus',
    'click_landing': 'fa-mouse-pointer',
    'signup': 'fa-user-check',
    'signup_complete': 'fa-user-check',
    'workspace_login': 'fa-right-to-bracket',
    'checkout_start': 'fa-cart-shopping',
    'no_purchase_window': 'fa-bell',
    'paid_licensed': 'fa-crown',
    'license_expiring': 'fa-hourglass-half',
    'repurchase': 'fa-arrows-rotate',
    'expired_no_renew': 'fa-triangle-exclamation',
    'opt_out': 'fa-ban',
    'suppressed': 'fa-ban',
    'manual_set': 'fa-screwdriver-wrench',
    'pause_nurture': 'fa-pause',
    'resume_nurture': 'fa-play',
}


def _movement_kind(stage_from: str, stage_to: str) -> str:
    if not stage_from or not stage_to or stage_from == stage_to:
        return 'same'
    rank_from = STAGE_RANK.get(stage_from, 0)
    rank_to = STAGE_RANK.get(stage_to, 0)
    if stage_to == GrowthJourney.Stage.SUPPRESSED:
        return 'blocked'
    if rank_to > rank_from:
        return 'forward'
    if rank_to < rank_from:
        return 'back'
    return 'same'


def _enrich_recent_event(ev: dict) -> dict:
    event_type = ev.get('event_type') or ''
    stage_from = ev.get('stage_from') or ''
    stage_to = ev.get('stage_to') or ''
    from_label = STAGE_LABELS.get(stage_from, stage_from or '—')
    to_label = STAGE_LABELS.get(stage_to, stage_to or '—')
    movement = _movement_kind(stage_from, stage_to)
    created = ev.get('created_at')
    relative = ''
    if created is not None:
        try:
            relative = timesince(created, timezone.now())
        except Exception:
            relative = ''

    if movement == 'same':
        path_text = f'ماندن در «{to_label}»' if to_label != '—' else 'بدون تغییر مرحله'
    elif movement == 'blocked':
        path_text = f'مسدود از «{from_label}»'
    else:
        path_text = f'از «{from_label}» به «{to_label}»'

    phone = (ev.get('journey__phone_normalized') or '').strip()
    return {
        **ev,
        'phone': phone,
        'event_label': EVENT_LABELS.get(event_type, event_type or 'رویداد'),
        'event_tone': EVENT_TONES.get(event_type, 'neutral'),
        'event_icon': EVENT_ICONS.get(event_type, 'fa-circle-dot'),
        'stage_from_label': from_label,
        'stage_to_label': to_label,
        'movement': movement,
        'path_text': path_text,
        'relative_fa': f'{relative} پیش' if relative else '',
        'stage_changed': bool(stage_from and stage_to and stage_from != stage_to),
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
        charts = overview.get('charts') or {}

        recent_fa = [_enrich_recent_event(ev) for ev in (overview.get('recent_events') or [])]

        ctx.update({
            'overview': overview,
            'summary': overview.get('summary') or {},
            'selected_stage': stage,
            'selected_meta': selected_meta,
            'detail_rows': detail_rows,
            'last_run': last_run,
            'run_summary': run_summary,
            'recent_events_fa': recent_fa,
            'recent_events_count': len(recent_fa),
            'charts_json': json.dumps(charts, ensure_ascii=False, default=str),
            'rates': (charts.get('rates') or {}),
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
