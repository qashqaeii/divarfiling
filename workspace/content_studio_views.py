"""API استودیوی هوشمند ملک."""
from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views import View

from workspace.mixins import WorkspaceLoginMixin
from workspace.services.crm_scope import property_for_user
from workspace.services.property_content_studio.brand import save_user_brand_defaults
from workspace.services.property_content_studio.draft import delete_draft, save_draft
from workspace.services.property_content_studio.session import build_studio_session

logger = logging.getLogger(__name__)


def _parse_json(request) -> dict:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def _property_or_404(user, property_id):
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at:
        return None
    return prop


class PropertyContentStudioSessionView(WorkspaceLoginMixin, View):
    """بارگذاری اولیه استودیو."""

    def get(self, request, property_id):
        prop = _property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        from workspace.services.crm_property_share import build_property_share_context

        share_ctx = build_property_share_context(request.user, prop)
        data = build_studio_session(
            request.user,
            prop,
            request,
            mask_sensitive=share_ctx.mask_sensitive,
        )
        return JsonResponse(data)


class PropertyContentStudioDraftView(WorkspaceLoginMixin, View):
    def put(self, request, property_id):
        prop = _property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        body = _parse_json(request)
        payload = body.get('draft') or body.get('payload') or body
        if not isinstance(payload, dict):
            return JsonResponse({'ok': False, 'error': 'فرمت پیش‌نویس نامعتبر است'}, status=400)
        saved = save_draft(request.user, prop, payload)
        return JsonResponse({'ok': True, 'draft': saved})

    def delete(self, request, property_id):
        prop = _property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        delete_draft(request.user, prop)
        return JsonResponse({'ok': True})


class PropertyContentStudioBrandView(WorkspaceLoginMixin, View):
    def put(self, request, property_id):
        prop = _property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        body = _parse_json(request)
        brand = save_user_brand_defaults(request.user, body)
        return JsonResponse({'ok': True, 'brand': brand})


class PropertyContentStudioAIView(WorkspaceLoginMixin, View):
    def post(self, request, property_id, action):
        from ai_workspace.constants import FEATURE_PROPERTY_CONTENT_STUDIO, is_ai_enabled, is_feature_enabled
        from ai_workspace.services.gateway import FeatureDisabledError
        from ai_workspace.services.property_content_studio_ai import (
            generate_divar_body,
            generate_divar_titles,
            generate_social_pack,
        )
        from ai_workspace.services.quota import QuotaExceededError, quota_error_response

        if not is_ai_enabled():
            return JsonResponse({'ok': False, 'error': 'سرویس AI فعلاً غیرفعال است.'}, status=503)
        if not is_feature_enabled(FEATURE_PROPERTY_CONTENT_STUDIO, request.user):
            return JsonResponse({'ok': False, 'error': 'قابلیت AI استودیو غیرفعال است.'}, status=403)

        prop = _property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)

        body = _parse_json(request)
        try:
            if action == 'divar-titles':
                return JsonResponse(generate_divar_titles(request.user, property_id))
            if action == 'divar-body':
                style = (body.get('style') or 'formal').strip()
                return JsonResponse(generate_divar_body(request.user, property_id, style))
            if action == 'social':
                return JsonResponse(generate_social_pack(request.user, property_id))
            return JsonResponse({'ok': False, 'error': 'عملیات نامعتبر'}, status=400)
        except LookupError:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        except FeatureDisabledError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except QuotaExceededError as exc:
            return JsonResponse(quota_error_response(request.user, exc), status=429)
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'پاسخ AI نامعتبر بود. دوباره تلاش کنید.'}, status=502)
        except Exception:
            logger.exception('content_studio_ai_failed property_id=%s action=%s', property_id, action)
            return JsonResponse({'ok': False, 'error': 'خطا در تولید محتوا'}, status=500)
