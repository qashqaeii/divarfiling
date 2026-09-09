"""ویو عمومی تأیید صورت‌جلسه تحویل."""
from __future__ import annotations

import io

from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views import View

from contracts.constants import HANDOVER_ACK_ITEMS, LEGAL_DISCLAIMER_SHORT
from contracts.services.handover import HandoverError, accept_handover
from contracts.services.handover_invitations import lookup_handover_invitation
from contracts.services.handover_public_context import build_handover_accept_context
from contracts.services.otp_service import ContractOtpError, request_handover_otp


def _base_ctx(inv, token: str, request, **extra):
    return build_handover_accept_context(
        inv,
        token=token,
        request=request,
        ack_items=HANDOVER_ACK_ITEMS,
        legal_disclaimer=LEGAL_DISCLAIMER_SHORT,
        **extra,
    )


class PublicHandoverAcceptView(View):
    template_name = 'contracts/public/handover_accept.html'

    def get(self, request, token):
        inv = lookup_handover_invitation(token)
        if not inv:
            return render(request, self.template_name, {
                'error': 'لینک نامعتبر یا منقضی شده است.',
                'legal_disclaimer': LEGAL_DISCLAIMER_SHORT,
            })
        return render(request, self.template_name, _base_ctx(inv, token, request))

    def post(self, request, token):
        inv = lookup_handover_invitation(token)
        if not inv:
            return render(request, self.template_name, {
                'error': 'لینک نامعتبر است.',
                'legal_disclaimer': LEGAL_DISCLAIMER_SHORT,
            })
        action = request.POST.get('action', '')
        phone = request.POST.get('phone', '')
        national_id = request.POST.get('national_id', '')

        if action == 'request_otp':
            try:
                request_handover_otp(inv, phone, request=request)
            except ContractOtpError as exc:
                return render(request, self.template_name, _base_ctx(
                    inv, token, request,
                    error=exc.message,
                    phone=phone,
                    national_id=national_id,
                ))
            return render(request, self.template_name, _base_ctx(
                inv, token, request,
                otp_sent=True,
                phone=phone,
                national_id=national_id,
            ))

        if action == 'accept':
            ack = request.POST.getlist('ack')
            try:
                accept_handover(
                    inv,
                    phone=phone,
                    national_id=national_id,
                    otp_code=request.POST.get('otp_code', ''),
                    ack_checkboxes=ack,
                    request=request,
                )
                inv.handover.refresh_from_db()
                return render(request, 'contracts/public/handover_done.html', _base_ctx(
                    inv, token, request,
                    success=True,
                ))
            except (HandoverError, ContractOtpError) as exc:
                return render(request, self.template_name, _base_ctx(
                    inv, token, request,
                    error=getattr(exc, 'message', str(exc)),
                    phone=phone,
                    national_id=national_id,
                    otp_sent=True,
                ))

        return render(request, self.template_name, _base_ctx(inv, token, request))


class PublicHandoverInvitationPdfView(View):
    """PDF صورت‌جلسه — inline در مرورگر (لینک دعوت)."""

    def get(self, request, token):
        inv = lookup_handover_invitation(token)
        if not inv:
            raise Http404
        handover = inv.handover
        from contracts.services.handover_pdf import render_handover_pdf_bytes

        preview = handover.status != 'finalized'
        pdf_bytes = render_handover_pdf_bytes(handover, preview=preview)
        if not pdf_bytes:
            raise Http404
        filename = f'handover_{handover.contract.internal_number}_{handover.pk}.pdf'
        response = FileResponse(
            io.BytesIO(pdf_bytes),
            as_attachment=False,
            filename=filename,
            content_type='application/pdf',
        )
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
