"""ویوهای پنل مدیریت سیستم — فقط برای کاربران staff."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseNotFound
from django.views import View
from django.views.generic import TemplateView

from accounts.services.admin_dashboard import get_admin_dashboard_context
from accounts.services.admin_exports import EXPORT_REGISTRY, build_export
from accounts.services.admin_system_summary import system_summary_json_response


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
        days = max(7, min(days, 90))

        dashboard = get_admin_dashboard_context(days=days)
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
