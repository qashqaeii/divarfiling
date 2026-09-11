"""Advisor 360 و Member View — فاز ۳."""
from __future__ import annotations

import io

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from workspace.mixins_agency import AgencyHubAccessMixin, AgencyOwnerRequiredMixin
from workspace.services.agency_data_scope import (
    AgencyDataScopeError,
    get_advisor_member_header,
    get_member_activity_qs,
    get_member_contacts_qs,
    get_member_contract,
    get_member_contracts_qs,
    get_member_deals_qs,
    get_member_filing_qs,
    get_member_listings_qs,
    get_member_overview_kpis,
    get_member_properties_qs,
    resolve_visible_agency_member,
)
from workspace.services.agency_entitlement import (
    agency_hub_access_level,
    can_manage_agency,
    get_advisor_agency_seat_context,
    has_assigned_agency_seat,
)
from workspace.services.agency_exports import export_member_data, export_team_data

TAB_CHOICES = (
    'overview', 'contacts', 'properties', 'filing', 'deals', 'contracts', 'activities',
)
PAGE_SIZE = 25


class AgencyAdvisorDetailView(AgencyOwnerRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/agency/advisor_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        member_id = self.kwargs['member_id']
        try:
            member = resolve_visible_agency_member(self.request.user, member_id)
        except AgencyDataScopeError as exc:
            raise PermissionDenied(str(exc))

        tab = self.request.GET.get('tab', 'overview')
        if tab not in TAB_CHOICES:
            tab = 'overview'
        period = int(self.request.GET.get('period', '30') or 30)
        if period not in (7, 30, 90):
            period = 30

        header = get_advisor_member_header(self.request.user, member)
        ctx.update(header)
        ctx['tabs'] = (
            ('overview', 'نمای کلی'),
            ('contacts', 'مخاطبین'),
            ('properties', 'فایل‌های شخصی'),
            ('filing', 'فایلینگ'),
            ('deals', 'معاملات'),
            ('contracts', 'قراردادها'),
            ('activities', 'فعالیت‌ها'),
        )
        ctx['periods'] = (7, 30, 90)
        ctx['tab'] = tab
        ctx['period'] = period
        ctx['team_url'] = reverse('workspace:agency_hub_advisors')
        ctx['export_url'] = reverse('workspace:agency_advisor_export', kwargs={'member_id': member_id})

        if tab == 'overview':
            ctx['kpis'] = get_member_overview_kpis(self.request.user, member, days=period)
        elif tab == 'contacts':
            qs = get_member_contacts_qs(
                self.request.user, member,
                search=self.request.GET.get('q', ''),
                status=self.request.GET.get('status', ''),
            )
            ctx['page_obj'] = Paginator(qs, PAGE_SIZE).get_page(self.request.GET.get('page'))
        elif tab == 'properties':
            qs = get_member_properties_qs(
                self.request.user, member,
                search=self.request.GET.get('q', ''),
            )
            ctx['page_obj'] = Paginator(qs, PAGE_SIZE).get_page(self.request.GET.get('page'))
        elif tab == 'filing':
            dataset_id = self.request.GET.get('dataset')
            if dataset_id:
                qs = get_member_listings_qs(self.request.user, member, dataset_id=dataset_id)
                ctx['listings_page'] = Paginator(qs, PAGE_SIZE).get_page(self.request.GET.get('page'))
                ctx['dataset_id'] = dataset_id
            else:
                ctx['datasets_page'] = Paginator(
                    get_member_filing_qs(self.request.user, member), PAGE_SIZE,
                ).get_page(self.request.GET.get('page'))
        elif tab == 'deals':
            qs = get_member_deals_qs(
                self.request.user, member,
                search=self.request.GET.get('q', ''),
                stage=self.request.GET.get('stage', ''),
            )
            ctx['page_obj'] = Paginator(qs, PAGE_SIZE).get_page(self.request.GET.get('page'))
        elif tab == 'contracts':
            qs = get_member_contracts_qs(self.request.user, member)
            ctx['page_obj'] = Paginator(qs, PAGE_SIZE).get_page(self.request.GET.get('page'))
        elif tab == 'activities':
            ctx['activities'] = get_member_activity_qs(self.request.user, member, limit=80)

        return ctx


class AgencyAdvisorExportView(AgencyOwnerRequiredMixin, LoginRequiredMixin, View):
    def get(self, request, member_id: int):
        data_type = request.GET.get('type', 'contacts')
        fmt = request.GET.get('format', 'xlsx')
        try:
            return export_member_data(
                request.user, member_id, data_type, fmt,
                filters={
                    'search': request.GET.get('q', ''),
                    'dataset_id': request.GET.get('dataset_id', ''),
                },
            )
        except (AgencyDataScopeError, PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
            return redirect(
                reverse('workspace:agency_advisor_detail', kwargs={'member_id': member_id})
            )


class AgencyTeamExportView(AgencyOwnerRequiredMixin, LoginRequiredMixin, View):
    def post(self, request):
        data_type = request.POST.get('type', 'contacts')
        fmt = request.POST.get('format', 'xlsx')
        member_ids = None
        if not request.POST.get('all_members'):
            member_ids = [int(x) for x in request.POST.getlist('member_ids') if x.isdigit()]
        try:
            return export_team_data(
                request.user, data_type, fmt,
                member_ids=member_ids,
                filters={
                    'search': request.POST.get('q', ''),
                    'date_from': request.POST.get('date_from', ''),
                    'date_to': request.POST.get('date_to', ''),
                },
            )
        except (AgencyDataScopeError, PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
            return redirect('workspace:agency_hub_advisors')


class AgencyAdvisorContractPdfView(AgencyOwnerRequiredMixin, LoginRequiredMixin, View):
    """PDF قرارداد مشاور — مسیر read-only مدیریتی بدون License شخصی."""

    def get(self, request, member_id: int, contract_id: int):
        member = resolve_visible_agency_member(request.user, member_id)
        contract = get_member_contract(request.user, member, contract_id)
        if not contract or not contract.current_version_id:
            raise Http404
        from contracts.services.pdf import render_contract_pdf_bytes
        version = contract.current_version
        preview = contract.status != 'finalized'
        try:
            pdf_bytes = render_contract_pdf_bytes(
                version, request=request, preview=preview, refresh_stored=not preview,
            )
        except ValueError:
            raise Http404
        if not pdf_bytes:
            raise Http404
        filename = f'{contract.internal_number}_v{version.version_number}.pdf'
        inline = request.GET.get('inline') == '1'
        response = FileResponse(
            io.BytesIO(pdf_bytes),
            as_attachment=not inline,
            filename=filename,
            content_type='application/pdf',
        )
        if inline:
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class AgencyAdvisorMemberView(AgencyHubAccessMixin, LoginRequiredMixin, TemplateView):
    """تجربه مشاور — جدا از Owner Dashboard."""

    template_name = 'workspace/crm/agency/advisor_member.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and can_manage_agency(request.user):
            return redirect('workspace:agency_hub_advisors')
        if not has_assigned_agency_seat(request.user):
            messages.error(request, 'دسترسی بخش آژانس برای شما فعال نیست.')
            return redirect(reverse('workspace:crm_dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        seat_ctx = get_advisor_agency_seat_context(self.request.user)
        if not seat_ctx:
            raise PermissionDenied
        ctx.update(seat_ctx)
        ctx['access_level'] = agency_hub_access_level(self.request.user)
        return ctx


class AgencyAdvisorDocumentDownloadView(AgencyOwnerRequiredMixin, LoginRequiredMixin, View):
    """دانلود مدرک CRM مشاور — با agency gate."""

    def get(self, request, member_id: int, document_id: int):
        from workspace.models import CustomerDocument
        member = resolve_visible_agency_member(request.user, member_id)
        doc = CustomerDocument.objects.filter(
            pk=document_id, user_id=member.user_id,
        ).select_related('customer', 'property').first()
        if not doc:
            raise Http404
        if doc.customer_id:
            if doc.customer.agency_id != member.agency_id:
                raise Http404
        if doc.property_id:
            if doc.property.agency_id != member.agency_id:
                raise Http404
        if not doc.file:
            raise Http404
        return FileResponse(doc.file.open('rb'), as_attachment=True, filename=doc.file.name.split('/')[-1])


class AgencyAdvisorDetailAPIView(AgencyOwnerRequiredMixin, LoginRequiredMixin, View):
    """API سبک برای pagination آینده — JSON 403."""

    def get(self, request, member_id: int):
        tab = request.GET.get('tab', 'contacts')
        try:
            member = resolve_visible_agency_member(request.user, member_id)
        except AgencyDataScopeError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        page = int(request.GET.get('page', 1) or 1)
        if tab == 'contacts':
            qs = get_member_contacts_qs(request.user, member, search=request.GET.get('q', ''))
            p = Paginator(qs, PAGE_SIZE).get_page(page)
            items = [{'id': c.pk, 'name': c.name, 'phone': c.phone, 'status': c.status} for c in p]
        else:
            return JsonResponse({'ok': False, 'error': 'tab نامعتبر'}, status=400)
        return JsonResponse({'ok': True, 'items': items, 'page': p.number, 'pages': p.paginator.num_pages})
