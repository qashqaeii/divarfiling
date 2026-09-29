"""API views for Management AI — GET never triggers LLM."""
from __future__ import annotations

from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

from accounts.admin_views import StaffRequiredMixin
from accounts.services.admin_dashboard import ALL_TIME_DAYS
from accounts.services.admin_panel_shell import parse_admin_panel_range
from accounts.services.management_ai import generate_analysis, get_latest_analysis
from accounts.services.management_ai.schemas import PHASE1_SECTIONS


def _period_from_request(request) -> tuple[int, bool]:
    days, range_key = parse_admin_panel_range(request)
    compare = request.GET.get('compare') == '1' or request.POST.get('compare') == '1'
    if range_key == 'all':
        return ALL_TIME_DAYS, False
    if compare and range_key == 'all':
        compare = False
    return days, compare


class AdminManagementAIAnalysisView(StaffRequiredMixin, View):
    """GET latest stored analysis — no provider call."""

    def get(self, request, section: str):
        if section not in PHASE1_SECTIONS:
            return JsonResponse({'status': 'error', 'error': 'invalid_section'}, status=404)
        days, compare = _period_from_request(request)
        payload = get_latest_analysis(section, days, compare)
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


@method_decorator(require_POST, name='dispatch')
class AdminManagementAIAnalysisGenerateView(StaffRequiredMixin, View):
    """POST — manual AI generation only."""

    def post(self, request, section: str):
        if section not in PHASE1_SECTIONS:
            return JsonResponse({'ok': False, 'error': 'invalid_section'}, status=404)
        days, compare = _period_from_request(request)
        force = request.POST.get('force') == '1'
        result = generate_analysis(
            section,
            days,
            compare,
            request.user,
            force=force,
        )
        status = 200 if result.get('ok') else 400
        if result.get('error') == 'rate_limited':
            status = 429
        if result.get('error') == 'in_progress':
            status = 409
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False}, status=status)
