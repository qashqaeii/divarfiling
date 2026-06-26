"""Viewهای REST API موبایل."""
from __future__ import annotations

import json
import logging

from django.contrib.auth import authenticate, get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from mobile_api.responses import api_error, api_ok
from mobile_api.services.crm_service import (
    create_quick_lead,
    get_contact,
    list_contacts,
    today_payload,
)
from mobile_api.services.device_service import register_or_update_device, update_device_fcm
from mobile_api.services.extraction_ingest import extraction_limits_payload, ingest_mobile_extraction
from mobile_api.services.filing_service import get_dataset, list_datasets, list_listings
from mobile_api.services.license_service import license_status_payload, require_light_extract
from mobile_api.services.settings_service import (
    get_notification_prefs,
    get_profile,
    update_notification_prefs,
    update_profile,
)
from mobile_api.services.sync_service import pull_sync, push_sync
from mobile_api.serializers import contact_to_dict, listing_to_dict

User = get_user_model()
logger = logging.getLogger(__name__)


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'expires_in': int(refresh.access_token.lifetime.total_seconds()),
    }


def _parse_body(request) -> dict:
    try:
        if not request.body:
            return {}
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return {}


def _device_id(request) -> str:
    return (request.META.get('HTTP_X_DEVICE_ID') or '').strip()


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = _parse_body(request)
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return api_error('نام کاربری و رمز عبور الزامی است.', code='VALIDATION_ERROR')

        user = authenticate(request, username=username, password=password)
        if user is None:
            user = User.objects.filter(phone=username).first()
            if user and user.check_password(password):
                pass
            else:
                return api_error('نام کاربری یا رمز عبور اشتباه است.', code='AUTH_INVALID', status=401)

        tokens = _tokens_for_user(user)
        from mobile_api.serializers import user_to_dict
        return api_ok({**tokens, 'user': user_to_dict(user)})


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = _parse_body(request)
        refresh_str = data.get('refresh') or ''
        if not refresh_str:
            return api_error('توکن refresh الزامی است.', code='VALIDATION_ERROR')
        try:
            refresh = RefreshToken(refresh_str)
            access = refresh.access_token
            return api_ok({
                'access': str(access),
                'refresh': str(refresh),
                'expires_in': int(access.lifetime.total_seconds()),
            })
        except TokenError:
            return api_error('توکن منقضی شده است.', code='AUTH_EXPIRED', status=401)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        refresh_str = data.get('refresh') or ''
        if refresh_str:
            try:
                RefreshToken(refresh_str)
            except Exception:
                pass
        return api_ok({})


class DeviceRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        try:
            result = register_or_update_device(request.user, data)
            return api_ok(result)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class DevicePatchView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        data = _parse_body(request)
        device_id = _device_id(request)
        if not device_id:
            return api_error('شناسه دستگاه در هدر الزامی است.', code='VALIDATION_ERROR')
        if not update_device_fcm(request.user, device_id, data.get('fcm_token', '')):
            return api_error('دستگاه یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({})


class LicenseStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(license_status_payload(request.user))


class ContactsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.GET.get('q', '')
        page = int(request.GET.get('page', 1) or 1)
        page_size = int(request.GET.get('page_size', 50) or 50)
        items, meta = list_contacts(request.user, q=q, page=page, page_size=page_size)
        return api_ok(items, meta=meta)


class ContactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contact_id):
        c = get_contact(request.user, contact_id)
        if not c:
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(contact_to_dict(c))


class QuickLeadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        try:
            c = create_quick_lead(request.user, data)
            return api_ok(contact_to_dict(c), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class TodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(today_payload(request.user))


class DatasetsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = int(request.GET.get('page', 1) or 1)
        page_size = int(request.GET.get('page_size', 20) or 20)
        items, meta = list_datasets(request.user, page=page, page_size=page_size)
        return api_ok(items, meta=meta)


class DatasetListingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dataset_id):
        if not get_dataset(request.user, dataset_id):
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        page = int(request.GET.get('page', 1) or 1)
        page_size = int(request.GET.get('page_size', 50) or 50)
        q = request.GET.get('q', '')
        items, meta = list_listings(
            request.user, dataset_id, page=page, page_size=page_size, q=q,
        )
        return api_ok(items, meta=meta)


class ListingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        from workspace.models import Listing
        lst = Listing.objects.filter(
            dataset__user=request.user,
            token=token,
        ).select_related('dataset').first()
        if not lst:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(listing_to_dict(lst))


class ExtractionLimitsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(extraction_limits_payload(request.user))


class ExtractionUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        data = _parse_body(request)
        try:
            result = ingest_mobile_extraction(request.user, data)
            return api_ok({
                'dataset_id': str(result.dataset.pk),
                'ingested_count': result.ingested_count,
                'skipped_count': result.skipped_count,
                'workspace_url': f'/workspace/datasets/{result.dataset.pk}/',
            })
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        except RuntimeError as exc:
            return api_error(str(exc), code='INGEST_ERROR', status=400)
        except Exception:
            logger.exception('mobile extraction upload failed for user=%s', request.user.pk)
            return api_error(
                'خطای داخلی سرور در ذخیره استخراج.',
                code='SERVER_ERROR',
                status=500,
            )


class SyncPullView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        since = request.GET.get('since', '')
        entities_raw = request.GET.get('entities', 'contacts')
        entities = [e.strip() for e in entities_raw.split(',') if e.strip()]
        return api_ok(pull_sync(request.user, since, entities))


class SyncPushView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        ops = data.get('operations') or []
        return api_ok(push_sync(request.user, ops))


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(get_profile(request.user))

    def patch(self, request):
        data = _parse_body(request)
        return api_ok(update_profile(request.user, data))


class NotificationPrefsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(get_notification_prefs(request.user, _device_id(request)))

    def patch(self, request):
        data = _parse_body(request)
        device_id = _device_id(request)
        if not device_id:
            return api_error('شناسه دستگاه در هدر الزامی است.', code='VALIDATION_ERROR')
        return api_ok(update_notification_prefs(request.user, device_id, data))
