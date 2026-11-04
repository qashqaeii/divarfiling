"""Property Content Studio — JWT mobile API (parity with workspace content studio)."""
from __future__ import annotations

import logging

from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ai_workspace.constants import FEATURE_PROPERTY_CONTENT_STUDIO, is_ai_enabled, is_feature_enabled
from ai_workspace.services.gateway import FeatureDisabledError
from ai_workspace.services.property_content_studio_ai import (
    generate_divar_body,
    generate_divar_titles,
    generate_poster_headlines,
    generate_social_pack,
)
from ai_workspace.services.quota import QuotaExceededError, quota_error_response
from mobile_api.authentication import MobileJWTAuthentication
from mobile_api.responses import api_error, api_ok
from mobile_api.views import _parse_body
from workspace.services.property_content_studio.access import resolve_studio_access
from workspace.services.property_content_studio.brand import save_user_brand_defaults
from workspace.services.property_content_studio.draft import (
    delete_draft,
    export_draft_payload_for_access,
    save_draft,
    sync_draft_with_property,
)
from workspace.services.property_content_studio.draft_validate import DraftValidationError
from workspace.services.property_content_studio.manifest import (
    ManifestNotFoundError,
    ManifestUnavailableError,
    ManifestVersionMismatchError,
    build_templates_catalog,
    enrich_property_templates_for_mobile,
    get_template_manifest,
)
from workspace.services.property_content_studio.constants import OUTPUT_FORMATS
from workspace.services.property_content_studio.mobile_export import (
    enrich_property_payload_for_mobile_export,
    export_mobile_studio_data,
)
from workspace.services.property_content_studio.session import build_studio_session

logger = logging.getLogger(__name__)

_AI_ACTIONS = frozenset({'divar-titles', 'divar-body', 'poster-headlines', 'social'})
_FORMAT_IDS = frozenset(OUTPUT_FORMATS.keys())


class PCSManifestJsonNegotiation(DefaultContentNegotiation):
    """Ignore ?format= for renderer selection — canvas format is a query param, not Accept."""

    def select_renderer(self, request, renderers, format_suffix=None):
        renderer = renderers[0]
        return renderer, renderer.media_type


def _canvas_format_param(request, *, default: str = 'story') -> str:
    raw = (
        request.query_params.get('canvas_format')
        or request.query_params.get('output_format')
        or request.query_params.get('format')
        or default
    )
    return str(raw or default).strip().lower()


def _resolve_property(request, property_id):
    prop, share_ctx = resolve_studio_access(request.user, property_id)
    if not prop:
        return None, None, api_error('فایل شخصی یافت نشد', code='NOT_FOUND', status=404)
    return prop, share_ctx, None


def _mobile_session_payload(user, prop, request, share_ctx) -> dict:
    session = build_studio_session(
        user,
        prop,
        request,
        mask_sensitive=share_ctx.mask_sensitive,
    )
    data = {key: val for key, val in session.items() if key != 'ok'}
    data['can_edit_property'] = share_ctx.can_edit
    data['property'] = enrich_property_templates_for_mobile(
        enrich_property_payload_for_mobile_export(
            data.get('property') or {},
            prop,
            mask_sensitive=share_ctx.mask_sensitive,
        ),
        request,
    )
    data['templates_catalog'] = build_templates_catalog(request)
    return export_mobile_studio_data(data, prop, mask_sensitive=share_ctx.mask_sensitive)


class PropertyContentStudioSessionView(APIView):
    authentication_classes = [MobileJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        prop, share_ctx, err = _resolve_property(request, property_id)
        if err:
            return err
        return api_ok(_mobile_session_payload(request.user, prop, request, share_ctx))


class PropertyContentStudioDraftView(APIView):
    authentication_classes = [MobileJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, property_id):
        prop, share_ctx, err = _resolve_property(request, property_id)
        if err:
            return err
        body = _parse_body(request)
        if body.get('sync_property'):
            meta = sync_draft_with_property(
                request.user,
                prop,
                mask_sensitive=share_ctx.mask_sensitive,
            )
            payload = {
                'draft_stale': meta['stale'],
                'property_fingerprint': meta['fingerprint'],
                'needs_manual_review': meta.get('needs_manual_review', False),
                'draft': meta.get('draft'),
                'property': enrich_property_templates_for_mobile(
                    enrich_property_payload_for_mobile_export(
                        meta.get('property') or {},
                        prop,
                        mask_sensitive=share_ctx.mask_sensitive,
                    ),
                    request,
                ),
            }
            return api_ok(payload)
        payload = body.get('draft') or body.get('payload') or body
        if not isinstance(payload, dict):
            return api_error('فرمت پیش‌نویس نامعتبر است', code='VALIDATION_ERROR', status=400)
        try:
            saved, meta = save_draft(
                request.user,
                prop,
                payload,
                sync_property=bool(body.get('sync_property_content')),
            )
        except DraftValidationError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR', status=400)
        draft_out = export_draft_payload_for_access(
            saved,
            mask_sensitive=share_ctx.mask_sensitive,
            prop=prop,
        )
        return api_ok({
            'draft': draft_out,
            'draft_stale': meta['stale'],
            'property_fingerprint': meta['fingerprint'],
        })

    def delete(self, request, property_id):
        prop, _, err = _resolve_property(request, property_id)
        if err:
            return err
        delete_draft(request.user, prop)
        return api_ok({'deleted': True})


class PropertyContentStudioBrandView(APIView):
    authentication_classes = [MobileJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, property_id):
        prop, _, err = _resolve_property(request, property_id)
        if err:
            return err
        body = _parse_body(request)
        brand = save_user_brand_defaults(request.user, body)
        return api_ok({'brand': brand})


class PropertyContentStudioAIView(APIView):
    authentication_classes = [MobileJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, property_id, action):
        action = (action or '').strip().lower()
        if action not in _AI_ACTIONS:
            return api_error('عملیات نامعتبر', code='VALIDATION_ERROR', status=400)

        if not is_ai_enabled():
            return api_error('سرویس AI فعلاً غیرفعال است.', code='SERVICE_UNAVAILABLE', status=503)
        if not is_feature_enabled(FEATURE_PROPERTY_CONTENT_STUDIO, request.user):
            return api_error('قابلیت AI استودیو غیرفعال است.', code='FORBIDDEN', status=403)

        prop, share_ctx, err = _resolve_property(request, property_id)
        if err:
            return err

        body = _parse_body(request)
        mask = share_ctx.mask_sensitive
        try:
            if action == 'divar-titles':
                result = generate_divar_titles(request.user, property_id, mask_sensitive=mask)
            elif action == 'poster-headlines':
                result = generate_poster_headlines(request.user, property_id, mask_sensitive=mask)
            elif action == 'divar-body':
                style = (body.get('style') or 'formal').strip()
                result = generate_divar_body(
                    request.user,
                    property_id,
                    style,
                    mask_sensitive=mask,
                )
            else:
                result = generate_social_pack(request.user, property_id, mask_sensitive=mask)
        except LookupError:
            return api_error('فایل شخصی یافت نشد', code='NOT_FOUND', status=404)
        except FeatureDisabledError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        except QuotaExceededError as exc:
            q = quota_error_response(request.user, exc)
            return api_error(
                q.get('error', 'سهمیه AI'),
                code='QUOTA_EXCEEDED',
                status=429,
                retry_after=q.get('retry_after'),
            )
        except ValueError:
            return api_error('پاسخ AI نامعتبر بود. دوباره تلاش کنید.', code='BAD_GATEWAY', status=502)
        except Exception:
            logger.exception(
                'mobile_content_studio_ai_failed property_id=%s action=%s',
                property_id,
                action,
            )
            return api_error('خطا در تولید محتوا', code='ERROR', status=500)

        data = {key: val for key, val in result.items() if key != 'ok'}
        return api_ok(data)


class PropertyContentStudioTemplateManifestView(APIView):
    authentication_classes = [MobileJWTAuthentication]
    permission_classes = [IsAuthenticated]
    content_negotiation_class = PCSManifestJsonNegotiation

    def get(self, request, property_id, template_id):
        _, _, err = _resolve_property(request, property_id)
        if err:
            return err
        fmt = _canvas_format_param(request)
        if fmt not in _FORMAT_IDS:
            return api_error('فرمت نامعتبر است', code='VALIDATION_ERROR', status=400)
        try:
            manifest = get_template_manifest(template_id, fmt, request)
        except ManifestNotFoundError:
            return api_error('قالب یا فرمت نامعتبر است', code='NOT_FOUND', status=404)
        except ManifestVersionMismatchError:
            return api_error(
                'نسخه Manifest با سرور هماهنگ نیست؛ دوباره بارگذاری کنید.',
                code='MANIFEST_VERSION_MISMATCH',
                status=503,
            )
        except ManifestUnavailableError as exc:
            return api_error(str(exc), code='MANIFEST_UNAVAILABLE', status=503)
        return api_ok(manifest)
