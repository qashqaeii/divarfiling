"""ویوهای احراز هویت‌شده قرارداد."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import DetailView, TemplateView

from contracts.constants import (
    CONTRACT_TYPES,
    CREATOR_ACK_CHECKBOX,
    LEGAL_DISCLAIMER_FULL,
    WIZARD_DISPLAY_STEPS,
    WIZARD_STEP_LABELS,
    WIZARD_STEPS,
)
from contracts.models import Contract
from contracts.services.clause_ux import build_clause_context, build_clause_sections, clause_warnings
from contracts.services.clauses import get_applicable_clauses, get_legal_warnings
from contracts.services.contract_renderer import render_contract_document
from contracts.services.lifecycle import (
    ContractError,
    cancel_contract,
    copy_contract,
    create_contract,
    create_new_version,
    prepare_for_send,
    save_wizard_step,
    validate_contract_ready,
)
from contracts.services.invitations import resend_invitation, send_invitations
from contracts.services.scope import contract_for_deal, contract_for_user, contracts_qs
from contracts.services.wizard_parse import parse_wizard_step
from workspace.crm_views import CRMContextMixin
from workspace.services.crm_scope import deal_for_user


class DealContractsMixin(LoginRequiredMixin, CRMContextMixin):
    deal_id_kwarg = 'deal_id'

    def get_deal(self):
        deal = deal_for_user(self.request.user, self.kwargs[self.deal_id_kwarg])
        if not deal:
            raise Http404
        return deal


class DealContractsSectionView(DealContractsMixin, TemplateView):
    template_name = 'contracts/deal_section.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        deal = self.get_deal()
        qs = contract_for_deal(self.request.user, deal.pk)
        from workspace.services.crm_deals import infer_recommended_contract_type

        ctx.update({
            'deal': deal,
            'contracts': qs,
            'contract_metrics': {
                'active': qs.exclude(status__in=('finalized', 'cancelled', 'superseded')).count(),
                'pending': qs.filter(status__in=('sent', 'viewed', 'partially_accepted')).count(),
                'completed': qs.filter(status='finalized').count(),
            },
            'crm_section': 'deals',
            'contract_types': CONTRACT_TYPES,
            'recommended_contract_type': infer_recommended_contract_type(deal),
        })
        return ctx


class ContractCreateView(DealContractsMixin, View):
    def post(self, request, deal_id):
        deal = self.get_deal()
        contract_type = request.POST.get('contract_type', 'lease')
        try:
            contract = create_contract(request.user, deal.pk, contract_type, request=request)
        except ContractError as exc:
            messages.error(request, str(exc))
            return redirect('workspace:crm_deal_detail', deal_id=deal.pk)
        return redirect('workspace:contract_wizard', deal_id=deal.pk, contract_id=contract.pk)


class ContractWizardView(DealContractsMixin, TemplateView):
    template_name = 'contracts/wizard.html'

    def get_contract(self):
        c = contract_for_user(self.request.user, self.kwargs['contract_id'])
        if not c or c.deal_id != self.kwargs['deal_id']:
            raise Http404
        return c

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        contract = self.get_contract()
        deal = self.get_deal()
        wizard = contract.wizard_data or {}
        step = self.request.GET.get('step') or contract.wizard_step or 'type'
        if step not in WIZARD_STEPS:
            step = 'type'
        context_data = build_clause_context(wizard)
        display_steps = WIZARD_DISPLAY_STEPS.get(contract.contract_type, WIZARD_DISPLAY_STEPS['lease'])
        step_keys = [s[0] for s in display_steps]
        step_index = step_keys.index(step) if step in step_keys else 0
        next_label = display_steps[step_index + 1][1] if step_index + 1 < len(display_steps) else ''
        validation_errors = (
            validate_contract_ready(contract, contract.current_version)
            if contract.current_version else []
        )
        selected_codes = {
            c.get('code') for c in (wizard.get('selected_clauses') or []) if c.get('code')
        }
        from contracts.constants import WIZARD_UNIT_DIRECTIONS
        from workspace.services.property_features import (
            CHOICES_COOLING,
            CHOICES_DIRECTION,
            CHOICES_FACADE,
            CHOICES_FLOORING,
            CHOICES_HEATING,
            CHOICES_KITCHEN,
        )

        ctx.update({
            'deal': deal,
            'contract': contract,
            'wizard_step': step,
            'wizard_steps': WIZARD_STEPS,
            'display_steps': display_steps,
            'wizard_step_labels': WIZARD_STEP_LABELS,
            'wizard_data': wizard,
            'step_number': step_index + 1,
            'step_total': len(display_steps),
            'next_step_label': next_label,
            'prefill_parties': any(p.get('customer_id') for p in (wizard.get('parties') or [])),
            'prefill_property': bool(wizard.get('property')),
            'prefill_financial': bool(wizard.get('financial')),
            'selected_clause_codes': selected_codes,
            'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
            'creator_ack': CREATOR_ACK_CHECKBOX,
            'legal_warnings': get_legal_warnings(contract.contract_type, context_data),
            'available_clauses': get_applicable_clauses(
                contract.contract_type, context_data, user=self.request.user,
            ),
            'clause_sections': build_clause_sections(
                contract.contract_type, wizard,
                user=self.request.user,
                is_staff=getattr(self.request.user, 'is_staff', False),
            ),
            'clause_step_warnings': clause_warnings(wizard, contract.contract_type),
            'validation_errors': validation_errors,
            'validation_count': len(validation_errors),
            'contract_sections': render_contract_document(contract),
            'wizard_property_choices': {
                'unit_direction': WIZARD_UNIT_DIRECTIONS,
                'building_direction': CHOICES_DIRECTION,
                'facade_type': CHOICES_FACADE,
                'floor_type': CHOICES_FLOORING,
                'kitchen_type': CHOICES_KITCHEN,
                'heating_type': CHOICES_HEATING,
                'cooling_type': CHOICES_COOLING,
            },
            'crm_section': 'deals',
        })
        return ctx

    @method_decorator(csrf_protect)
    def post(self, request, deal_id, contract_id):
        contract = self.get_contract()
        step = request.POST.get('step', contract.wizard_step)
        data = {}
        if request.content_type and 'application/json' in request.content_type:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            step = data.get('step', step)
            payload = data.get('data', {})
            action = data.get('action', '')
        else:
            action = request.POST.get('action', '')
            payload = parse_wizard_step(request.POST, step, contract.contract_type)
        try:
            if action == 'autosave' or step:
                save_wizard_step(contract, step, payload, user=request.user, request=request)
            if action == 'prepare_send':
                prepare_for_send(contract, user=request.user, request=request)
                send_invitations(contract, user=request.user, request=request)
                messages.success(request, 'قرارداد برای طرفین ارسال شد.')
                return redirect('workspace:contract_manage', deal_id=deal_id, contract_id=contract.pk)
        except ContractError as exc:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
            messages.error(request, str(exc))
            return redirect('workspace:contract_wizard', deal_id=deal_id, contract_id=contract.pk)

        next_step = request.POST.get('next_step') or request.GET.get('next')
        url = reverse('workspace:contract_wizard', kwargs={'deal_id': deal_id, 'contract_id': contract.pk})
        if next_step:
            url += f'?step={next_step}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'redirect': url})
        return redirect(url)


class ContractManageView(DealContractsMixin, DetailView):
    model = Contract
    template_name = 'contracts/manage.html'
    context_object_name = 'contract'
    pk_url_kwarg = 'contract_id'

    def get_queryset(self):
        return contract_for_deal(self.request.user, self.kwargs['deal_id'])

    def _party_progress(self, contract, version):
        progress = []
        role_labels = {
            'landlord': 'موجر', 'tenant': 'مستأجر', 'seller': 'فروشنده',
            'buyer': 'خریدار', 'owner': 'مالک', 'builder': 'سازنده',
        }
        accepted_party_ids = set()
        accepted_witness_ids = set()
        if version:
            accepted_party_ids = set(
                version.acceptances.filter(party_id__isnull=False).values_list('party_id', flat=True)
            )
            accepted_witness_ids = set(
                version.acceptances.filter(witness_id__isnull=False).values_list('witness_id', flat=True)
            )
            parties = version.parties.order_by('sort_order', 'pk')
            witnesses = version.witnesses.order_by('witness_number')
        else:
            wizard = contract.wizard_data or {}
            parties = wizard.get('parties') or []
            witnesses = wizard.get('witnesses') or []

        if version and hasattr(parties, 'order_by'):
            for party in parties:
                progress.append({
                    'label': role_labels.get(party.role, party.role),
                    'name': party.display_name,
                    'accepted': party.pk in accepted_party_ids,
                    'invitation': contract.invitations.filter(
                        version=version, party=party, is_revoked=False,
                    ).order_by('-created_at').first(),
                })
            for witness in witnesses:
                progress.append({
                    'label': witness.witness_role or f'شاهد {witness.witness_number}',
                    'name': f'{witness.first_name} {witness.last_name}'.strip(),
                    'accepted': witness.pk in accepted_witness_ids,
                    'invitation': contract.invitations.filter(
                        version=version, witness=witness, is_revoked=False,
                    ).order_by('-created_at').first(),
                })
        else:
            for party in parties:
                name = f"{party.get('first_name', '')} {party.get('last_name', '')}".strip()
                progress.append({
                    'label': role_labels.get(party.get('role', ''), party.get('role', '')),
                    'name': name or '—',
                    'accepted': False,
                    'invitation': None,
                })
            for witness in witnesses:
                progress.append({
                    'label': witness.get('witness_role') or 'شاهد',
                    'name': f"{witness.get('first_name', '')} {witness.get('last_name', '')}".strip(),
                    'accepted': False,
                    'invitation': None,
                })
        return progress

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        contract = self.object
        version = contract.current_version
        party_progress = self._party_progress(contract, version)
        pending_count = sum(1 for p in party_progress if not p['accepted'])
        ctx.update({
            'deal': self.get_deal(),
            'version': version,
            'party_progress': party_progress,
            'pending_count': pending_count,
            'audit_events': contract.audit_events.select_related('party', 'actor_user').order_by('-created_at')[:50],
            'invitations': contract.invitations.select_related('party', 'witness').order_by('-created_at'),
            'handover': contract.handovers.order_by('-created_at').first(),
            'finalized_handover': contract.handovers.filter(status='finalized').first(),
            'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
            'crm_section': 'deals',
        })
        return ctx

    def post(self, request, deal_id, contract_id):
        contract = get_object_or_404(self.get_queryset(), pk=contract_id)
        action = request.POST.get('action')
        try:
            if action == 'resend':
                inv_id = request.POST.get('invitation_id')
                inv = contract.invitations.filter(pk=inv_id).first()
                if inv:
                    resend_invitation(inv, request=request)
                    messages.success(request, 'پیامک مجدداً ارسال شد.')
            elif action == 'cancel':
                cancel_contract(contract, request.POST.get('reason', ''), user=request.user, request=request)
                messages.success(request, 'قرارداد لغو شد.')
            elif action == 'copy':
                new_c = copy_contract(contract, user=request.user, request=request)
                return redirect('workspace:contract_wizard', deal_id=deal_id, contract_id=new_c.pk)
            elif action == 'new_version':
                create_new_version(contract, user=request.user, request=request)
                messages.success(request, 'نسخه جدید ایجاد شد.')
                return redirect('workspace:contract_wizard', deal_id=deal_id, contract_id=contract.pk)
            elif action == 'send':
                prepare_for_send(contract, user=request.user, request=request)
                send_invitations(contract, user=request.user, request=request)
                messages.success(request, 'قرارداد ارسال شد.')
        except (ContractError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect('workspace:contract_manage', deal_id=deal_id, contract_id=contract.pk)


class ContractPdfDownloadView(LoginRequiredMixin, View):
    def get(self, request, deal_id, contract_id):
        contract = contract_for_user(request.user, contract_id)
        if not contract or contract.deal_id != deal_id:
            raise Http404
        version = contract.current_version
        if not version or not version.pdf_file:
            from contracts.services.pdf import generate_contract_pdf
            generate_contract_pdf(version)
        if not version.pdf_file:
            raise Http404
        return FileResponse(version.pdf_file.open('rb'), as_attachment=True,
                            filename=version.pdf_file.name.split('/')[-1])


class ContractsDashboardView(LoginRequiredMixin, CRMContextMixin, TemplateView):
    template_name = 'contracts/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = contracts_qs(self.request.user)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(internal_number__icontains=q)
        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        ctype = self.request.GET.get('type', '')
        if ctype:
            qs = qs.filter(contract_type=ctype)
        ctx.update({
            'contracts': qs[:100],
            'contract_types': CONTRACT_TYPES,
            'crm_section': 'contracts',
        })
        return ctx
