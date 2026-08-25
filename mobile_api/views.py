"""Viewهای REST API موبایل."""
from __future__ import annotations

import json
import logging

from django.contrib.auth import authenticate, get_user_model
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.phone_utils import find_user_by_phone
from workspace.export_security import require_export_authorization_api
from mobile_api.responses import api_error, api_ok
from mobile_api.services.crm_service import (
    complete_follow_up_task,
    complete_reminder,
    contact_detail_payload,
    create_activity,
    create_note,
    create_quick_lead,
    create_reminder,
    create_standalone_reminder,
    delete_reminder,
    get_contact,
    link_listing_to_contact,
    list_contacts,
    list_reminders,
    postpone_follow_up,
    postpone_reminder,
    today_payload,
    update_contact,
    update_reminder,
)
from mobile_api.services.dashboard_service import dashboard_payload
from mobile_api.services.deals_service import (
    change_deal_stage,
    create_deal_from_mobile,
    get_deal_detail,
    list_deals_paginated,
    pipeline_payload,
    stages_payload,
    update_deal_from_mobile,
)
from mobile_api.services.properties_service import (
    change_property_status,
    create_property_from_mobile,
    fetch_property_nearby_pois_from_mobile,
    get_property_detail,
    link_property_contact,
    list_properties_paginated,
    soft_delete_property,
    update_property_from_mobile,
    update_property_location_from_mobile,
    upload_property_image,
)
from mobile_api.services.device_service import deactivate_device, register_or_update_device, update_device_fcm
from mobile_api.services.documents_service import (
    delete_contact_document,
    delete_property_document,
    list_contact_documents,
    list_property_documents,
    send_listing_to_contact,
    upload_contact_document,
    upload_property_document,
)
from mobile_api.services.extraction_ingest import extraction_limits_payload, ingest_mobile_extraction
from mobile_api.services.filing_service import (
    dataset_detail_payload,
    delete_dataset,
    delete_dataset_consultants,
    delete_dataset_disguised_consultants,
    export_dataset_response,
    get_dataset,
    get_listing_detail,
    list_datasets,
    list_listings,
    rename_dataset,
    search_listings,
    toggle_listing_favorite,
    unlink_listing_contact,
    update_listing,
    update_listing_meta,
    delete_listing,
)
from mobile_api.services.mobile_export import export_contacts_response, export_properties_response
from mobile_api.services.insights_service import dataset_insights_payload, dataset_map_payload
from mobile_api.services.license_service import license_status_payload, require_light_extract
from mobile_api.pagination import clamp_page, clamp_page_size
from mobile_api.throttles import (
    MobileExtractionThrottle,
    MobileLoginThrottle,
    MobileRefreshThrottle,
    MobileUserThrottle,
)
from mobile_api.services.notification_service import (
    ensure_local_reminder_inbox,
    list_notifications_paginated,
    mark_all_read,
    mark_read,
    unread_count,
)
from mobile_api.services.sync_service import pull_sync, push_sync
from mobile_api.services.settings_service import (
    get_notification_prefs,
    get_profile,
    update_notification_prefs,
    update_profile,
    update_profile_avatar,
)
from mobile_api.services.schedule_service import (
    ScheduleRunError,
    create_schedule,
    delete_schedule,
    fail_schedule_run,
    get_schedule,
    list_due_schedules,
    list_runs,
    list_schedules,
    start_schedule_run,
    toggle_schedule,
    update_schedule,
)
from mobile_api.services.cloud_extract_service import (
    create_job as create_cloud_extraction_job,
    get_job as get_cloud_extraction_job,
    job_to_dict as cloud_job_to_dict,
    list_jobs as list_cloud_extraction_jobs,
)
from mobile_api.serializers import (
    activity_to_dict,
    contact_to_dict,
    deal_to_dict,
    document_to_dict,
    listing_to_dict,
    property_to_dict,
    property_contact_to_dict,
    reminder_to_dict,
    run_to_dict,
    schedule_to_dict,
)

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


class FileDownloadNegotiation(DefaultContentNegotiation):
    """جلوگیری از 404 درگاه DRF وقتی ?format=csv|xlsx برای فایل باینری ارسال می‌شود."""

    def select_renderer(self, request, renderers, format_suffix=None):
        renderer = renderers[0]
        return renderer, renderer.media_type


def _export_format(request, default: str = 'xlsx') -> str:
    raw = (
        request.query_params.get('export_format')
        or request.query_params.get('format')
        or default
    )
    return str(raw or default).strip().lower()


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return api_error('نام کاربری و رمز عبور الزامی است.', code='VALIDATION_ERROR')

        user = authenticate(request, username=username, password=password)
        if user is None:
            user = find_user_by_phone(username)
            if not user or not user.check_password(password):
                return api_error('نام کاربری یا رمز عبور اشتباه است.', code='AUTH_INVALID', status=401)

        tokens = _tokens_for_user(user)
        from mobile_api.serializers import user_to_dict
        return api_ok({**tokens, 'user': user_to_dict(user)})


class RefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MobileRefreshThrottle]

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
                token = RefreshToken(refresh_str)
                token.blacklist()
            except Exception:
                pass
        deactivate_device(request.user, _device_id(request))
        return api_ok({})


class AppVersionView(APIView):
    """نسخهٔ منتشرشده اپ اندروید — عمومی (بدون لاگین) برای آپدیت داخلی."""

    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]

    def get(self, request):
        from mobile_api.services.app_update_service import app_version_payload

        response = api_ok(app_version_payload(request))
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class DeviceRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        try:
            result = register_or_update_device(request.user, data)
            return api_ok(result)
        except ValueError as exc:
            msg = str(exc)
            if 'حداکثر تعداد دستگاه' in msg:
                return api_error(msg, code='LICENSE_DEVICE_LIMIT', status=403)
            return api_error(msg, code='VALIDATION_ERROR')


class DevicePatchView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        data = _parse_body(request)
        device_id = _device_id(request)
        if not device_id:
            return api_error('شناسه دستگاه در هدر الزامی است.', code='VALIDATION_ERROR')
        fcm_token = data.get('fcm_token', '')
        if update_device_fcm(request.user, device_id, fcm_token):
            return api_ok({})
        # دستگاه هنوز ثبت نشده (مثلاً بعد از به‌روزرسانی اپ) — ثبت سبک
        try:
            register_or_update_device(
                request.user,
                {
                    'device_id': device_id,
                    'fcm_token': fcm_token,
                    'device_model': request.headers.get('X-Device-Model', ''),
                    'app_version': request.headers.get('X-App-Version', ''),
                },
            )
            return api_ok({})
        except ValueError as exc:
            msg = str(exc)
            if 'حداکثر تعداد دستگاه' in msg:
                return api_error(msg, code='LICENSE_DEVICE_LIMIT', status=403)
            return api_error(msg, code='VALIDATION_ERROR')


class LicenseStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(license_status_payload(request.user))


class CrmNeighborhoodsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.crm_service import crm_neighborhoods_payload

        return api_ok(crm_neighborhoods_payload(request.user))


class ContactsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 50), default=50, maximum=100)
        params = {
            'q': request.GET.get('q', ''),
            'customer_type': request.GET.get('customer_type', ''),
            'status': request.GET.get('status', ''),
            'priority': request.GET.get('priority', ''),
            'due': request.GET.get('due', ''),
            'sort': request.GET.get('sort', ''),
            'tag': request.GET.get('tag', '') or request.GET.get('tags', ''),
        }
        items, meta = list_contacts(request.user, page=page, page_size=page_size, **params)
        return api_ok(items, meta=meta)


class ContactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contact_id):
        payload = contact_detail_payload(request.user, contact_id, request=request)
        if not payload:
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request, contact_id):
        data = _parse_body(request)
        try:
            c = update_contact(request.user, contact_id, data)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
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
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 20), default=20, maximum=100)
        items, meta = list_datasets(request.user, page=page, page_size=page_size)
        return api_ok(items, meta=meta)


class DatasetListingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dataset_id):
        from workspace.services.filters import parse_filter_params_from_mapping

        if not get_dataset(request.user, dataset_id):
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 50), default=50, maximum=100)
        filters = parse_filter_params_from_mapping(request.GET)
        items, meta = list_listings(
            request.user, dataset_id, page=page, page_size=page_size, filters=filters,
        )
        return api_ok(items, meta=meta)


class DatasetDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dataset_id):
        payload = dataset_detail_payload(request.user, dataset_id)
        if not payload:
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request, dataset_id):
        name = request.data.get('name') if isinstance(request.data, dict) else None
        payload, err = rename_dataset(request.user, str(dataset_id), name or '')
        if err == 'NOT_FOUND':
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        if err == 'INVALID_NAME':
            return api_error('نام فایل نامعتبر است.', code='VALIDATION', status=400)
        return api_ok(payload)

    def delete(self, request, dataset_id):
        if not delete_dataset(request.user, str(dataset_id)):
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'deleted': True})


class DatasetDeleteConsultantsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, dataset_id):
        payload, err, deleted = delete_dataset_consultants(request.user, str(dataset_id))
        if err == 'NOT_FOUND':
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'dataset': payload, 'deleted_count': deleted})


class DatasetDeleteDisguisedConsultantsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, dataset_id):
        payload, err, deleted = delete_dataset_disguised_consultants(request.user, str(dataset_id))
        if err == 'NOT_FOUND':
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'dataset': payload, 'deleted_count': deleted})


class DatasetInsightsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dataset_id):
        payload = dataset_insights_payload(request.user, dataset_id)
        if payload is None:
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class DatasetMapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dataset_id):
        payload = dataset_map_payload(request.user, dataset_id)
        if payload is None:
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class ListingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        payload = get_listing_detail(request.user, token, request)
        if not payload:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request, token):
        payload = update_listing(request.user, token, request.data, request)
        if not payload:
            return api_error('آگهی یافت نشد یا داده نامعتبر است.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def delete(self, request, token):
        payload = delete_listing(request.user, token)
        if not payload:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class ListingMetaView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, token):
        payload = update_listing_meta(request.user, token, request.data, request)
        if not payload:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class ListingFavoriteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        payload = toggle_listing_favorite(request.user, token, request)
        if not payload:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class ListingLinkedContactDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, token, link_id):
        payload = unlink_listing_contact(request.user, token, link_id, request)
        if not payload:
            return api_error('پیوند یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class ListingPublicShareView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        from mobile_api.services.filing_service import get_listing_public_share
        payload = get_listing_public_share(request.user, token, request)
        if not payload:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request, token):
        from mobile_api.services.filing_service import update_listing_public_share
        payload = update_listing_public_share(request.user, token, request.data, request)
        if not payload:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class DatasetExportView(APIView):
    permission_classes = [IsAuthenticated]
    content_negotiation_class = FileDownloadNegotiation

    def get(self, request, dataset_id):
        denied = require_export_authorization_api(request, request.user)
        if denied:
            return denied
        response, error_code = export_dataset_response(
            request.user,
            str(dataset_id),
            _export_format(request, 'xlsx'),
        )
        if error_code == 'LICENSE_REQUIRED':
            return api_error(
                'برای خروجی گرفتن از فایل، لایسنس فعال ربات نیاز است.',
                code='LICENSE_REQUIRED',
                status=403,
            )
        if error_code == 'NOT_FOUND' or response is None:
            return api_error('مجموعه یافت نشد.', code='NOT_FOUND', status=404)
        return response


class ContactsExportView(APIView):
    permission_classes = [IsAuthenticated]
    content_negotiation_class = FileDownloadNegotiation

    def get(self, request):
        denied = require_export_authorization_api(request, request.user)
        if denied:
            return denied
        return export_contacts_response(request.user, request.GET, _export_format(request, 'xlsx'))


class PropertiesExportView(APIView):
    permission_classes = [IsAuthenticated]
    content_negotiation_class = FileDownloadNegotiation

    def get(self, request):
        denied = require_export_authorization_api(request, request.user)
        if denied:
            return denied
        return export_properties_response(request.user, request.GET, _export_format(request, 'xlsx'))


class FilingSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.filters import parse_filter_params_from_mapping

        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 30), default=30, maximum=100)
        filters = parse_filter_params_from_mapping(request.GET)
        items, meta = search_listings(
            request.user, page=page, page_size=page_size, filters=filters,
        )
        return api_ok(items, meta=meta)


class ExtractionLimitsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(extraction_limits_payload(request.user))


class ExtractionUploadView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MobileExtractionThrottle]

    def post(self, request):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        data = _parse_body(request)
        try:
            result = ingest_mobile_extraction(request.user, data)
            return api_ok({
                'dataset_id': str(result.dataset.pk),
                'dataset_name': result.dataset.name,
                'ingested_count': result.ingested_count,
                'skipped_count': result.skipped_count,
                'created_count': result.created_count,
                'updated_count': result.updated_count,
                'duplicate_count': result.duplicate_count,
                'genuine_personal_count': result.genuine_personal_count,
                'disguised_consultant_count': result.disguised_consultant_count,
                'dataset_merged': result.dataset_merged,
                'total_in_dataset': result.dataset.row_count,
                'workspace_url': f'/workspace/datasets/{result.dataset.pk}/',
            })
        except ValueError as exc:
            msg = str(exc)
            code = 'RUN_ALREADY_FINISHED' if 'قبلاً تکمیل شده' in msg else 'VALIDATION_ERROR'
            return api_error(msg, code=code)
        except RuntimeError as exc:
            return api_error(str(exc), code='INGEST_ERROR', status=400)
        except Exception:
            logger.exception('mobile extraction upload failed for user=%s', request.user.pk)
            return api_error(
                'خطای داخلی سرور در ذخیره استخراج.',
                code='SERVER_ERROR',
                status=500,
            )


class ExtractionSchedulesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = [schedule_to_dict(s) for s in list_schedules(request.user)]
        return api_ok(items)

    def post(self, request):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        data = _parse_body(request)
        try:
            schedule = create_schedule(request.user, data, device_id=_device_id(request))
            return api_ok(schedule_to_dict(schedule), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ExtractionScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, schedule_id):
        schedule = get_schedule(request.user, schedule_id)
        if not schedule:
            return api_error('زمان‌بندی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(schedule_to_dict(schedule))

    def patch(self, request, schedule_id):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        data = _parse_body(request)
        schedule = update_schedule(request.user, schedule_id, data)
        if not schedule:
            return api_error('زمان‌بندی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(schedule_to_dict(schedule))

    def delete(self, request, schedule_id):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        if not delete_schedule(request.user, schedule_id):
            return api_error('زمان‌بندی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'deleted': True})


class ExtractionScheduleToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, schedule_id):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        data = _parse_body(request)
        enabled = data.get('is_enabled') if 'is_enabled' in data else None
        schedule = toggle_schedule(request.user, schedule_id, enabled=enabled)
        if not schedule:
            return api_error('زمان‌بندی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(schedule_to_dict(schedule))


class ExtractionScheduleRunsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, schedule_id):
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 20), default=20, maximum=100)
        runs, meta = list_runs(request.user, schedule_id, page=page, page_size=page_size)
        if not get_schedule(request.user, schedule_id):
            return api_error('زمان‌بندی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok([run_to_dict(r) for r in runs], meta=meta)


class ExtractionScheduleRunStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, schedule_id):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        data = _parse_body(request)
        trigger = (data.get('trigger') or 'device')[:20]
        try:
            run = start_schedule_run(
                request.user,
                schedule_id,
                trigger=trigger,
                device_id=_device_id(request),
            )
            schedule = get_schedule(request.user, schedule_id)
            return api_ok({
                'run': run_to_dict(run),
                'schedule': schedule_to_dict(schedule) if schedule else None,
                'filters': run.filters_snapshot,
            })
        except ScheduleRunError as exc:
            return api_error(str(exc), code=exc.code)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ExtractionScheduleRunFailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, run_id):
        data = _parse_body(request)
        run = fail_schedule_run(request.user, run_id, data.get('error') or data.get('message') or '')
        if not run:
            return api_error('اجرای استخراج یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(run_to_dict(run))


class ExtractionSchedulesDueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        due = list_due_schedules(request.user, device_id=_device_id(request))
        return api_ok([schedule_to_dict(s) for s in due])


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
        return api_ok(get_profile(request.user, request=request))

    def patch(self, request):
        data = _parse_body(request)
        return api_ok(update_profile(request.user, data, request=request))


class ProfileAvatarView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        avatar = request.FILES.get('avatar')
        if not avatar:
            return api_error('فایل تصویر ارسال نشده است.', code='VALIDATION_ERROR')
        try:
            return api_ok(update_profile_avatar(request.user, avatar=avatar, request=request))
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')

    def delete(self, request):
        return api_ok(update_profile_avatar(request.user, clear=True, request=request))


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


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return api_ok(dashboard_payload(request.user))
        except Exception:
            logging.getLogger(__name__).exception('dashboard_payload failed')
            return api_error('خطا در بارگذاری داشبورد', code='SERVER_ERROR', status=500)


class ContactActivitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        data = _parse_body(request)
        try:
            activity = create_activity(request.user, contact_id, data)
            return api_ok(activity_to_dict(activity), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ContactNotesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        data = _parse_body(request)
        try:
            activity = create_note(request.user, contact_id, data)
            return api_ok(activity_to_dict(activity), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ContactRemindersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        data = _parse_body(request)
        try:
            reminder = create_reminder(request.user, contact_id, data)
            return api_ok(reminder_to_dict(reminder), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ContactListingsLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        data = _parse_body(request)
        try:
            from mobile_api.serializers import linked_listing_to_dict
            link = link_listing_to_contact(request.user, contact_id, data)
            return api_ok(linked_listing_to_dict(link), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ContactDocumentsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, contact_id):
        if not get_contact(request.user, contact_id):
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        docs = list_contact_documents(request.user, contact_id, request=request)
        return api_ok(docs)

    def post(self, request, contact_id):
        uploaded = request.FILES.get('file')
        try:
            doc = upload_contact_document(
                request.user,
                contact_id,
                title=(request.POST.get('title') or '').strip(),
                uploaded_file=uploaded,
                doc_type=(request.POST.get('doc_type') or '').strip(),
                note=(request.POST.get('note') or '').strip(),
                request=request,
            )
            return api_ok(document_to_dict(doc, request=request), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ContactDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, contact_id, document_id):
        if not delete_contact_document(request.user, contact_id, document_id):
            return api_error('مدرک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'deleted': True})


class ContactSendListingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        data = _parse_body(request)
        try:
            result = send_listing_to_contact(request.user, contact_id, data)
            return api_ok(result, status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ContactMatchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contact_id):
        from workspace.services.crm_match_notifications import contact_matches_payload
        payload = contact_matches_payload(request.user, contact_id, request=request)
        if not payload:
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class ContactSuggestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        from workspace.services.crm_match_notifications import suggest_contact_matches
        data = _parse_body(request)
        selected = data.get('matches') or data.get('selected') or []
        if not isinstance(selected, list):
            return api_error('لیست ملک‌ها نامعتبر است.', code='VALIDATION_ERROR')
        try:
            text, count = suggest_contact_matches(
                request.user,
                contact_id,
                selected,
                note=(data.get('note') or ''),
                request=request,
            )
            if count <= 0:
                return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
            return api_ok({
                'suggested_count': count,
                'whatsapp_text': text,
            }, status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class PropertyContactMatchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        from workspace.services.crm_match_notifications import property_contact_matches_payload
        payload = property_contact_matches_payload(request.user, property_id, request=request)
        if not payload:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        if payload.get('forbidden'):
            return api_error(
                payload.get('message') or 'دسترسی مجاز نیست.',
                code='FORBIDDEN',
                status=403,
            )
        return api_ok(payload)


class PropertySuggestContactsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, property_id):
        from workspace.services.crm_match_notifications import suggest_property_contacts
        data = _parse_body(request)
        selected = data.get('customer_ids') or data.get('matches') or data.get('selected') or []
        if not isinstance(selected, list):
            return api_error('لیست مخاطبان نامعتبر است.', code='VALIDATION_ERROR')
        customer_ids = []
        for item in selected:
            if isinstance(item, dict):
                cid = item.get('customer_id') or item.get('id')
                if cid is not None:
                    customer_ids.append(cid)
            else:
                customer_ids.append(item)
        try:
            result = suggest_property_contacts(
                request.user,
                property_id,
                customer_ids,
                note=(data.get('note') or ''),
                request=request,
            )
            if not result.get('linked_count'):
                return api_error(
                    'هیچ مخاطبی پیوند نشد — دسترسی یا شناسه‌ها را بررسی کنید.',
                    code='NOT_FOUND',
                    status=404,
                )
            return api_ok({
                'suggested_count': result['linked_count'],
                'whatsapp_text': result.get('whatsapp_text') or '',
                'public_url': result.get('public_url') or '',
                'suggestions': result.get('suggestions') or [],
            }, status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class ReminderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, reminder_id):
        data = _parse_body(request)
        action = data.get('action')
        if action in ('complete', 'postpone', 'snooze'):
            if action == 'postpone' or action == 'snooze':
                days = int(data.get('days', 0) or 0)
                hours = int(data.get('hours', 0) or 0)
                if action == 'snooze' and hours == 0 and days == 0:
                    hours = int(data.get('minutes', 60) or 60) // 60 or 1
                r = postpone_reminder(request.user, reminder_id, days=days, hours=hours)
            else:
                r = complete_reminder(request.user, reminder_id, note=data.get('note', ''))
            if not r:
                return api_error('یادآور یافت نشد.', code='NOT_FOUND', status=404)
            return api_ok(reminder_to_dict(r))
        try:
            r = update_reminder(request.user, reminder_id, data)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        if not r:
            return api_error('یادآور یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(reminder_to_dict(r))

    def delete(self, request, reminder_id):
        if not delete_reminder(request.user, reminder_id):
            return api_error('یادآور یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({})


class RemindersListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import datetime
        from django.utils import timezone
        from django.utils.dateparse import parse_date, parse_datetime as parse_dt

        due_from_raw = request.GET.get('due_from') or request.GET.get('from')
        due_to_raw = request.GET.get('due_to') or request.GET.get('to')
        done_raw = request.GET.get('done')
        due_from = parse_dt(due_from_raw) if due_from_raw else None
        due_to = parse_dt(due_to_raw) if due_to_raw else None
        if due_from_raw and due_from is None:
            d = parse_date(due_from_raw)
            if d:
                due_from = timezone.make_aware(datetime.combine(d, datetime.min.time()))
        if due_to_raw and due_to is None:
            d = parse_date(due_to_raw)
            if d:
                due_to = timezone.make_aware(datetime.combine(d, datetime.max.time().replace(microsecond=0)))
        done = None
        if done_raw is not None and str(done_raw).strip() != '':
            done = str(done_raw).lower() in ('1', 'true', 'yes')
        items = list_reminders(
            request.user,
            due_from=due_from,
            due_to=due_to,
            done=done,
        )
        return api_ok([reminder_to_dict(r) for r in items])
    def post(self, request):
        data = _parse_body(request)
        try:
            reminder = create_standalone_reminder(request.user, data)
            return api_ok(reminder_to_dict(reminder), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class TodayTaskActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        contact_id = data.get('contact_id')
        reminder_id = data.get('reminder_id')
        action = data.get('action', 'complete')
        if not contact_id and not reminder_id:
            return api_error('شناسه مخاطب یا یادآور الزامی است.', code='VALIDATION_ERROR')
        if reminder_id:
            if action in ('postpone', 'snooze'):
                days = int(data.get('days', 0) or 0)
                hours = int(data.get('hours', 0) or 0)
                if action == 'snooze' and hours == 0 and days == 0:
                    hours = 1
                if days == 0 and hours == 0:
                    days = 1
                r = postpone_reminder(request.user, int(reminder_id), days=days, hours=hours)
                if not r:
                    return api_error('یادآور یافت نشد.', code='NOT_FOUND', status=404)
                return api_ok(reminder_to_dict(r))
            r = complete_reminder(request.user, int(reminder_id), note=data.get('note', ''))
            if not r:
                return api_error('یادآور یافت نشد.', code='NOT_FOUND', status=404)
            return api_ok(reminder_to_dict(r))
        if action == 'postpone':
            days = int(data.get('days', 1) or 1)
            c = postpone_follow_up(request.user, int(contact_id), days=days)
        else:
            c = complete_follow_up_task(request.user, int(contact_id), note=data.get('note', ''))
        if not c:
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(contact_to_dict(c))


class NotificationsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 20), default=20, maximum=100)
        items, meta = list_notifications_paginated(request.user, page=page, page_size=page_size)
        return api_ok(items, meta=meta)


class NotificationsUnreadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok({'count': unread_count(request.user)})


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        if not mark_read(request.user, notification_id):
            return api_error('اعلان یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({})


class NotificationsMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = mark_all_read(request.user)
        return api_ok({'count': count})


class NotificationLocalDeliveredView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        try:
            reminder_id = int(data.get('reminder_id') or 0)
        except (TypeError, ValueError):
            reminder_id = 0
        if reminder_id <= 0:
            return api_error('شناسه یادآور الزامی است.', code='VALIDATION_ERROR')
        note = ensure_local_reminder_inbox(request.user, reminder_id)
        if not note:
            return api_error('یادآور یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'notification_id': note.pk})


class DealsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 20), default=20, maximum=100)
        query = {
            'q': request.GET.get('q', ''),
            'stage': request.GET.get('stage', ''),
            'bucket': request.GET.get('bucket', ''),
            'customer_id': request.GET.get('customer_id', ''),
        }
        items, meta = list_deals_paginated(request.user, page=page, page_size=page_size, query=query)
        return api_ok(items, meta=meta)

    def post(self, request):
        data = _parse_body(request)
        try:
            deal = create_deal_from_mobile(request.user, data)
            payload = get_deal_detail(request.user, deal.pk)
            return api_ok(payload, status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class DealDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, deal_id):
        payload = get_deal_detail(request.user, deal_id)
        if not payload:
            return api_error('معامله یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request, deal_id):
        data = _parse_body(request)
        deal = update_deal_from_mobile(request.user, deal_id, data)
        if not deal:
            return api_error('معامله یافت نشد.', code='NOT_FOUND', status=404)
        payload = get_deal_detail(request.user, deal_id)
        return api_ok(payload)

    def delete(self, request, deal_id):
        from mobile_api.services.deals_service import delete_deal
        if not delete_deal(request.user, deal_id):
            return api_error('معامله یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({})


class DealChecklistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, deal_id):
        from mobile_api.services.deals_service import toggle_deal_checklist_item
        data = _parse_body(request)
        item_id = (data.get('item_id') or '').strip()
        if not item_id:
            return api_error('آیتم نامعتبر است.', code='VALIDATION_ERROR')
        try:
            result = toggle_deal_checklist_item(
                request.user,
                deal_id,
                item_id,
                done=data.get('done') if 'done' in data else None,
            )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        if not result:
            return api_error('معامله یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(result)


class DealStageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, deal_id):
        data = _parse_body(request)
        stage = (data.get('stage') or '').strip()
        if not stage:
            return api_error('مرحله الزامی است.', code='VALIDATION_ERROR')
        try:
            deal = change_deal_stage(
                request.user,
                deal_id,
                stage,
                lost_reason=(data.get('lost_reason') or '').strip(),
            )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        if not deal:
            return api_error('معامله یافت نشد.', code='NOT_FOUND', status=404)
        payload = get_deal_detail(request.user, deal_id)
        return api_ok(payload)


class DealPipelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(pipeline_payload(request.user))


class DealStagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok({'stages': stages_payload(request.user)})


class PropertiesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 20), default=20, maximum=100)
        query = {
            'q': request.GET.get('q', ''),
            'deal_mode': request.GET.get('deal_mode', ''),
            'transaction_status': request.GET.get('transaction_status', ''),
            'property_type': request.GET.get('property_type', ''),
            'city': request.GET.get('city', ''),
            'folder_id': request.GET.get('folder_id', ''),
        }
        items, meta = list_properties_paginated(
            request.user, page=page, page_size=page_size, query=query, request=request,
        )
        return api_ok(items, meta=meta)

    def post(self, request):
        data = _parse_body(request)
        try:
            prop = create_property_from_mobile(request.user, data)
            return api_ok(property_to_dict(prop, detailed=True, request=request), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class PropertyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        payload = get_property_detail(request.user, property_id, request=request)
        if not payload:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request, property_id):
        data = _parse_body(request)
        prop = update_property_from_mobile(request.user, property_id, data)
        if not prop:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(property_to_dict(prop, detailed=True, request=request))

    def delete(self, request, property_id):
        if not soft_delete_property(request.user, property_id):
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({})


class PropertyLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, property_id):
        data = _parse_body(request)
        try:
            payload = update_property_location_from_mobile(request.user, property_id, data)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        if not payload:
            return api_error('دسترسی ندارید.', code='FORBIDDEN', status=403)
        return api_ok(payload)


class PropertyNearbyPoisView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, property_id):
        data = _parse_body(request)
        force_refresh = bool(data.get('refresh'))
        try:
            result = fetch_property_nearby_pois_from_mobile(
                request.user,
                property_id,
                force_refresh=force_refresh,
            )
        except PermissionError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(result)


class PropertyFoldersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.crm_property_folders import list_property_folders, serialize_folder
        rows = list_property_folders(request.user)
        return api_ok([serialize_folder(f) for f in rows])

    def post(self, request):
        from workspace.services.crm_property_folders import create_property_folder, serialize_folder
        data = _parse_body(request)
        try:
            folder = create_property_folder(
                request.user,
                name=data.get('name', ''),
                description=data.get('description', ''),
                color=data.get('color', ''),
                icon=data.get('icon', ''),
                is_pinned=bool(data.get('is_pinned')),
            )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(serialize_folder(folder), status=201)


class PropertyFolderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, folder_id):
        from workspace.services.crm_property_folders import serialize_folder, update_property_folder
        try:
            folder = update_property_folder(request.user, folder_id, _parse_body(request))
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(serialize_folder(folder))

    def delete(self, request, folder_id):
        from workspace.services.crm_property_folders import delete_property_folder
        if not delete_property_folder(request.user, folder_id):
            return api_error('زونکن یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({})


class PropertyFolderReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from workspace.services.crm_property_folders import reorder_property_folders, serialize_folder
        data = _parse_body(request)
        folder_ids = data.get('folder_ids') or data.get('order') or []
        rows = reorder_property_folders(request.user, folder_ids)
        return api_ok([serialize_folder(f) for f in rows])


class PropertyFolderMembershipView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, folder_id, property_id):
        from workspace.services.crm_property_folders import add_property_to_folder, folder_for_user, serialize_folder
        try:
            add_property_to_folder(request.user, folder_id, property_id)
            folder = folder_for_user(request.user, folder_id)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(serialize_folder(folder) if folder else {})

    def delete(self, request, folder_id, property_id):
        from workspace.services.crm_property_folders import remove_property_from_folder
        try:
            remove_property_from_folder(request.user, folder_id, property_id)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({})


class PropertyPublicShareView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        from mobile_api.services.properties_service import get_property_public_share
        payload = get_property_public_share(request.user, property_id, request)
        if not payload:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request, property_id):
        from mobile_api.services.properties_service import update_property_public_share
        payload = update_property_public_share(
            request.user, property_id, request.data, request,
        )
        if not payload:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class PropertyStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, property_id):
        data = _parse_body(request)
        status = (data.get('transaction_status') or data.get('status') or '').strip()
        if not status:
            return api_error('وضعیت الزامی است.', code='VALIDATION_ERROR')
        try:
            prop = change_property_status(request.user, property_id, status)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        if not prop:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(property_to_dict(prop, detailed=True, request=request))


class PropertyContactsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, property_id):
        data = _parse_body(request)
        try:
            link = link_property_contact(request.user, property_id, data)
            return api_ok(property_contact_to_dict(link), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class PropertyDocumentsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, property_id):
        from workspace.services.crm_scope import property_for_user
        prop = property_for_user(request.user, property_id)
        if not prop:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        docs = list_property_documents(request.user, property_id, request=request)
        return api_ok(docs)

    def post(self, request, property_id):
        uploaded = request.FILES.get('file')
        try:
            doc = upload_property_document(
                request.user,
                property_id,
                title=(request.POST.get('title') or '').strip(),
                uploaded_file=uploaded,
                doc_type=(request.POST.get('doc_type') or '').strip(),
                note=(request.POST.get('note') or '').strip(),
                request=request,
            )
            return api_ok(document_to_dict(doc, request=request), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class PropertyDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, property_id, document_id):
        if not delete_property_document(request.user, property_id, document_id):
            return api_error('مدرک یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'deleted': True})


class PropertyImagesView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, property_id):
        uploaded = request.FILES.get('image')
        try:
            payload = upload_property_image(
                request.user,
                property_id,
                uploaded,
                request=request,
            )
            return api_ok(payload, status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class CloudExtractionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = [cloud_job_to_dict(j) for j in list_cloud_extraction_jobs(request.user)]
        return api_ok(items)

    def post(self, request):
        err = require_light_extract(request.user)
        if err:
            return api_error(err, code='LICENSE_REQUIRED', status=403)
        data = _parse_body(request)
        try:
            job = create_cloud_extraction_job(request.user, data)
            return api_ok(cloud_job_to_dict(job), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class CloudExtractionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = get_cloud_extraction_job(request.user, job_id)
        if not job:
            return api_error('کار استخراج یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(cloud_job_to_dict(job))


def _crm_template_to_dict(tpl) -> dict:
    return {
        'id': tpl.pk,
        'title': tpl.name,
        'body': tpl.body,
        'category': tpl.category,
    }


class CRMTemplatesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.crm_templates import list_templates
        items = [_crm_template_to_dict(t) for t in list_templates(request.user)]
        return api_ok(items)


class CRMSavedFiltersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.crm_saved_filters import (
            estimate_listings_new_count,
            list_saved_filters,
            serialize_filter,
        )
        entity = (request.GET.get('entity') or request.GET.get('scope') or '').strip()
        if not entity:
            return api_error('پارامتر entity الزامی است.', code='VALIDATION_ERROR')
        with_new = str(request.GET.get('include_new_count', '')).lower() in ('1', 'true', 'yes')
        rows = list_saved_filters(request.user, entity)
        items = []
        for f in rows:
            new_count = None
            if with_new and f.scope == 'listings':
                try:
                    new_count = estimate_listings_new_count(request.user, f)
                except Exception:
                    new_count = 0
            items.append(serialize_filter(f, new_count=new_count))
        return api_ok(items)

    def post(self, request):
        from workspace.services.crm_saved_filters import save_filter, serialize_filter

        data = _parse_body(request)
        name = (data.get('name') or '').strip()
        scope = (data.get('scope') or data.get('entity') or '').strip()
        params = data.get('params') or data.get('payload') or {}
        is_pinned = bool(data.get('is_pinned', False))
        if not isinstance(params, dict):
            return api_error('params باید آبجکت باشد.', code='VALIDATION_ERROR')
        try:
            obj = save_filter(
                request.user,
                name=name,
                scope=scope,
                params=params,
                is_pinned=is_pinned,
            )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(serialize_filter(obj), status=201)


class CRMSavedFilterDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, filter_id):
        from workspace.services.crm_saved_filters import delete_filter

        if not delete_filter(request.user, filter_id):
            return api_error('فیلتر یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'deleted': True})


class CRMSavedFilterPinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, filter_id):
        from workspace.models import CRMSavedFilter
        from workspace.services.crm_saved_filters import serialize_filter, toggle_pin

        try:
            obj = toggle_pin(request.user, filter_id)
        except CRMSavedFilter.DoesNotExist:
            return api_error('فیلتر یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(serialize_filter(obj))


def _ticket_to_dict(ticket, *, request=None, include_messages: bool = False) -> dict:
    from mobile_api.services.support_mobile import ticket_to_dict
    return ticket_to_dict(ticket, request=request, include_messages=include_messages)


class SupportTicketsListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.support_tickets import filter_user_tickets
        tickets = filter_user_tickets(request.user)
        return api_ok([_ticket_to_dict(t, request=request) for t in tickets[:50]])

    def post(self, request):
        from workspace.services.support_tickets import create_ticket
        from workspace.support_constants import TICKET_CATEGORY_OTHER, TICKET_PRIORITY_NORMAL

        data = _parse_body(request)
        subject = (data.get('subject') or '').strip()
        body = (data.get('body') or '').strip()
        if not subject:
            return api_error('موضوع الزامی است.', code='VALIDATION_ERROR')
        if not body:
            return api_error('متن پیام الزامی است.', code='VALIDATION_ERROR')
        category = (data.get('category') or TICKET_CATEGORY_OTHER).strip()
        priority = (data.get('priority') or TICKET_PRIORITY_NORMAL).strip()
        try:
            ticket = create_ticket(
                user=request.user,
                subject=subject,
                category=category,
                priority=priority,
                body=body,
            )
            return api_ok(_ticket_to_dict(ticket, request=request), status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class SupportTicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        from mobile_api.services.support_mobile import ticket_detail_payload
        payload = ticket_detail_payload(request.user, ticket_id, request=request)
        if not payload:
            return api_error('تیکت یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class SupportTicketReplyView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, ticket_id):
        from mobile_api.services.support_mobile import get_user_ticket, ticket_message_to_dict, ticket_to_dict
        from workspace.services.support_tickets import add_user_reply, validate_attachment_file

        ticket = get_user_ticket(request.user, ticket_id)
        if not ticket:
            return api_error('تیکت یافت نشد.', code='NOT_FOUND', status=404)
        body = (request.data.get('body') or '').strip()
        if not body:
            return api_error('متن پاسخ الزامی است.', code='VALIDATION_ERROR')
        attachment = request.FILES.get('attachment') or request.FILES.get('file')
        if attachment:
            err = validate_attachment_file(attachment)
            if err:
                return api_error(err, code='VALIDATION_ERROR')
        try:
            message = add_user_reply(
                ticket=ticket,
                user=request.user,
                body=body,
                attachment=attachment,
            )
            ticket.refresh_from_db()
            return api_ok({
                'ticket': ticket_to_dict(ticket, request=request),
                'message': ticket_message_to_dict(message, request=request),
            }, status=201)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')


class SupportTicketCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        from mobile_api.services.support_mobile import get_user_ticket, ticket_to_dict
        from workspace.services.support_tickets import close_ticket

        ticket = get_user_ticket(request.user, ticket_id)
        if not ticket:
            return api_error('تیکت یافت نشد.', code='NOT_FOUND', status=404)
        close_ticket(ticket=ticket, by_user=request.user, staff=False)
        ticket.refresh_from_db()
        return api_ok(ticket_to_dict(ticket, request=request))


class SupportTicketReopenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        from mobile_api.services.support_mobile import get_user_ticket, ticket_to_dict
        from workspace.services.support_tickets import reopen_ticket

        ticket = get_user_ticket(request.user, ticket_id)
        if not ticket:
            return api_error('تیکت یافت نشد.', code='NOT_FOUND', status=404)
        reopen_ticket(ticket=ticket)
        ticket.refresh_from_db()
        return api_ok(ticket_to_dict(ticket, request=request))


def _ai_quota_payload(user, *, enabled: bool | None = None):
    from ai_workspace.constants import is_ai_enabled
    from ai_workspace.services.quota import get_status
    from mobile_api.services.license_service import license_payload_for_user

    ai_enabled = is_ai_enabled() if enabled is None else bool(enabled)
    plan_label = license_payload_for_user(user).get('plan') or 'پلن'
    if not ai_enabled:
        return {
            'enabled': False,
            'remaining': 0,
            'limit': 0,
            'plan_label': plan_label,
        }
    try:
        status = get_status(user)
        return {
            'enabled': True,
            'remaining': status.remaining,
            'limit': status.daily_limit,
            'plan_label': plan_label,
        }
    except Exception:
        return {
            'enabled': True,
            'remaining': 0,
            'limit': 0,
            'plan_label': plan_label,
        }


def _ai_text_payload(*, text: str, quota_remaining: int, is_fallback: bool, summary=None):
    payload = {
        'text': text,
        'quota_remaining': quota_remaining,
        'is_fallback': bool(is_fallback),
        'source': 'fallback' if is_fallback else 'ai',
    }
    if summary is not None:
        payload['summary'] = summary
    return payload


def _fallback_draft_text(*, name: str, listing_token: str, tone: str, notes: str) -> str:
    listing_hint = f' (آگهی {listing_token})' if listing_token else ''
    tone_hint = f' — لحن {tone}' if tone else ''
    return (
        f'سلام {name or "مشتری"} عزیز،\n'
        f'در خصوص درخواست شما{listing_hint}{tone_hint} در خدمتم.\n'
        f'{notes}'.strip()
    ).strip()


def _fallback_listing_summary(listing) -> str:
    parts = [listing.title or 'آگهی']
    if listing.neighborhood or listing.city:
        parts.append(' — '.join(p for p in (listing.neighborhood, listing.city) if p))
    if listing.price:
        parts.append(f'قیمت: {listing.price:,}')
    elif listing.rent or listing.deposit:
        rent_part = f'اجاره {listing.rent:,}' if listing.rent else ''
        dep_part = f'ودیعه {listing.deposit:,}' if listing.deposit else ''
        parts.append(' · '.join(p for p in (dep_part, rent_part) if p))
    if listing.area:
        parts.append(f'متراژ {listing.area} متر')
    if listing.rooms:
        parts.append(f'{listing.rooms} خواب')
    return ' · '.join(str(p) for p in parts if p)


class AIQuotaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(_ai_quota_payload(request.user))


class AIDraftMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from ai_workspace.constants import is_ai_enabled, normalize_crm_tone
        from ai_workspace.services.crm_message import generate_message, result_to_dict as crm_result_to_dict
        from ai_workspace.services.gateway import FeatureDisabledError
        from ai_workspace.services.quota import QuotaExceededError, get_status
        from workspace.services.crm_scope import customer_for_user

        data = _parse_body(request)
        contact_id = data.get('contact_id')
        listing_token = (data.get('listing_token') or '').strip()
        intent = (data.get('intent') or '').strip()
        notes = (data.get('notes') or '').strip()
        tone = normalize_crm_tone(data.get('tone') or intent or 'رسمی')

        if not contact_id and not listing_token:
            return api_error(
                'حداقل شناسه مخاطب یا توکن آگهی لازم است.',
                code='VALIDATION_ERROR',
            )

        name = ''
        customer = None
        if contact_id:
            customer = customer_for_user(request.user, contact_id)
            if contact_id and not customer:
                return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
            if customer:
                name = customer.name or ''

        quota_payload = _ai_quota_payload(request.user)
        quota_remaining = int(quota_payload.get('remaining') or 0)

        if is_ai_enabled() and customer:
            try:
                result = generate_message(request.user, customer, tone=tone)
                payload = crm_result_to_dict(result)
                quota_remaining = get_status(request.user).remaining
                text = payload.get('text') or ''
                if notes and notes not in text:
                    text = f'{text}\n\n{notes}'.strip()
                return api_ok(
                    _ai_text_payload(
                        text=text,
                        quota_remaining=quota_remaining,
                        is_fallback=bool(payload.get('is_fallback')),
                    )
                )
            except QuotaExceededError as exc:
                return api_error(
                    str(exc) or 'سهمیه روزانه AI تمام شده است.',
                    code='QUOTA_EXCEEDED',
                    status=429,
                )
            except FeatureDisabledError:
                pass
            except Exception:
                logger.exception('ai draft-message failed for user=%s', request.user.pk)

        text = _fallback_draft_text(
            name=name,
            listing_token=listing_token,
            tone=tone,
            notes=notes,
        )
        return api_ok(
            _ai_text_payload(
                text=text,
                quota_remaining=quota_remaining,
                is_fallback=True,
            )
        )


class AISummarizeListingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from ai_workspace.constants import is_ai_enabled
        from ai_workspace.services.gateway import FeatureDisabledError
        from ai_workspace.services.listing_summary import generate_summary, result_to_dict as listing_result_to_dict
        from ai_workspace.services.quota import QuotaExceededError, get_status
        from workspace.models import Listing

        data = _parse_body(request)
        listing_token = (data.get('listing_token') or '').strip()
        if not listing_token:
            return api_error('شناسه آگهی الزامی است.', code='VALIDATION_ERROR')

        listing = (
            Listing.objects.filter(dataset__user=request.user, token=listing_token)
            .select_related('dataset')
            .order_by('-created_at', '-id')
            .first()
        )
        if not listing:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)

        quota_payload = _ai_quota_payload(request.user)
        quota_remaining = int(quota_payload.get('remaining') or 0)

        if is_ai_enabled():
            try:
                result = generate_summary(request.user, listing.dataset, listing)
                payload = listing_result_to_dict(result)
                summary_data = payload.get('data') or {}
                text = summary_data.get('summary') if isinstance(summary_data, dict) else ''
                if not text:
                    text = (result.text or '').strip()
                if text:
                    quota_remaining = get_status(request.user).remaining
                    return api_ok(
                        _ai_text_payload(
                            text=text,
                            quota_remaining=quota_remaining,
                            is_fallback=bool(getattr(result, 'is_fallback', False) or payload.get('is_fallback')),
                            summary=summary_data,
                        )
                    )
            except QuotaExceededError as exc:
                return api_error(
                    str(exc) or 'سهمیه روزانه AI تمام شده است.',
                    code='QUOTA_EXCEEDED',
                    status=429,
                )
            except FeatureDisabledError:
                pass
            except Exception:
                logger.exception('ai summarize-listing failed token=%s', listing_token)

        text = _fallback_listing_summary(listing)
        return api_ok(
            _ai_text_payload(
                text=text,
                quota_remaining=quota_remaining,
                is_fallback=True,
                summary={'summary': text},
            )
        )

