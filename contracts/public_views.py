"""ویوهای عمومی قرارداد — بدون لاگین."""
from __future__ import annotations

import base64
import io

from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from contracts.constants import LEGAL_DISCLAIMER_FULL, PARTY_ACK_ITEMS, VERIFICATION_MISMATCH_MSG
from contracts.models import Contract
from contracts.services.acceptance import accept_contract
from contracts.services.audit import log_audit_event
from contracts.services.notifications import notify_contract_event
from contracts.services.otp_service import ContractOtpError, request_contract_otp
from contracts.services.state_machine import transition_contract
from contracts.services.tokens import lookup_access_token, lookup_contract_by_verify_token, lookup_invitation
from contracts.services.version_copy import version_display_snapshot

ROLE_LABELS_FA = {
    'landlord': 'موجر',
    'tenant': 'مستأجر',
    'seller': 'فروشنده',
    'buyer': 'خریدار',
    'owner': 'مالک',
    'builder': 'سازنده',
    'witness': 'شاهد',
    'other': 'سایر',
}


class PublicAcceptView(View):
    template_name = 'contracts/public/accept.html'

    def _get_invitation(self, token: str):
        inv = lookup_invitation(token)
        if not inv:
            raise Http404
        if inv.expires_at and inv.expires_at < timezone.now():
            raise Http404
        return inv

    def get(self, request, token):
        inv = self._get_invitation(token)
        contract = inv.contract
        if not inv.opened_at:
            inv.opened_at = timezone.now()
            inv.save(update_fields=['opened_at'])
            log_audit_event(contract, 'INVITATION_OPENED', version=inv.version, request=request)

        role_label = ''
        if inv.party:
            role_label = ROLE_LABELS_FA.get(inv.party.role, inv.party.role)
        elif inv.witness:
            role_label = f'شاهد {inv.witness.witness_number}'

        sender = contract.user.get_full_name() or contract.user.username
        session_key = f'contract_verified_{inv.token_hash}'
        verified = request.session.get(session_key, False)

        ctx = {
            'contract': contract,
            'role_label': role_label,
            'sender_name': sender,
            'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
            'party_ack_items': PARTY_ACK_ITEMS,
            'verified': verified,
            'masked': not verified,
        }
        if verified:
            inv.viewed_at = inv.viewed_at or timezone.now()
            inv.save(update_fields=['viewed_at'])
            version = inv.version
            snap = version_display_snapshot(version)
            ctx.update({
                'version': version,
                'clauses': snap.get('clauses', []),
                'parties': snap.get('parties', []),
            })
            if contract.status == 'sent':
                try:
                    transition_contract(contract, 'viewed')
                except Exception:
                    pass
            log_audit_event(contract, 'CONTRACT_VIEWED', version=version, request=request)
            notify_contract_event(contract, 'viewed')
        return render(request, self.template_name, ctx)

    def post(self, request, token):
        inv = self._get_invitation(token)
        action = request.POST.get('action')
        session_key = f'contract_verified_{inv.token_hash}'
        pending_key = f'contract_pending_{inv.token_hash}'

        if action == 'verify_identity':
            phone = request.POST.get('mobile', '').strip()
            national_id = request.POST.get('national_id', '').strip()
            try:
                from contracts.services.acceptance import _verify_identity
                _verify_identity(inv, phone, national_id)
            except ValueError:
                return render(request, self.template_name, {
                    'contract': inv.contract,
                    'error': VERIFICATION_MISMATCH_MSG,
                    'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
                    'masked': True,
                })
            request.session[pending_key] = {'phone': phone, 'national_id': national_id}
            try:
                request_contract_otp(inv, phone, request=request)
            except ContractOtpError as exc:
                return render(request, self.template_name, {
                    'contract': inv.contract,
                    'error': exc.message,
                    'show_otp': True,
                    'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
                })
            return render(request, self.template_name, {
                'contract': inv.contract,
                'show_otp': True,
                'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
            })

        if action == 'verify_otp':
            pending = request.session.get(pending_key, {})
            phone = pending.get('phone', '')
            otp_code = request.POST.get('otp_code', '').strip()
            try:
                from contracts.services.otp_service import verify_contract_otp
                verify_contract_otp(inv, phone, otp_code, request=request)
            except ContractOtpError as exc:
                return render(request, self.template_name, {
                    'contract': inv.contract,
                    'error': exc.message,
                    'show_otp': True,
                    'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
                })
            request.session[session_key] = True
            log_audit_event(inv.contract, 'OTP_VERIFIED', version=inv.version, request=request)
            return self.get(request, token)

        if action == 'accept':
            if not request.session.get(session_key):
                raise Http404
            pending = request.session.get(pending_key, {})
            acks = request.POST.getlist('ack')
            sig_data = request.POST.get('signature_data', '')
            sig_file = None
            if sig_data and sig_data.startswith('data:image'):
                try:
                    header, b64 = sig_data.split(',', 1)
                    sig_file = io.BytesIO(base64.b64decode(b64))
                    sig_file.name = 'signature.png'
                except Exception:
                    sig_file = None
            try:
                accept_contract(
                    inv,
                    phone=pending.get('phone', ''),
                    national_id=pending.get('national_id', ''),
                    ack_checkboxes=acks,
                    signature_image=sig_file,
                    request=request,
                    otp_already_verified=True,
                )
            except (ValueError, ContractOtpError) as exc:
                return render(request, self.template_name, {
                    'contract': inv.contract,
                    'error': getattr(exc, 'message', str(exc)),
                    'verified': True,
                    'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
                })
            return render(request, 'contracts/public/accept_done.html', {
                'contract': inv.contract,
                'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
            })

        return self.get(request, token)


class PublicVerifyView(View):
    template_name = 'contracts/public/verify.html'

    def get(self, request, token):
        contract = lookup_contract_by_verify_token(token)
        if not contract:
            raise Http404
        version = contract.current_version
        ctx = {
            'contract': contract,
            'version': version,
            'status_label': contract.get_status_display(),
            'content_hash': (version.content_hash[:16] + '…') if version and version.content_hash else '',
            'finalized_at': contract.finalized_at,
        }
        return render(request, self.template_name, ctx)


class PublicFinalViewView(View):
    template_name = 'contracts/public/final_view.html'

    def _get_token(self, token: str):
        tok = lookup_access_token(token)
        if not tok:
            raise Http404
        return tok

    def get(self, request, token):
        tok = self._get_token(token)
        contract = tok.contract
        session_key = f'final_verified_{tok.token_hash}'
        verified = request.session.get(session_key, False)
        ctx = {
            'contract': contract,
            'verified': verified,
            'masked': not verified,
        }
        if verified and contract.current_version:
            snap = version_display_snapshot(contract.current_version)
            ctx['clauses'] = snap.get('clauses', [])
        return render(request, self.template_name, ctx)

    def post(self, request, token):
        tok = self._get_token(token)
        action = request.POST.get('action')
        session_key = f'final_verified_{tok.token_hash}'
        if action == 'request_otp':
            mobile = tok.party.mobile if tok.party_id else tok.witness.mobile
            inv = tok.contract.invitations.filter(mobile=mobile).order_by('-created_at').first()
            if inv:
                try:
                    request_contract_otp(inv, mobile, purpose='final_view', request=request,
                                         access_token=tok)
                except ContractOtpError as exc:
                    return render(request, self.template_name, {
                        'contract': tok.contract,
                        'error': exc.message,
                        'show_otp': True,
                    })
            return render(request, self.template_name, {
                'contract': tok.contract, 'show_otp': True,
            })
        if action == 'verify_otp':
            mobile = tok.party.mobile if tok.party_id else tok.witness.mobile
            inv = tok.contract.invitations.filter(mobile=mobile).order_by('-created_at').first()
            if inv:
                from contracts.services.otp_service import verify_contract_otp
                try:
                    verify_contract_otp(inv, mobile, request.POST.get('otp_code', ''), request=request)
                except ContractOtpError as exc:
                    return render(request, self.template_name, {
                        'contract': tok.contract,
                        'error': exc.message,
                        'show_otp': True,
                    })
            request.session[session_key] = True
            return self.get(request, token)
        return self.get(request, token)
