"""Mixin‌های workspace."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from workspace.models import Dataset, WorkspaceSettings
from workspace.services.access import has_active_bot_license


class WorkspaceLoginMixin(LoginRequiredMixin):
    """دسترسی به میزکار — فقط ورود به سیستم."""


class LicenseRequiredMixin(WorkspaceLoginMixin):
    """دسترسی به امکانات ربات — نیاز به لایسنس فعال."""

    license_denied_message = (
        'این بخش مربوط به ربات استخراج دیوار است و نیاز به لایسنس فعال دارد.'
    )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not has_active_bot_license(request.user):
            messages.info(request, self.license_denied_message)
            upgrade_url = reverse('workspace:upgrade')
            next_path = request.get_full_path()
            if next_path and next_path != upgrade_url:
                return redirect(f'{upgrade_url}?next={next_path}')
            return redirect(upgrade_url)
        return super().dispatch(request, *args, **kwargs)


class DatasetOwnerMixin(LicenseRequiredMixin):
    """بررسی مالکیت dataset — فقط دیتاست‌های فعال."""

    def get_dataset(self):
        pk = self.kwargs.get('dataset_id') or self.kwargs.get('pk')
        return get_object_or_404(Dataset, pk=pk, user=self.request.user, is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self, 'get_dataset'):
            try:
                context['dataset'] = self.get_dataset()
            except Exception:
                pass
        return context


def get_or_create_settings(user) -> WorkspaceSettings:
    settings, _ = WorkspaceSettings.objects.get_or_create(user=user)
    return settings
