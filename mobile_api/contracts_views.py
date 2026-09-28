"""Views — /api/mobile/v1/contracts/"""
from __future__ import annotations

import io

from django.http import FileResponse, Http404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mobile_api.pagination import clamp_page, clamp_page_size
from mobile_api.responses import api_error, api_ok
from mobile_api.views import _parse_body
from contracts.services.license_gate import LICENSE_REQUIRED_MSG


def _contract_value_error(exc: ValueError):
    if str(exc) == LICENSE_REQUIRED_MSG:
        return api_error(str(exc), code='CONTRACTS_LICENSE_REQUIRED', status=403)
    return api_error(str(exc), code='VALIDATION_ERROR')


class ContractsListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.contracts_mobile import list_contracts_paginated

        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 20), default=20, maximum=50)
        params = {
            'q': request.GET.get('q') or request.GET.get('search') or '',
            'status': request.GET.get('status') or '',
            'type': request.GET.get('type') or request.GET.get('contract_type') or '',
            'deal': request.GET.get('deal_id') or '',
            'deal_linked': request.GET.get('deal_linked') or '',
            'date_from': request.GET.get('date_from') or '',
            'date_to': request.GET.get('date_to') or '',
            'sort': request.GET.get('sort') or 'updated',
            'needs_action': request.GET.get('needs_action') or '',
        }
        try:
            items, meta, stats = list_contracts_paginated(
                request.user,
                page=page,
                page_size=page_size,
                query=params,
            )
        except ValueError as exc:
            return _contract_value_error(exc)
        return api_ok({'items': items, 'stats': stats}, meta=meta)

    def post(self, request):
        from mobile_api.services.contracts_mobile import create_contract_mobile

        data = _parse_body(request)
        contract_type = (data.get('contract_type') or '').strip()
        deal_id = data.get('deal_id')
        try:
            deal_pk = int(deal_id) if deal_id not in (None, '', 0) else None
        except (TypeError, ValueError):
            return api_error('شناسه معامله نامعتبر است.', code='VALIDATION_ERROR')
        try:
            payload = create_contract_mobile(
                request.user,
                contract_type=contract_type or 'sale',
                deal_id=deal_pk,
            )
        except ValueError as exc:
            return _contract_value_error(exc)
        return api_ok(payload, status=201)


class ContractDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contract_id):
        from mobile_api.services.contracts_mobile import contract_detail_payload

        try:
            payload = contract_detail_payload(request.user, contract_id)
        except ValueError as exc:
            return _contract_value_error(exc)
        if not payload:
            return api_error('قرارداد یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class ContractTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contract_id):
        from mobile_api.services.contracts_mobile import contract_timeline_payload

        try:
            payload = contract_timeline_payload(request.user, contract_id)
        except ValueError as exc:
            return _contract_value_error(exc)
        if payload is None:
            return api_error('قرارداد یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'items': payload})


class ContractAttachmentsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, contract_id):
        from mobile_api.services.contracts_mobile import list_attachments_payload

        try:
            items = list_attachments_payload(request.user, contract_id)
        except ValueError as exc:
            return _contract_value_error(exc)
        if items is None:
            return api_error('قرارداد یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'items': items})

    def post(self, request, contract_id):
        from mobile_api.services.contracts_mobile import upload_attachment_payload

        uploaded = request.FILES.get('file') or request.FILES.get('attachment')
        if not uploaded:
            return api_error('فایلی انتخاب نشده است.', code='VALIDATION_ERROR')
        try:
            item = upload_attachment_payload(
                request.user,
                contract_id,
                uploaded,
                title=(request.POST.get('title') or '').strip(),
                attachment_type=(request.POST.get('attachment_type') or 'other').strip(),
            )
        except ValueError as exc:
            if str(exc) == LICENSE_REQUIRED_MSG:
                return api_error(str(exc), code='CONTRACTS_LICENSE_REQUIRED', status=403)
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(item, status=201)


class ContractAttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contract_id, attachment_id):
        from contracts.services.attachments import attachment_for_user, build_attachment_response

        try:
            from mobile_api.services.contracts_mobile import assert_mobile_contract_license

            assert_mobile_contract_license(request.user)
        except ValueError as exc:
            return _contract_value_error(exc)
        att = attachment_for_user(request.user, attachment_id)
        if not att or att.contract_id != contract_id:
            return api_error('ضمیمه یافت نشد.', code='NOT_FOUND', status=404)
        inline = request.GET.get('inline') == '1'
        try:
            return build_attachment_response(att, inline=inline)
        except Http404:
            return api_error('فایل یافت نشد.', code='NOT_FOUND', status=404)


class ContractPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contract_id):
        from contracts.services.pdf import render_contract_pdf_bytes
        from mobile_api.services.contracts_mobile import get_contract_for_pdf

        try:
            contract = get_contract_for_pdf(request.user, contract_id)
        except ValueError as exc:
            return _contract_value_error(exc)
        if not contract:
            return api_error('قرارداد یافت نشد.', code='NOT_FOUND', status=404)
        version = contract.current_version
        if not version:
            return api_error('نسخه قرارداد آماده نیست.', code='NOT_FOUND', status=404)
        preview = contract.status != 'finalized'
        try:
            pdf_bytes = render_contract_pdf_bytes(
                version,
                request=request,
                preview=preview,
                refresh_stored=not preview,
            )
        except ValueError:
            return api_error('PDF در دسترس نیست.', code='NOT_FOUND', status=404)
        if not pdf_bytes:
            return api_error('PDF در دسترس نیست.', code='NOT_FOUND', status=404)
        filename = f'{contract.internal_number}_v{version.version_number}.pdf'
        response = FileResponse(
            io.BytesIO(pdf_bytes),
            content_type='application/pdf',
            filename=filename,
        )
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class ContractWizardCustomerSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from contracts.services.wizard_sources import parse_picker_request_params, search_wizard_customers_page

        q, offset, limit = parse_picker_request_params(
            request.GET.get('q', ''),
            request.GET.get('offset', 0),
            request.GET.get('limit', 20),
        )
        return api_ok(search_wizard_customers_page(request.user, q, offset=offset, limit=limit))


class ContractWizardCustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, customer_id):
        from contracts.services.wizard_sources import wizard_customer_party_payload

        payload = wizard_customer_party_payload(request.user, customer_id)
        if not payload:
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'party': payload})


class ContractWizardPropertySearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from contracts.services.wizard_sources import parse_picker_request_params, search_wizard_properties_page

        q, offset, limit = parse_picker_request_params(
            request.GET.get('q', ''),
            request.GET.get('offset', 0),
            request.GET.get('limit', 20),
        )
        return api_ok(search_wizard_properties_page(request.user, q, offset=offset, limit=limit))


class ContractWizardPropertyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        from contracts.services.wizard_sources import wizard_property_payload

        payload = wizard_property_payload(request.user, property_id)
        if not payload:
            return api_error('فایل شخصی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'property': payload})


class ContractHandoverView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contract_id):
        from mobile_api.services.contracts_mobile import contract_detail_payload

        try:
            detail = contract_detail_payload(request.user, contract_id)
        except ValueError as exc:
            return _contract_value_error(exc)
        if not detail:
            return api_error('قرارداد یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(detail.get('handover') or {})
