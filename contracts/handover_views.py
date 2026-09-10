"""ویوهای صورت‌جلسه تحویل."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView

from contracts.services.attachments import attachment_for_user, build_attachment_response, save_contract_attachment
from contracts.services.handover import HandoverError, create_handover, publish_handover, save_handover_step
from contracts.services.handover_parse import parse_handover_step
from contracts.services.handover_wizard import VALID_STEPS, build_handover_wizard_context
from contracts.services.routing import contract_manage_url, handover_wizard_url
from contracts.services.scope import contract_for_user
from contracts.views import ContractAccessMixin, DealContractsMixin


class HandoverCreateView(ContractAccessMixin, View):
    def post(self, request, contract_id, deal_id=None):
        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        contract = self.get_contract()
        try:
            handover = create_handover(request.user, contract.pk, request=request)
        except HandoverError as exc:
            messages.error(request, str(exc))
            return redirect(contract_manage_url(contract))
        return redirect(handover_wizard_url(contract, handover))


class HandoverWizardView(ContractAccessMixin, TemplateView):
    template_name = 'contracts/handover_wizard.html'

    def get_handover(self):
        contract = self.get_contract()
        handover = contract.handovers.filter(pk=self.kwargs['handover_id']).first()
        if not handover:
            raise Http404
        return handover, contract

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        handover, contract = self.get_handover()
        step = self.request.GET.get('step', 'basic')
        ctx.update({
            'deal': self.get_deal(),
            'contract': contract,
            'handover': handover,
            'crm_section': 'contracts' if not contract.deal_id else 'deals',
        })
        ctx.update(build_handover_wizard_context(handover, step=step))
        return ctx

    @method_decorator(csrf_protect)
    def post(self, request, contract_id, deal_id=None, handover_id=None):
        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        if handover_id is not None:
            self.kwargs['handover_id'] = handover_id
        handover, contract = self.get_handover()
        step = request.POST.get('step', 'basic')
        if step not in VALID_STEPS:
            step = 'basic'
        try:
            data = parse_handover_step(request.POST, step, handover)
            save_handover_step(handover, step, data, user=request.user)
            photos = list(request.FILES.getlist('photos'))
            if request.FILES.get('photo'):
                photos.append(request.FILES['photo'])
            caption = request.POST.get('photo_caption', '')
            for uploaded in photos:
                if not uploaded:
                    continue
                save_contract_attachment(
                    contract=contract,
                    version=handover.version,
                    uploaded=uploaded,
                    attachment_type='property_photo',
                    title=caption,
                    user=request.user,
                    handover=handover,
                )
            if request.POST.get('action') == 'publish':
                publish_handover(handover, user=request.user, request=request)
                messages.success(request, 'صورت‌جلسه برای طرفین ارسال شد.')
                return redirect(contract_manage_url(contract))
        except (HandoverError, ValidationError) as exc:
            messages.error(request, str(exc))
            next_step = 'review' if request.POST.get('action') == 'publish' else step
        else:
            next_step = request.POST.get('next_step', step)
        if next_step not in VALID_STEPS:
            next_step = step
        return redirect(handover_wizard_url(contract, handover, step=next_step))


class ContractAttachmentUploadView(DealContractsMixin, View):
    def post(self, request, deal_id, contract_id):
        contract = contract_for_user(request.user, contract_id)
        if not contract or contract.deal_id != deal_id:
            raise Http404
        version = contract.current_version
        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.error(request, 'فایلی انتخاب نشده است.')
            return redirect(request.META.get('HTTP_REFERER', contract_manage_url(contract)))
        try:
            save_contract_attachment(
                contract=contract,
                version=version,
                uploaded=uploaded,
                attachment_type=request.POST.get('attachment_type', 'other'),
                title=request.POST.get('title', ''),
                user=request.user,
            )
            messages.success(request, 'فایل آپلود شد.')
        except ValidationError as exc:
            messages.error(request, str(exc))
        return redirect(request.META.get('HTTP_REFERER', contract_manage_url(contract)))


class ContractAttachmentDownloadView(LoginRequiredMixin, View):
    def get(self, request, deal_id, contract_id, attachment_id):
        att = attachment_for_user(request.user, attachment_id)
        if not att or att.contract_id != contract_id or att.contract.deal_id != deal_id:
            raise Http404
        inline = request.GET.get('inline') == '1'
        return build_attachment_response(att, inline=inline)


class HandoverPdfDownloadView(ContractAccessMixin, View):
    def get(self, request, contract_id, handover_id, deal_id=None):
        self.kwargs.setdefault('contract_id', contract_id)
        if deal_id is not None:
            self.kwargs['deal_id'] = deal_id
        contract = self.get_contract()
        handover = contract.handovers.filter(pk=handover_id).first()
        if not handover or not handover.pdf_file:
            raise Http404
        return FileResponse(
            handover.pdf_file.open('rb'),
            as_attachment=True,
            filename=handover.pdf_file.name.split('/')[-1],
        )
