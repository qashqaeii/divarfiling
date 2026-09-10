"""Mixin‌های دسترسی قرارداد."""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from contracts.services.license_gate import LICENSE_REQUIRED_MSG, user_has_contract_license
from workspace.mixins import WorkspaceLoginMixin


class ContractLicenseRequiredMixin(WorkspaceLoginMixin):
    """دسترسی به امکانات قرارداد — نیاز به لایسنس فعال."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_has_contract_license(request.user):
            return self._contract_license_denied(request)
        return super().dispatch(request, *args, **kwargs)

    def _contract_license_denied(self, request):
        accepts = request.headers.get('Accept', '')
        if (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in accepts
            or request.path.endswith('/api/deals/')
        ):
            return JsonResponse({'ok': False, 'error': LICENSE_REQUIRED_MSG}, status=403)
        messages.info(request, LICENSE_REQUIRED_MSG)
        return redirect(reverse('workspace:contracts_dashboard'))


class ContractLicenseContextMixin:
    """وضعیت قفل قراردادها برای قالب‌ها."""

    def get_contract_license_context(self):
        locked = not user_has_contract_license(self.request.user)
        return {
            'contracts_locked': locked,
            'contracts_license_required_msg': LICENSE_REQUIRED_MSG,
        }
