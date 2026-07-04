"""API views — AI workspace."""
from __future__ import annotations

import json
import uuid

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from ai_workspace.constants import normalize_crm_tone
from ai_workspace.services.crm_message import generate_message, result_to_dict as crm_result_to_dict
from ai_workspace.services.gateway import FeatureDisabledError
from ai_workspace.services.listing_summary import generate_summary, result_to_dict as listing_result_to_dict
from ai_workspace.services.quota import QuotaExceededError, get_status, status_to_dict
from ai_workspace.services.upload_brief import generate_brief, result_to_dict as upload_result_to_dict
from workspace.mixins import LicenseRequiredMixin
from workspace.models import Dataset, Listing
from workspace.services.crm_scope import customer_for_user


class AIEnabledMixin(LicenseRequiredMixin):
    """نیاز به لایسنس + AI_ENABLED."""

    def dispatch(self, request, *args, **kwargs):
        if not is_ai_enabled():
            return JsonResponse({'ok': False, 'error': 'سرویس AI فعلاً غیرفعال است.'}, status=503)
        return super().dispatch(request, *args, **kwargs)


class AIQuotaView(AIEnabledMixin, View):
    def get(self, request):
        return JsonResponse({'ok': True, **status_to_dict(get_status(request.user))})


class ListingSummaryView(AIEnabledMixin, View):
    def post(self, request, dataset_id, listing_id):
        dataset = get_object_or_404(Dataset, pk=dataset_id, user=request.user)
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        try:
            result = generate_summary(request.user, dataset, listing)
            return JsonResponse(listing_result_to_dict(result))
        except FeatureDisabledError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except QuotaExceededError as exc:
            return JsonResponse({'ok': False, 'error': str(exc), 'code': exc.code}, status=429)


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
            return JsonResponse({'ok': False, 'error': str(exc), 'code': exc.code}, status=429)


class UploadBriefView(AIEnabledMixin, View):
    def post(self, request):
        upload_batch = request.session.get('upload_batch')
        if not upload_batch:
            return JsonResponse(
                {'ok': False, 'error': 'اطلاعات آپلود اخیر یافت نشد. ابتدا فایل آپلود کنید.'},
                status=400,
            )
        dataset = None
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            body = {}
        ds_id = body.get('dataset_id')
        if ds_id:
            try:
                dataset = Dataset.objects.filter(user=request.user, pk=uuid.UUID(str(ds_id))).first()
            except (ValueError, TypeError):
                dataset = None
        if not dataset:
            imported = upload_batch.get('imported') or []
            if imported:
                first_ds = imported[0].get('id') or imported[0].get('dataset_id')
                if first_ds:
                    dataset = Dataset.objects.filter(user=request.user, pk=first_ds).first()
        try:
            result = generate_brief(request.user, upload_batch, dataset)
            return JsonResponse(upload_result_to_dict(result))
        except FeatureDisabledError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except QuotaExceededError as exc:
            return JsonResponse({'ok': False, 'error': str(exc), 'code': exc.code}, status=429)
