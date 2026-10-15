"""API views — AI workspace."""
from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from ai_workspace.constants import FEATURE_UPLOAD_BRIEF, is_ai_enabled, is_feature_enabled, normalize_crm_tone
from ai_workspace.services.crm_message import generate_message, result_to_dict as crm_result_to_dict
from ai_workspace.services.gateway import FeatureDisabledError
from ai_workspace.services.listing_summary import generate_summary, result_to_dict as listing_result_to_dict
from ai_workspace.services.listing_summary_prefs import parse_listing_summary_preferences, preference_labels
from ai_workspace.services.property_summary import generate_summary_for_user
from ai_workspace.services.property_summary_skip import (
    PropertySummaryInsufficientContext,
    property_summary_skipped_dict,
)
from ai_workspace.services.quota import QuotaExceededError, get_status, quota_error_response, status_to_dict
from workspace.mixins import WorkspaceLoginMixin
from workspace.models import Dataset, Listing
from workspace.services.crm_scope import customer_for_user

logger = logging.getLogger(__name__)

class AIEnabledMixin(WorkspaceLoginMixin):
    """ورود + AI_ENABLED — سهمیه و مجوز قابلیت در gateway."""

    def dispatch(self, request, *args, **kwargs):
        if not is_ai_enabled():
            return JsonResponse({'ok': False, 'error': 'سرویس AI فعلاً غیرفعال است.'}, status=503)
        return super().dispatch(request, *args, **kwargs)


class AIQuotaView(AIEnabledMixin, View):
    def get(self, request):
        return JsonResponse({'ok': True, **status_to_dict(get_status(request.user))})


def _parse_ai_json_body(request) -> dict:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


class ListingSummaryView(AIEnabledMixin, View):
    def post(self, request, dataset_id, listing_id):
        dataset = get_object_or_404(Dataset, pk=dataset_id, user=request.user)
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        body = _parse_ai_json_body(request)
        tone, style = parse_listing_summary_preferences(body)
        try:
            result = generate_summary(
                request.user, dataset, listing, tone=tone, style=style,
            )
            return JsonResponse(listing_result_to_dict(
                result,
                user=request.user,
                preferences=preference_labels(tone, style),
            ))
        except FeatureDisabledError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except QuotaExceededError as exc:
            return JsonResponse(quota_error_response(request.user, exc), status=429)


class PropertySummaryView(AIEnabledMixin, View):
    def post(self, request, property_id):
        body = _parse_ai_json_body(request)
        tone, style = parse_listing_summary_preferences(body)
        try:
            result = generate_summary_for_user(
                request.user, property_id, tone=tone, style=style,
            )
            return JsonResponse(listing_result_to_dict(
                result,
                user=request.user,
                preferences=preference_labels(tone, style),
            ))
        except PropertySummaryInsufficientContext as exc:
            return JsonResponse(
                property_summary_skipped_dict(
                    request.user,
                    reason=exc.reason,
                    message=exc.message,
                )
            )
        except LookupError:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        except FeatureDisabledError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except QuotaExceededError as exc:
            return JsonResponse(quota_error_response(request.user, exc), status=429)


class CRMMessageView(AIEnabledMixin, View):
    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            body = {}
        channel = body.get('channel') or 'واتساپ'
        tone = normalize_crm_tone(body.get('tone'))
        try:
            result = generate_message(
                request.user, customer, channel=channel, tone=tone,
            )
            return JsonResponse(crm_result_to_dict(result))
        except FeatureDisabledError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except QuotaExceededError as exc:
            return JsonResponse(quota_error_response(request.user, exc), status=429)
        except Exception:
            logger.exception('crm_message_failed customer_id=%s tone=%s', customer_id, tone)
            return JsonResponse(
                {'ok': False, 'error': 'خطا در سرویس AI. لطفاً دوباره تلاش کنید.'},
                status=500,
            )


class UploadBriefView(AIEnabledMixin, View):
    """Legacy endpoint — upload AI brief غیرفعال است؛ هیچ LLM/provider صدا زده نمی‌شود."""

    def post(self, request):
        if not is_feature_enabled(FEATURE_UPLOAD_BRIEF, request.user):
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'تحلیل هوشمند آپلود فعلاً غیرفعال است.',
                    'code': 'feature_disabled',
                },
                status=403,
            )
        return JsonResponse(
            {'ok': False, 'error': 'تحلیل هوشمند آپلود فعلاً غیرفعال است.', 'code': 'feature_disabled'},
            status=403,
        )
