"""APIهای دریافت شماره از دیوار — فقط برای کاربران مجاز."""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from workspace.models import Listing
from workspace.services.divar_session.feature import user_can_use_divar_contact
from workspace.services.divar_session.errors import DivarSessionError
from workspace.services.divar_session.service import (
    disconnect_divar_session,
    fetch_listing_phone,
    public_session_status,
    send_divar_otp,
    verify_divar_otp,
)
from workspace.mixins import DatasetOwnerMixin


class DivarContactPermissionMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not user_can_use_divar_contact(request.user):
            return JsonResponse(
                {'ok': False, 'error': 'دسترسی مجاز نیست.', 'code': 'forbidden'},
                status=403,
                json_dumps_params={'ensure_ascii': False},
            )
        return super().dispatch(request, *args, **kwargs)


class DivarContactStatusView(DivarContactPermissionMixin, View):
    def get(self, request):
        return JsonResponse(
            {'ok': True, 'status': public_session_status(request.user)},
            json_dumps_params={'ensure_ascii': False},
        )


class DivarContactOtpSendView(DivarContactPermissionMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)
        try:
            result = send_divar_otp(request.user, body.get('phone') or '')
        except DivarSessionError as exc:
            return JsonResponse(
                {'ok': False, 'error': exc.message, 'code': exc.code},
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})


class DivarContactOtpVerifyView(DivarContactPermissionMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)
        try:
            result = verify_divar_otp(
                request.user,
                body.get('phone') or '',
                body.get('otp') or '',
            )
        except DivarSessionError as exc:
            return JsonResponse(
                {'ok': False, 'error': exc.message, 'code': exc.code},
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})


class DivarContactDisconnectView(DivarContactPermissionMixin, View):
    def post(self, request):
        result = disconnect_divar_session(request.user)
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})


class DivarContactFetchPhoneView(DivarContactPermissionMixin, DatasetOwnerMixin, View):
    def post(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        try:
            result = fetch_listing_phone(request.user, listing)
        except DivarSessionError as exc:
            status = 403 if exc.code == 'forbidden' else 400
            return JsonResponse(
                {'ok': False, 'error': exc.message, 'code': exc.code},
                status=status,
                json_dumps_params={'ensure_ascii': False},
            )
        status_code = 200 if result.get('ok') else 409
        return JsonResponse(result, status=status_code, json_dumps_params={'ensure_ascii': False})
