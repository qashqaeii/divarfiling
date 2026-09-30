"""API وب فضای آژانس — /workspace/api/crm/agency/space/

Web Phase 1–3: frozen — parity changes go through mobile API + Android native.
"""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from workspace.services.agency_space_access import can_access_agency_space, get_user_space_agency
from workspace.services.agency_space_analytics import (
    can_view_space_analytics,
    get_space_analytics_payload,
)
from workspace.services.agency_space_moderation import (
    AgencySpaceModerationError,
    hide_space_item_public,
    restore_space_item_moderation,
)
from workspace.services.agency_space_params import filters_to_legacy_kwargs, parse_space_list_filters
from workspace.services.agency_space_publish import (
    AgencySpacePublishError,
    publish_customer,
    publish_property,
    unpublish_space_item,
    update_space_item,
)
from workspace.services.agency_space_copy import (
    AgencySpaceCopyError,
    copy_result_to_api_dict,
    copy_space_item_to_personal_crm,
)
from workspace.services.agency_space_query import (
    get_space_item_for_user,
    get_space_items_from_filters,
    paginate_space_items,
)
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.services.agency_space_ui_context import prefetch_publisher_workspace_for_space_items
from workspace.services.crm_agency_features import is_agency_feature_enabled


class _AgencySpaceAPIBase(LoginRequiredMixin, View):
    def _feature_ok(self, request):
        agency = get_user_space_agency(request.user)
        if not is_agency_feature_enabled('agency_space', agency):
            return self._err('قابلیت فعال نیست', 404)
        if not can_access_agency_space(request.user, agency):
            return self._err('دسترسی مجاز نیست', 403)
        return None

    def _err(self, msg, code=400):
        return JsonResponse({'ok': False, 'error': msg}, status=code)

    def _json_body(self, request):
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return None


class AgencySpaceItemsAPIView(_AgencySpaceAPIBase):
    def get(self, request):
        if (err := self._feature_ok(request)):
            return err
        filters = parse_space_list_filters(request.GET)
        legacy = filters_to_legacy_kwargs(filters)
        rows, total, num_pages = paginate_space_items(
            get_space_items_from_filters(request.user, filters),
            filters.page,
            filters.page_size,
        )
        row_list = list(rows)
        prefetch_publisher_workspace_for_space_items(row_list)
        items = [
            serialize_space_item(i, request.user, detail=False, request=request)
            for i in row_list
        ]
        return JsonResponse({
            'ok': True,
            'items': [i for i in items if i],
            'total': total,
            'page': filters.page,
            'num_pages': num_pages,
            'filters': legacy,
        })


class AgencySpaceAnalyticsAPIView(_AgencySpaceAPIBase):
    def get(self, request):
        if (err := self._feature_ok(request)):
            return err
        agency = get_user_space_agency(request.user)
        if not can_view_space_analytics(request.user, agency):
            return self._err('دسترسی مجاز نیست', 403)
        return JsonResponse({
            'ok': True,
            'analytics': get_space_analytics_payload(agency),
        })


class AgencySpaceItemAPIView(_AgencySpaceAPIBase):
    def get(self, request, item_id: int):
        if (err := self._feature_ok(request)):
            return err
        item = get_space_item_for_user(request.user, item_id)
        if not item:
            return self._err('آیتم یافت نشد', 404)
        prefetch_publisher_workspace_for_space_items([item])
        data = serialize_space_item(item, request.user, detail=True, request=request)
        return JsonResponse({'ok': True, 'item': data})

    def patch(self, request, item_id: int):
        if (err := self._feature_ok(request)):
            return err
        body = self._json_body(request)
        if body is None:
            return self._err('JSON نامعتبر')
        try:
            item = update_space_item(
                request.user,
                item_id,
                visibility=body.get('visibility'),
                contact_share_level=body.get('contact_share_level'),
                member_ids=body.get('member_ids'),
                note=body.get('note'),
            )
        except AgencySpacePublishError as exc:
            return self._err(str(exc))
        return JsonResponse({
            'ok': True,
            'item': serialize_space_item(item, request.user, detail=True, request=request),
        })


class AgencySpacePublishPropertyAPIView(_AgencySpaceAPIBase):
    def post(self, request):
        if (err := self._feature_ok(request)):
            return err
        body = self._json_body(request)
        if body is None:
            return self._err('JSON نامعتبر')
        try:
            item = publish_property(
                request.user,
                int(body.get('property_id', 0)),
                visibility=body.get('visibility', 'agency_public'),
                member_ids=body.get('member_ids') or [],
                note=body.get('note', ''),
            )
        except (AgencySpacePublishError, ValueError) as exc:
            return self._err(str(exc))
        return JsonResponse({
            'ok': True,
            'item': serialize_space_item(item, request.user, detail=True, request=request),
        }, status=201)


class AgencySpacePublishContactAPIView(_AgencySpaceAPIBase):
    def post(self, request):
        if (err := self._feature_ok(request)):
            return err
        body = self._json_body(request)
        if body is None:
            return self._err('JSON نامعتبر')
        try:
            item = publish_customer(
                request.user,
                int(body.get('customer_id', 0)),
                visibility=body.get('visibility', 'agency_public'),
                contact_share_level=body.get('contact_share_level', 'summary'),
                member_ids=body.get('member_ids') or [],
                note=body.get('note', ''),
            )
        except (AgencySpacePublishError, ValueError) as exc:
            return self._err(str(exc))
        return JsonResponse({
            'ok': True,
            'item': serialize_space_item(item, request.user, detail=True, request=request),
        }, status=201)


class AgencySpaceUnpublishAPIView(_AgencySpaceAPIBase):
    def post(self, request, item_id: int):
        if (err := self._feature_ok(request)):
            return err
        try:
            item = unpublish_space_item(request.user, item_id)
        except AgencySpacePublishError as exc:
            return self._err(str(exc))
        return JsonResponse({'ok': True, 'item_id': item.pk})


class AgencySpaceCopyAPIView(_AgencySpaceAPIBase):
    def post(self, request, item_id: int):
        if (err := self._feature_ok(request)):
            return err
        try:
            result = copy_space_item_to_personal_crm(request.user, item_id)
        except (AgencySpaceCopyError, PermissionError) as exc:
            return self._err(str(exc), 403 if isinstance(exc, PermissionError) else 400)
        return JsonResponse({
            'ok': True,
            'data': copy_result_to_api_dict(result),
        })


class AgencySpaceModerateAPIView(_AgencySpaceAPIBase):
    def post(self, request, item_id: int):
        if (err := self._feature_ok(request)):
            return err
        body = self._json_body(request) or {}
        action = body.get('action', '')
        reason = (body.get('reason') or body.get('moderation_reason') or '').strip()
        try:
            if action == 'hide':
                item = hide_space_item_public(
                    request.user,
                    item_id,
                    moderation_reason=reason,
                )
            elif action == 'restore':
                item = restore_space_item_moderation(request.user, item_id)
            else:
                return self._err('عملیات نامعتبر')
        except AgencySpaceModerationError as exc:
            return self._err(str(exc))
        return JsonResponse({'ok': True, 'item_id': item.pk, 'status': item.status})

