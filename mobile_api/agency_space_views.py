"""Agency Space Mobile API — /api/mobile/v1/agency/space/"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mobile_api.responses import api_error, api_ok
from mobile_api.services.agency_space_mobile import require_agency_space_access, space_item_payload
from mobile_api.views import _parse_body


class AgencySpaceItemsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.agency_space_params import filters_to_legacy_kwargs, parse_space_list_filters
        from workspace.services.agency_space_query import get_space_items_from_filters, paginate_space_items

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])

        filters = parse_space_list_filters(request.query_params)
        legacy = filters_to_legacy_kwargs(filters)
        rows, total, num_pages = paginate_space_items(
            get_space_items_from_filters(request.user, filters),
            filters.page,
            filters.page_size,
        )
        items = [
            space_item_payload(i, request.user, detail=False, request=request)
            for i in rows
        ]
        return api_ok({
            'items': [i for i in items if i],
            'total': total,
            'page': filters.page,
            'num_pages': num_pages,
            'filters': legacy,
        })


class AgencySpaceAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.agency_space_analytics import (
            can_view_space_analytics,
            get_space_analytics_payload,
        )

        agency, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        if not can_view_space_analytics(request.user, agency):
            return api_error('دسترسی مجاز نیست.', code='FORBIDDEN', status=403)
        return api_ok({'analytics': get_space_analytics_payload(agency)})


class AgencySpaceItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, item_id: int):
        from workspace.services.agency_space_query import get_space_item_for_user

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        item = get_space_item_for_user(request.user, item_id)
        if not item:
            return api_error('آیتم یافت نشد.', code='NOT_FOUND', status=404)
        data = space_item_payload(item, request.user, detail=True, request=request)
        if not data:
            return api_error('دسترسی مجاز نیست.', code='FORBIDDEN', status=403)
        return api_ok({'item': data})

    def patch(self, request, item_id: int):
        from workspace.services.agency_space_publish import AgencySpacePublishError, update_space_item

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        body = _parse_body(request)
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
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'item': space_item_payload(item, request.user, detail=True, request=request)})


class AgencySpacePublishPropertyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from workspace.services.agency_space_publish import AgencySpacePublishError, publish_property

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        body = _parse_body(request)
        try:
            item = publish_property(
                request.user,
                int(body.get('property_id', 0)),
                visibility=body.get('visibility', 'agency_public'),
                member_ids=body.get('member_ids') or [],
                note=body.get('note', ''),
            )
        except (AgencySpacePublishError, ValueError) as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'item': space_item_payload(item, request.user, detail=True, request=request)}, status=201)


class AgencySpacePublishContactView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from workspace.services.agency_space_publish import AgencySpacePublishError, publish_customer

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        body = _parse_body(request)
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
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'item': space_item_payload(item, request.user, detail=True, request=request)}, status=201)


class AgencySpaceUnpublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, item_id: int):
        from workspace.services.agency_space_publish import AgencySpacePublishError, unpublish_space_item

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        try:
            item = unpublish_space_item(request.user, item_id)
        except AgencySpacePublishError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'item_id': item.pk})


class AgencySpaceCopyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, item_id: int):
        from workspace.services.agency_space_copy import (
            AgencySpaceCopyError,
            copy_result_to_api_dict,
            copy_space_item_to_personal_crm,
        )

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        try:
            result = copy_space_item_to_personal_crm(request.user, item_id)
        except (AgencySpaceCopyError, PermissionError) as exc:
            status = 403 if isinstance(exc, PermissionError) else 400
            code = 'FORBIDDEN' if status == 403 else 'VALIDATION_ERROR'
            return api_error(str(exc), code=code, status=status)
        return api_ok(copy_result_to_api_dict(result))


class AgencySpaceBulkModerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from workspace.services.agency_space_moderation import (
            AgencySpaceModerationError,
            bulk_moderate_space_items,
        )

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        body = _parse_body(request) or {}
        action = (body.get('action') or '').strip()
        item_ids = body.get('item_ids') or []
        if not isinstance(item_ids, list) or not item_ids:
            return api_error('حداقل یک مورد انتخاب کنید.', code='VALIDATION_ERROR')
        if len(item_ids) > 50:
            return api_error('حداکثر ۵۰ مورد در هر درخواست.', code='VALIDATION_ERROR')
        reason = (body.get('reason') or body.get('moderation_reason') or '').strip()
        try:
            payload = bulk_moderate_space_items(
                request.user,
                item_ids,
                action,
                moderation_reason=reason,
            )
        except AgencySpaceModerationError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(payload)


class AgencySpaceModerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, item_id: int):
        from workspace.services.agency_space_moderation import (
            AgencySpaceModerationError,
            hide_space_item_public,
            restore_space_item_moderation,
        )

        _, err = require_agency_space_access(request.user)
        if err:
            return api_error(err['message'], code=err['code'], status=err['status'])
        body = _parse_body(request) or {}
        action = (body.get('action') or '').strip()
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
                return api_error('عملیات نامعتبر', code='VALIDATION_ERROR')
        except AgencySpaceModerationError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'item_id': item.pk, 'status': item.status})
