"""Mobile API views — Epic 03 Mobile Daily Power."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mobile_api.responses import api_error, api_ok
from mobile_api.services.global_search_mobile import _clamp_limit, global_search_mobile_payload
from mobile_api.views import _parse_body


class GlobalSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.GET.get('q') or request.GET.get('query') or ''
        limit = _clamp_limit(request.GET.get('limit'))
        payload = global_search_mobile_payload(request.user, q, limit=limit)
        return api_ok(payload)


class CrmPropertyMapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.crm_map_mobile import crm_property_map_payload

        payload = crm_property_map_payload(request.user, request.GET)
        return api_ok(payload)


class PropertyTeamSharesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        from mobile_api.services.property_team_share_mobile import (
            list_property_team_shares,
            searchable_team_members,
        )

        payload = list_property_team_shares(request.user, property_id)
        if payload is None:
            return api_error('ملک یافت نشد.', code='NOT_FOUND', status=404)
        q = request.GET.get('q') or ''
        if request.GET.get('members') == '1':
            members = searchable_team_members(request.user, property_id, q=q)
            if members is None:
                return api_error('دسترسی ندارید.', code='FORBIDDEN', status=403)
            payload['members'] = members
        return api_ok(payload)

    def post(self, request, property_id):
        from mobile_api.services.property_team_share_mobile import grant_property_team_share

        data = _parse_body(request)
        try:
            member_id = int(data.get('member_id') or 0)
        except (TypeError, ValueError):
            return api_error('عضو تیم نامعتبر است.', code='VALIDATION_ERROR')
        share_mode = str(data.get('share_mode') or '').strip()
        try:
            row = grant_property_team_share(
                request.user,
                property_id,
                member_id=member_id,
                share_mode=share_mode,
            )
        except PermissionError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(row, status=201)

    def delete(self, request, property_id):
        from mobile_api.services.property_team_share_mobile import revoke_property_team_share

        try:
            share_id = int(request.GET.get('share_id') or 0)
        except (TypeError, ValueError):
            return api_error('شناسه اشتراک نامعتبر است.', code='VALIDATION_ERROR')
        try:
            revoke_property_team_share(request.user, property_id, share_id)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({})


class ListingBenchmarkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        from mobile_api.services.listing_benchmark_mobile import listing_benchmark_payload

        payload = listing_benchmark_payload(request.user, token)
        if payload is None:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class FilingListingsMapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.filing_service import multi_dataset_listings_map_payload

        payload = multi_dataset_listings_map_payload(request.user, request.GET)
        return api_ok(payload)
