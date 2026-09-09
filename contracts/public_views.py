"""ویوهای عمومی قرارداد — بدون لاگین."""
from __future__ import annotations

import base64
import io

from django.http import FileResponse, Http404
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
from contracts.services.final_view_context import PARTY_ROLE_LABELS, build_final_view_context
from contracts.services.invitations import is_staff_access_token
from contracts.services.tokens import lookup_access_token, lookup_contract_by_verify_token, lookup_invitation
from contracts.services.version_copy import version_display_snapshot

ROLE_LABELS_FA = PARTY_ROLE_LABELS


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
            from contracts.models import ContractAcceptance
            already = ContractAcceptance.objects.filter(
                version=inv.version,
                party_id=inv.party_id,
            ).first() if inv.party_id else ContractAcceptance.objects.filter(
                version=inv.version,
                witness_id=inv.witness_id,
            ).first() if inv.witness_id else None
            if already:
                return render(request, 'contracts/public/accept_done.html', {
                    'contract': inv.contract,
                    'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
                })
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

    def _base_ctx(self, tok, verified: bool) -> dict:
        return build_final_view_context(
            tok.contract,
            access_token=tok,
            verified=verified,
        )

    def get(self, request, token):
        tok = self._get_token(token)
        session_key = f'final_verified_{tok.token_hash}'
        verified = request.session.get(session_key, False) or is_staff_access_token(tok)
        ctx = self._base_ctx(tok, verified)
        ctx['show_otp'] = False
        ctx['view_token'] = token
        return render(request, self.template_name, ctx)

    def post(self, request, token):
        tok = self._get_token(token)
        if is_staff_access_token(tok):
            return self.get(request, token)
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
                    ctx = self._base_ctx(tok, False)
                    ctx.update({'error': exc.message, 'show_otp': True, 'view_token': token})
                    return render(request, self.template_name, ctx)
            ctx = self._base_ctx(tok, False)
            ctx['show_otp'] = True
            ctx['view_token'] = token
            return render(request, self.template_name, ctx)
        if action == 'verify_otp':
            mobile = tok.party.mobile if tok.party_id else tok.witness.mobile
            inv = tok.contract.invitations.filter(mobile=mobile).order_by('-created_at').first()
            if inv:
                from contracts.services.otp_service import verify_contract_otp
                try:
                    verify_contract_otp(inv, mobile, request.POST.get('otp_code', ''), request=request)
                except ContractOtpError as exc:
                    ctx = self._base_ctx(tok, False)
                    ctx.update({'error': exc.message, 'show_otp': True, 'view_token': token})
                    return render(request, self.template_name, ctx)
            request.session[session_key] = True
            log_audit_event(tok.contract, 'CONTRACT_VIEWED', version=tok.contract.current_version, request=request)
            return self.get(request, token)
        return self.get(request, token)


class PublicFinalPdfView(View):
    """دانلود PDF قرارداد نهایی — فقط پس از تأیید OTP در همان نشست."""

    def get(self, request, token):
        tok = lookup_access_token(token)
        if not tok:
            raise Http404
        session_key = f'final_verified_{tok.token_hash}'
        if not request.session.get(session_key) and not is_staff_access_token(tok):
            raise Http404
        contract = tok.contract
        version = contract.current_version
        if not version or not version.pdf_file:
            raise Http404
        filename = version.pdf_file.name.split('/')[-1]
        return FileResponse(
            version.pdf_file.open('rb'),
            as_attachment=True,
            filename=filename,
            content_type='application/pdf',
        )
