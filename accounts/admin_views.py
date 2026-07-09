"""ویوهای پنل مدیریت سیستم — فقط برای کاربران staff."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from accounts.services.admin_dashboard import get_admin_dashboard_context


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
