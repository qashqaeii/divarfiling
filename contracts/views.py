"""ویوهای احراز هویت‌شده قرارداد."""
from __future__ import annotations

import io
import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import DetailView, TemplateView

from contracts.constants import (
    CONTRACT_STATUSES,
    CONTRACT_TYPES,
    CREATOR_ACK_CHECKBOX,
    LEGAL_DISCLAIMER_FULL,
    WIZARD_DISPLAY_STEPS,
    WIZARD_STEP_LABELS,
    WIZARD_STEPS,
)
from contracts.models import Contract
from contracts.services.audit import build_audit_timeline
from contracts.services.clause_ux import build_clause_context, build_clause_sections, clause_warnings
from contracts.services.clauses import get_applicable_clauses, get_legal_warnings
from contracts.services.contract_renderer import render_contract_document
from contracts.services.dashboard import (
    build_contracts_kpi_stats,
    contract_acceptance_progress,
    filter_contracts,
)
from contracts.services.invitations import resend_invitation, send_invitations
from contracts.services.lifecycle import (
    ContractError,
    cancel_contract,
    copy_contract,
    create_contract,
    create_new_version,
    delete_draft_contract,
    prepare_for_send,
    save_wizard_step,
    validate_contract_ready,
)
from contracts.services.review_context import build_review_context
from contracts.services.routing import (
    contract_manage_url,
    contract_pdf_preview_url,
    contract_wizard_url,
    contracts_dashboard_url,
    deal_contracts_filter_url,
)
from contracts.mixins import ContractLicenseContextMixin, ContractLicenseRequiredMixin
from contracts.services.scope import contract_for_deal, contract_for_user, contracts_qs
from contracts.services.wizard_parse import parse_wizard_step
from workspace.crm_views import CRMContextMixin
from workspace.mixins_crm_rbac import CRMContractsAccessMixin
from workspace.services.crm_scope import deal_for_user, deals_qs


class DealContractsMixin(CRMContractsAccessMixin, ContractLicenseRequiredMixin, CRMContextMixin):
    deal_id_kwarg = 'deal_id'

    def get_deal(self):
        deal = deal_for_user(self.request.user, self.kwargs[self.deal_id_kwarg])
        if not deal:
            raise Http404
        return deal


class ContractAccessMixin(CRMContractsAccessMixin, ContractLicenseRequiredMixin, CRMContextMixin):
    """دسترسی قرارداد — URL با یا بدون deal_id."""

    def _url_deal_id(self):
        return self.kwargs.get('deal_id')

    def get_contract(self, *, prefetch_review: bool = False):
        contract = contract_for_user(self.request.user, self.kwargs['contract_id'])
        if not contract:
            raise Http404
        url_deal_id = self._url_deal_id()
        if url_deal_id is not None and contract.deal_id != url_deal_id:
            raise Http404
        step = self.request.GET.get('step') or contract.wizard_step or 'type'
        if prefetch_review and step == 'review' and contract.current_version_id:
            contract = (
                Contract.objects.select_related('current_version', 'deal')
                .prefetch_related(
                    'current_version__parties',
                    'current_version__witnesses',
                    'current_version__clauses',
                    'current_version__payment_schedules__payments',
                    'current_version__property_snapshot',
                )
                .get(pk=contract.pk)
            )
        return contract

    def get_deal(self):
        contract = self.get_contract()
        return contract.deal if contract.deal_id else None


class DealContractsSectionView(DealContractsMixin, View):
    """سازگاری با URL قدیمی — redirect به workspace قراردادها."""

    def get(self, request, deal_id):
        return redirect(deal_contracts_filter_url(deal_id))


class ContractCreateView(DealContractsMixin, View):
    def post(self, request, deal_id):
        deal = self.get_deal()
        contract_type = request.POST.get('contract_type', 'lease')
        try:
            contract = create_contract(
                request.user, contract_type, deal_id=deal.pk, request=request,
            )
        except ContractError as exc:
            messages.error(request, str(exc))
            return redirect('workspace:crm_deal_detail', deal_id=deal.pk)
        return redirect(contract_wizard_url(contract))


class DealSearchApiView(ContractLicenseRequiredMixin, View):
    """جستجوی معامله برای اتصال قرارداد."""

    def get(self, request):
        q = (request.GET.get('q') or '').strip()
        qs = deals_qs(request.user).exclude(
            stage__in=['بسته‌شده', 'از دست رفته'],
        ).select_related('customer', 'property').order_by('-updated_at')
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(property__title__icontains=q)
            )
        results = []
        for d in qs[:30]:
            prop = ''
            if d.property_id:
                prop = (d.property.title or d.property.address or '')[:48]
            results.append({
                'id': d.pk,
                'title': d.title,
                'customer': d.customer.name if d.customer_id else '',
                'property': prop,
                'stage': d.stage,
            })
        return JsonResponse({'results': results})


class ContractCreateStandaloneView(
    CRMContractsAccessMixin, ContractLicenseRequiredMixin, CRMContextMixin, TemplateView,
):
    """ایجاد قرارداد مستقل از workspace قراردادها."""
    template_name = 'contracts/create.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'contract_types': CONTRACT_TYPES,
            'deals': deals_qs(self.request.user).exclude(
                stage__in=['بسته‌شده', 'از دست رفته'],
            ).select_related('customer', 'property')[:50],
            'crm_section': 'contracts',
            'preselected_deal_id': self.request.GET.get('deal'),
        })
        return ctx

    def post(self, request):
        contract_type = request.POST.get('contract_type', 'lease')
        deal_mode = request.POST.get('deal_mode', 'none')
        deal_id = None
        if deal_mode == 'existing':
            raw = request.POST.get('deal_id', '').strip()
            if raw:
                try:
                    deal_id = int(raw)
                except ValueError:
                    pass
            if deal_id and not deal_for_user(request.user, deal_id):
                messages.error(request, 'معامله انتخاب‌شده معتبر نیست.')
                return redirect('workspace:contract_create_standalone')
        try:
            contract = create_contract(
                request.user, contract_type, deal_id=deal_id, request=request,
            )
        except ContractError as exc:
            messages.error(request, str(exc))
            return redirect('workspace:contract_create_standalone')
        messages.success(request, 'قرارداد ایجاد شد — اطلاعات را تکمیل کنید.')
        return redirect(contract_wizard_url(contract))


class ContractWizardView(ContractAccessMixin, TemplateView):
    template_name = 'contracts/wizard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        contract = self.get_contract(prefetch_review=True)
        deal = self.get_deal()
        wizard = dict(contract.wizard_data or {})
        from contracts.services.prefill import ensure_default_parties
        ensured_parties = ensure_default_parties(
            wizard.get('parties') or [], contract.contract_type,
        )
        if ensured_parties != (wizard.get('parties') or []):
            wizard['parties'] = ensured_parties
            contract.wizard_data = wizard
            contract.save(update_fields=['wizard_data', 'updated_at'])
        step = self.request.GET.get('step') or contract.wizard_step or 'type'
        if step not in WIZARD_STEPS:
            step = 'type'
        context_data = build_clause_context(wizard, contract.contract_type)
        display_steps = WIZARD_DISPLAY_STEPS.get(
            contract.contract_type, WIZARD_DISPLAY_STEPS['lease'],
        )
        step_keys = [s[0] for s in display_steps]
        step_index = step_keys.index(step) if step in step_keys else 0
        next_label = display_steps[step_index + 1][1] if step_index + 1 < len(display_steps) else ''
        validation_errors = (
            validate_contract_ready(contract, contract.current_version)
            if contract.current_version else []
        )
        contract_sections = render_contract_document(contract) if contract.current_version else []
        review_context = (
            build_review_context(
                contract,
                validation_errors=validation_errors,
                version=contract.current_version,
            )
            if step == 'review' else None
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

        handover = None
        finalized_handover = None
        handover_public_pdf_url = ''
        if step == 'review':
            handover = contract.handovers.order_by('-created_at').first()
            finalized_handover = contract.handovers.filter(status='finalized').first()
            if finalized_handover:
                from contracts.services.routing import handover_public_pdf_url as _handover_pdf_url
                handover_public_pdf_url = _handover_pdf_url(contract, request=self.request)

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
            'prefill_property': bool(wizard.get('property')) or bool(
                (wizard.get('property') or {}).get('crm_property_id'),
            ),
            'wizard_enable_pickers': not bool(deal),
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
            'contract_sections': contract_sections,
            'review_context': review_context,
            'pdf_preview_url': (
                contract_pdf_preview_url(contract) if step == 'review' else ''
            ),
            'wizard_property_choices': {
                'unit_direction': WIZARD_UNIT_DIRECTIONS,
                'building_direction': CHOICES_DIRECTION,
                'facade_type': CHOICES_FACADE,
                'floor_type': CHOICES_FLOORING,
                'kitchen_type': CHOICES_KITCHEN,
                'heating_type': CHOICES_HEATING,
                'cooling_type': CHOICES_COOLING,
            },
            'crm_section': 'contracts',
            'contract_manage_url': contract_manage_url(contract),
            'contracts_dashboard_url': contracts_dashboard_url(),
            'handover': handover,
            'finalized_handover': finalized_handover,
            'handover_public_pdf_url': handover_public_pdf_url,
        })
        return ctx

    @method_decorator(csrf_protect)
    def post(self, request, contract_id, deal_id=None):
        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        contract = self.get_contract()
        step = request.POST.get('step', contract.wizard_step)
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
                return redirect(contract_manage_url(contract))
        except ContractError as exc:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
            messages.error(request, str(exc))
            return redirect(contract_wizard_url(contract))

        next_step = request.POST.get('next_step') or request.GET.get('next')
        url = contract_wizard_url(contract)
        if next_step:
            url += f'?step={next_step}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'redirect': url})
        return redirect(url)


class ContractManageView(ContractAccessMixin, DetailView):
    model = Contract
    template_name = 'contracts/manage.html'
    context_object_name = 'contract'
    pk_url_kwarg = 'contract_id'

    def get_object(self, queryset=None):
        return self.get_contract()

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

        acceptance_map = {}
        if version:
            for acc in version.acceptances.select_related('party', 'witness'):
                if acc.party_id:
                    acceptance_map[('party', acc.party_id)] = acc.otp_verified_at
                elif acc.witness_id:
                    acceptance_map[('witness', acc.witness_id)] = acc.otp_verified_at

        if version and hasattr(parties, 'order_by'):
            for party in parties:
                progress.append({
                    'label': role_labels.get(party.role, party.role),
                    'first_name': party.first_name or '',
                    'last_name': party.last_name or '',
                    'name': party.display_name,
                    'mobile': party.mobile or '',
                    'accepted': party.pk in accepted_party_ids,
                    'accepted_at': acceptance_map.get(('party', party.pk)),
                    'invitation': contract.invitations.filter(
                        version=version, party=party, is_revoked=False,
                    ).order_by('-created_at').first(),
                })
            for witness in witnesses:
                progress.append({
                    'label': witness.witness_role or f'شاهد {witness.witness_number}',
                    'first_name': witness.first_name or '',
                    'last_name': witness.last_name or '',
                    'name': f'{witness.first_name} {witness.last_name}'.strip(),
                    'mobile': witness.mobile or '',
                    'accepted': witness.pk in accepted_witness_ids,
                    'accepted_at': acceptance_map.get(('witness', witness.pk)),
                    'invitation': contract.invitations.filter(
                        version=version, witness=witness, is_revoked=False,
                    ).order_by('-created_at').first(),
                })
        else:
            for party in parties:
                first_name = party.get('first_name', '') or ''
                last_name = party.get('last_name', '') or ''
                name = f"{first_name} {last_name}".strip()
                progress.append({
                    'label': role_labels.get(party.get('role', ''), party.get('role', '')),
                    'first_name': first_name,
                    'last_name': last_name,
                    'name': name or '—',
                    'mobile': party.get('mobile', ''),
                    'accepted': False,
                    'invitation': None,
                })
            for witness in witnesses:
                first_name = witness.get('first_name', '') or ''
                last_name = witness.get('last_name', '') or ''
                progress.append({
                    'label': witness.get('witness_role') or 'شاهد',
                    'first_name': first_name,
                    'last_name': last_name,
                    'name': f"{first_name} {last_name}".strip(),
                    'mobile': witness.get('mobile', ''),
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
        audit_qs = contract.audit_events.select_related(
            'party', 'actor_user', 'version',
        ).order_by('-created_at')[:50]
        audit_timeline = build_audit_timeline(audit_qs)
        ctx.update({
            'deal': self.get_deal(),
            'version': version,
            'party_progress': party_progress,
            'pending_count': pending_count,
            'audit_timeline': audit_timeline,
            'audit_total_count': contract.audit_events.count(),
            'invitations': contract.invitations.select_related('party', 'witness').order_by('-created_at'),
            'handover': contract.handovers.order_by('-created_at').first(),
            'finalized_handover': contract.handovers.filter(status='finalized').first(),
            'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
            'crm_section': 'contracts',
            'contract_wizard_url': contract_wizard_url(contract),
            'contracts_dashboard_url': contracts_dashboard_url(),
            'acceptance_progress': contract_acceptance_progress(contract),
            'contract_statuses': CONTRACT_STATUSES,
        })
        from contracts.services.routing import contract_pdf_url, handover_public_pdf_url
        ctx['contract_pdf_url'] = contract_pdf_url(contract)
        ctx['handover_public_pdf_url'] = handover_public_pdf_url(contract, request=self.request)
        return ctx

    def post(self, request, contract_id, deal_id=None):
        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        contract = self.get_object()
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
                return redirect(contract_wizard_url(new_c))
            elif action == 'new_version':
                create_new_version(contract, user=request.user, request=request)
                messages.success(request, 'نسخه جدید ایجاد شد.')
                return redirect(contract_wizard_url(contract))
            elif action == 'send':
                prepare_for_send(contract, user=request.user, request=request)
                send_invitations(contract, user=request.user, request=request)
                messages.success(request, 'قرارداد ارسال شد.')
        except (ContractError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(contract_manage_url(contract))


class ContractDeleteDraftView(ContractAccessMixin, View):
    """حذف قرارداد پیش‌نویس از لیست یا معامله."""

    @method_decorator(csrf_protect)
    def post(self, request, contract_id, deal_id=None):
        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        contract = self.get_contract()
        saved_deal_id = contract.deal_id
        return_to = (request.POST.get('return_to') or '').strip()
        try:
            internal_number = delete_draft_contract(contract, user=request.user, request=request)
            messages.success(request, f'قرارداد {internal_number} حذف شد.')
        except ContractError as exc:
            messages.error(request, str(exc))
        if return_to.startswith('/workspace/'):
            return redirect(return_to)
        if saved_deal_id:
            return redirect(contracts_dashboard_url(deal=saved_deal_id))
        return redirect(contracts_dashboard_url())


class ContractPdfDownloadView(ContractAccessMixin, View):
    def get(self, request, contract_id, deal_id=None):
        import io

        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        contract = self.get_contract()
        version = contract.current_version
        if not version:
            raise Http404
        from contracts.services.pdf import render_contract_pdf_bytes
        preview = contract.status != 'finalized'
        try:
            pdf_bytes = render_contract_pdf_bytes(
                version,
                request=request,
                preview=preview,
                refresh_stored=not preview,
            )
        except ValueError:
            raise Http404
        if not pdf_bytes:
            raise Http404
        filename = f'{contract.internal_number}_v{version.version_number}.pdf'
        inline = request.GET.get('inline') == '1' or contract.status == 'finalized'
        response = FileResponse(
            io.BytesIO(pdf_bytes),
            as_attachment=not inline,
            filename=filename,
            content_type='application/pdf',
        )
        if inline:
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class ContractPdfPreviewView(ContractAccessMixin, View):
    """پیش‌نمایش PDF پیش از ارسال — بدون ذخیره فایل."""

    def get(self, request, contract_id, deal_id=None):
        import io

        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        contract = self.get_contract()
        version = contract.current_version
        if not version:
            raise Http404
        from contracts.services.pdf import render_contract_pdf_bytes
        try:
            pdf_bytes = render_contract_pdf_bytes(version, request=request, preview=True)
        except ValueError:
            raise Http404
        if not pdf_bytes:
            raise Http404
        filename = f'{contract.internal_number}_v{version.version_number}_preview.pdf'
        response = FileResponse(
            io.BytesIO(pdf_bytes),
            as_attachment=False,
            filename=filename,
            content_type='application/pdf',
        )
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class ContractsDashboardView(
    CRMContractsAccessMixin,
    LoginRequiredMixin,
    ContractLicenseContextMixin,
    CRMContextMixin,
    TemplateView,
):
    template_name = 'contracts/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_contract_license_context())
        if ctx['contracts_locked']:
            empty_page = Paginator([], 25).get_page(1)
            ctx.update({
                'contracts_page': empty_page,
                'contracts': [],
                'contract_types': CONTRACT_TYPES,
                'contract_statuses': CONTRACT_STATUSES,
                'stats': {
                    'total': 0,
                    'draft': 0,
                    'pending': 0,
                    'finalized': 0,
                    'needs_action': 0,
                    'mix_segments': [],
                    'hero_meta': 'قراردادی ثبت نشده',
                    'needs_action_share': 0,
                    'needs_action_meta': 'هنوز قراردادی نیست',
                    'draft_share': 0,
                    'draft_meta': 'هنوز قراردادی نیست',
                    'finalized_share': 0,
                    'finalized_meta': 'هنوز قراردادی نیست',
                    'pending_share': 0,
                },
                'kpi_links': {
                    'all': '?',
                    'needs_action': '?focus=needs',
                    'draft': '?status=draft',
                    'finalized': '?status=finalized',
                },
                'crm_section': 'contracts',
                'filter_deal': None,
                'filter_qs': '',
            })
            return ctx
        qs = filter_contracts(self.request.user, self.request.GET)
        paginator = Paginator(qs, 25)
        page = paginator.get_page(self.request.GET.get('page'))
        filter_deal = self.request.GET.get('deal')
        filter_deal_obj = None
        if filter_deal:
            try:
                filter_deal_obj = deal_for_user(self.request.user, int(filter_deal))
            except (TypeError, ValueError):
                filter_deal_obj = None

        deal_qs = f'&deal={filter_deal_obj.pk}' if filter_deal_obj else ''
        ctx.update({
            'contracts_page': page,
            'contracts': page.object_list,
            'contract_types': CONTRACT_TYPES,
            'contract_statuses': CONTRACT_STATUSES,
            'stats': build_contracts_kpi_stats(self.request.user),
            'kpi_links': {
                'all': f'?{deal_qs.lstrip("&")}' if deal_qs else '?',
                'needs_action': f'?focus=needs{deal_qs}',
                'draft': f'?status=draft{deal_qs}',
                'finalized': f'?status=finalized{deal_qs}',
            },
            'crm_section': 'contracts',
            'filter_deal': filter_deal_obj,
            'filter_qs': self.request.GET.urlencode(),
        })
        return ctx


class ContractWizardCustomerSearchView(ContractLicenseRequiredMixin, View):
    """جستجوی مخاطب برای ویزارد قرارداد (بدون بارگذاری لیست کامل)."""

    def get(self, request):
        from contracts.services.wizard_sources import parse_picker_request_params, search_wizard_customers_page

        q, offset, limit = parse_picker_request_params(
            request.GET.get('q', ''),
            request.GET.get('offset', 0),
            request.GET.get('limit', 20),
        )
        payload = search_wizard_customers_page(request.user, q, offset=offset, limit=limit)
        return JsonResponse({'ok': True, **payload})


class ContractWizardCustomerDetailView(ContractLicenseRequiredMixin, View):
    def get(self, request, customer_id):
        from contracts.services.wizard_sources import wizard_customer_party_payload

        payload = wizard_customer_party_payload(request.user, customer_id)
        if not payload:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        return JsonResponse({'ok': True, 'party': payload})


class ContractWizardPropertySearchView(ContractLicenseRequiredMixin, View):
    def get(self, request):
        from contracts.services.wizard_sources import parse_picker_request_params, search_wizard_properties_page

        q, offset, limit = parse_picker_request_params(
            request.GET.get('q', ''),
            request.GET.get('offset', 0),
            request.GET.get('limit', 20),
        )
        payload = search_wizard_properties_page(request.user, q, offset=offset, limit=limit)
        return JsonResponse({'ok': True, **payload})


class ContractWizardPropertyDetailView(ContractLicenseRequiredMixin, View):
    def get(self, request, property_id):
        from contracts.services.wizard_sources import wizard_property_payload

        payload = wizard_property_payload(request.user, property_id)
        if not payload:
            return JsonResponse({'ok': False, 'error': 'فایل شخصی یافت نشد'}, status=404)
        return JsonResponse({'ok': True, 'property': payload})
