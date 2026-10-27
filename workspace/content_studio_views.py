"""API استودیوی هوشمند ملک."""
from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views import View

from workspace.mixins import WorkspaceLoginMixin
from workspace.services.property_content_studio.access import resolve_studio_access
from workspace.services.property_content_studio.brand import save_user_brand_defaults
from workspace.services.property_content_studio.draft import (
    delete_draft,
    save_draft,
    sync_draft_with_property,
)
from workspace.services.property_content_studio.draft_validate import DraftValidationError
from workspace.services.property_content_studio.session import build_studio_session

logger = logging.getLogger(__name__)


def _parse_json(request) -> dict:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def _studio_property_or_404(user, property_id):
    prop, share_ctx = resolve_studio_access(user, property_id)
    if not prop:
        return None, None
    return prop, share_ctx


class PropertyContentStudioSessionView(WorkspaceLoginMixin, View):
    """بارگذاری اولیه استودیو."""

    def get(self, request, property_id):
        prop, share_ctx = _studio_property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        data = build_studio_session(
            request.user,
            prop,
            request,
            mask_sensitive=share_ctx.mask_sensitive,
        )
        data['can_edit_property'] = share_ctx.can_edit
        return JsonResponse(data)


class PropertyContentStudioDraftView(WorkspaceLoginMixin, View):
    def put(self, request, property_id):
        prop, share_ctx = _studio_property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        body = _parse_json(request)
        if body.get('sync_property'):
            meta = sync_draft_with_property(request.user, prop)
            return JsonResponse({'ok': True, 'draft_stale': meta['stale'], 'property_fingerprint': meta['fingerprint']})
        payload = body.get('draft') or body.get('payload') or body
        if not isinstance(payload, dict):
            return JsonResponse({'ok': False, 'error': 'فرمت پیش‌نویس نامعتبر است'}, status=400)
        try:
            saved, meta = save_draft(
                request.user,
                prop,
                payload,
                sync_property=bool(body.get('sync_property_content')),
            )
        except DraftValidationError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({
            'ok': True,
            'draft': saved,
            'draft_stale': meta['stale'],
            'property_fingerprint': meta['fingerprint'],
        })

    def delete(self, request, property_id):
        prop, _ = _studio_property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        delete_draft(request.user, prop)
        return JsonResponse({'ok': True})


class PropertyContentStudioBrandView(WorkspaceLoginMixin, View):
    def put(self, request, property_id):
        prop, _ = _studio_property_or_404(request.user, property_id)
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

        prop, share_ctx = _studio_property_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)

        body = _parse_json(request)
        try:
            if action == 'divar-titles':
                return JsonResponse(
                    generate_divar_titles(request.user, property_id, mask_sensitive=share_ctx.mask_sensitive),
                )
            if action == 'divar-body':
                style = (body.get('style') or 'formal').strip()
                return JsonResponse(
                    generate_divar_body(
                        request.user, property_id, style, mask_sensitive=share_ctx.mask_sensitive,
                    ),
                )
            if action == 'social':
                return JsonResponse(
                    generate_social_pack(request.user, property_id, mask_sensitive=share_ctx.mask_sensitive),
                )
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
