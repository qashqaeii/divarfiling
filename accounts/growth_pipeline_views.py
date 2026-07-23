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
    transition,
)


class AdminGrowthPipelineView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_growth_pipeline.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        overview = pipeline_overview()
        stage = (self.request.GET.get('stage') or '').strip()
        detail_rows = []
        if stage:
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
        ctx.update({
            'overview': overview,
            'selected_stage': stage,
            'detail_rows': detail_rows,
            'last_run': last_run,
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
                f'Backfill انجام شد — leads={stats.get("leads")} users={stats.get("users")} '
                f'updated={stats.get("updated")}',
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
                'Nurture متوقف شد.' if action == 'pause' else 'Nurture از سر گرفته شد.',
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
            messages.success(request, 'مخاطب به suppression اضافه شد.')
            return redirect(reverse('admin_panel_growth_pipeline') + f'?stage={journey.stage}')

        messages.error(request, 'اقدام نامعتبر.')
        return redirect('admin_panel_growth_pipeline')


class AdminGrowthPipelineJsonView(StaffRequiredMixin, View):
    def get(self, request):
        overview = pipeline_overview()
        # serialize datetimes
        recent = []
        for ev in overview.get('recent_events') or []:
            row = dict(ev)
            created = row.get('created_at')
            if created is not None:
                row['created_at'] = created.isoformat() if hasattr(created, 'isoformat') else str(created)
            recent.append(row)
        overview['recent_events'] = recent
        overview['last_run'] = cache.get('growth_pipeline_last_run') or {}
        return JsonResponse({'ok': True, 'overview': overview})
