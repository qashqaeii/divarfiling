"""ویوهای مدیریت لایسنس در داشبورد."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.views import View

from licenses.services.management import (
    assign_seat_to_member,
    register_device_slot,
    remove_device_slot,
    revoke_seat_assignment,
    update_device_slot,
)


class _LicenseActionView(LoginRequiredMixin, View):
    def _json_error(self, exc, status=400):
        if isinstance(exc, PermissionDenied):
            return JsonResponse({'ok': False, 'error': str(exc) or 'دسترسی مجاز نیست.'}, status=403)
        if isinstance(exc, ValidationError):
            msg = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
            return JsonResponse({'ok': False, 'error': msg}, status=status)
        return JsonResponse({'ok': False, 'error': str(exc)}, status=status)


class RegisterDeviceSlotView(_LicenseActionView):
    def post(self, request):
        license_id = request.POST.get('license_id', '').strip()
        hardware = request.POST.get('hardware_fingerprint', '').strip()
        label = request.POST.get('label', '').strip()
        try:
            activation = register_device_slot(
                request.user, license_id, hardware, label=label,
            )
            return JsonResponse({
                'ok': True,
                'message': 'سیستم با موفقیت ثبت شد. کلید لایسنس را در ربات وارد کنید.',
                'activation_id': activation.pk,
            })
        except Exception as exc:
            return self._json_error(exc)


class UpdateDeviceSlotView(_LicenseActionView):
    def post(self, request):
        activation_id = request.POST.get('activation_id', '').strip()
        label = request.POST.get('label')
        notes = request.POST.get('notes')
        try:
            activation = update_device_slot(
                request.user,
                int(activation_id),
                label=label,
                notes=notes,
            )
            return JsonResponse({
                'ok': True,
                'message': 'اطلاعات سیستم به‌روز شد.',
                'label': activation.label,
            })
        except Exception as exc:
            return self._json_error(exc)


class AssignSeatView(_LicenseActionView):
    def post(self, request):
        activation_id = request.POST.get('activation_id', '').strip()
        member_id = request.POST.get('member_id', '').strip()
        try:
            activation = assign_seat_to_member(
                request.user, int(activation_id), int(member_id),
            )
            name = activation.assigned_user.get_full_name() or activation.assigned_user.username
            return JsonResponse({
                'ok': True,
                'message': f'اسلات به {name} تخصیص یافت.',
                'assigned_user': name,
            })
        except Exception as exc:
            return self._json_error(exc)


class RevokeSeatView(_LicenseActionView):
    def post(self, request):
        activation_id = request.POST.get('activation_id', '').strip()
        try:
            revoke_seat_assignment(request.user, int(activation_id))
            return JsonResponse({'ok': True, 'message': 'تخصیص عضو تیم لغو شد.'})
        except Exception as exc:
            return self._json_error(exc)


class RemoveDeviceSlotView(_LicenseActionView):
    def post(self, request):
        activation_id = request.POST.get('activation_id', '').strip()
        try:
            remove_device_slot(request.user, int(activation_id))
            return JsonResponse({'ok': True, 'message': 'سیستم از لایسنس حذف شد.'})
        except Exception as exc:
            return self._json_error(exc)
