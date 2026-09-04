"""ویو عمومی تأیید صورت‌جلسه تحویل."""
from __future__ import annotations

from django.shortcuts import render
from django.views import View

from contracts.constants import HANDOVER_ACK_ITEMS, VERIFICATION_MISMATCH_MSG
from contracts.services.handover import HandoverError, accept_handover
from contracts.services.handover_invitations import lookup_handover_invitation
from contracts.services.otp_service import ContractOtpError, request_handover_otp


class PublicHandoverAcceptView(View):
    template_name = 'contracts/public/handover_accept.html'

    def get(self, request, token):
        inv = lookup_handover_invitation(token)
        if not inv:
            return render(request, self.template_name, {'error': 'لینک نامعتبر یا منقضی است.'})
        handover = inv.handover
        return render(request, self.template_name, {
            'invitation': inv,
            'handover': handover,
            'snapshot': handover.snapshot_json or {},
            'ack_items': HANDOVER_ACK_ITEMS,
            'masked': True,
        })

    def post(self, request, token):
        inv = lookup_handover_invitation(token)
        if not inv:
            return render(request, self.template_name, {'error': 'لینک نامعتبر است.'})
        action = request.POST.get('action', '')
        phone = request.POST.get('phone', '')
        national_id = request.POST.get('national_id', '')
        if action == 'request_otp':
            try:
                request_handover_otp(inv, phone, request=request)
            except ContractOtpError as exc:
                return render(request, self.template_name, {
                    'invitation': inv, 'handover': inv.handover,
                    'error': exc.message, 'phone': phone,
                })
            return render(request, self.template_name, {
                'invitation': inv, 'handover': inv.handover,
                'otp_sent': True, 'phone': phone, 'national_id': national_id,
                'ack_items': HANDOVER_ACK_ITEMS,
            })
        if action == 'accept':
            ack = request.POST.getlist('ack')
            try:
                accept_handover(
                    inv, phone=phone, national_id=national_id,
                    otp_code=request.POST.get('otp_code', ''),
                    ack_checkboxes=ack, request=request,
                )
                return render(request, 'contracts/public/handover_done.html', {'handover': inv.handover})
            except (HandoverError, ContractOtpError) as exc:
                return render(request, self.template_name, {
                    'invitation': inv, 'handover': inv.handover,
                    'error': getattr(exc, 'message', str(exc)),
                    'phone': phone, 'otp_sent': True,
                    'ack_items': HANDOVER_ACK_ITEMS,
                })
        return render(request, self.template_name, {'invitation': inv, 'handover': inv.handover})
