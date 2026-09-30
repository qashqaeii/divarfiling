"""صفحات وب فضای آژانس — Phase 3 discovery & management."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from workspace.constants import CRM_PROPERTIES, CRM_TYPES, PROPERTY_DEAL_MODES
from workspace.mixins_agency_space import AgencySpaceFeatureMixin
from workspace.services.agency_hub_nav import build_hub_nav
from workspace.services.agency_hub import hub_base_context
from workspace.services.agency_space_access import (
    can_moderate_agency_space,
    can_publish_to_agency_space,
    get_user_space_agency,
)
from workspace.services.agency_space_analytics import (
    can_view_space_analytics,
    get_contributor_metrics,
    get_space_analytics_payload,
    get_space_header_kpis,
)
from workspace.services.agency_space_overview import get_space_overview_payload
from workspace.services.agency_space_params import (
    build_space_filter_chips,
    parse_space_list_filters,
)
from workspace.services.agency_space_query import (
    get_space_item_for_user,
    get_space_items_from_filters,
    get_space_management_qs,
    serialize_management_row,
)
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.services.crm_scope import agency_members


def _hub_shell(request, hub_section: str) -> dict:
    ctx = hub_base_context(request.user)
    ctx.update({
        'crm_section': 'agency',
        'hub_section': hub_section,
        'hub_nav': build_hub_nav(request.user),
    })
    return ctx


class AgencyHubSpaceView(AgencySpaceFeatureMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/agency/hub_space.html'
    hub_section = 'space'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_hub_shell(self.request, self.hub_section))
        user = self.request.user
        filters = parse_space_list_filters(self.request.GET)
        tab = filters.normalized_tab()
        agency = get_user_space_agency(user)
        can_moderate = can_moderate_agency_space(user, agency)

        items = []
        page_obj = None
        total_count = 0
        overview = None
        if filters.is_overview():
            if agency:
                overview = get_space_overview_payload(user, agency)
        else:
            qs = get_space_items_from_filters(user, filters)
            total_count = qs.count()
            paginator = Paginator(qs, filters.page_size)
            page_obj = paginator.get_page(filters.page)
            items = [
                serialize_space_item(item, user, detail=False)
                for item in page_obj.object_list
            ]
            items = [i for i in items if i]

        ctx.update({
            'space_tab': tab,
            'space_scope': filters.normalized_scope(),
            'space_filters': filters,
            'space_filter_chips': build_space_filter_chips(filters),
            'space_items': items,
            'space_page': page_obj,
            'space_result_total': total_count,
            'space_overview': overview,
            'space_publishers': agency_members(agency) if agency else [],
            'space_detail_url_name': 'workspace:agency_hub_space_item',
            'space_api_items_url': reverse('workspace:api_agency_space_items'),
            'space_api_analytics_url': reverse('workspace:api_agency_space_analytics'),
            'space_api_copy_url_template': '/workspace/api/crm/agency/space/items/0/copy/',
            'can_moderate_space': can_moderate,
            'can_publish_space': can_publish_to_agency_space(user, agency),
            'space_kpis': get_space_header_kpis(user, agency) if agency else {},
            'space_property_types': CRM_PROPERTIES,
            'space_deal_modes': PROPERTY_DEAL_MODES,
            'space_customer_types': CRM_TYPES,
            'space_management_url': reverse('workspace:agency_hub_space_manage'),
            'space_publish_property_url': reverse('workspace:crm_properties'),
            'space_publish_contact_url': reverse('workspace:crm_contacts'),
        })
        return ctx


class AgencyHubSpaceManageView(AgencySpaceFeatureMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/agency/hub_space_manage.html'
    hub_section = 'space'

    def dispatch(self, request, *args, **kwargs):
        agency = get_user_space_agency(request.user)
        if not can_moderate_agency_space(request.user, agency):
            return redirect('workspace:agency_hub_space')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_hub_shell(self.request, self.hub_section))
        user = self.request.user
        agency = get_user_space_agency(user)
        status_filter = (self.request.GET.get('status') or '').strip()
        if status_filter not in ('active', 'hidden', 'archived', ''):
            status_filter = ''

        qs = get_space_management_qs(user, agency=agency, status_filter=status_filter)
        page = int(self.request.GET.get('page', 1) or 1)
        paginator = Paginator(qs, 30)
        page_obj = paginator.get_page(page)
        rows = [
            serialize_management_row(item, user)
            for item in page_obj.object_list
        ]
        rows = [r for r in rows if r]

        analytics = get_space_analytics_payload(agency) if agency else {}
        contributors = get_contributor_metrics(agency) if agency else []

        ctx.update({
            'manage_page': page_obj,
            'manage_rows': rows,
            'manage_status': status_filter,
            'space_analytics': analytics,
            'contributor_metrics': contributors,
            'can_view_analytics': can_view_space_analytics(user, agency),
            'space_api_analytics_url': reverse('workspace:api_agency_space_analytics'),
            'space_back_url': reverse('workspace:agency_hub_space'),
        })
        return ctx


class AgencyHubSpaceItemView(AgencySpaceFeatureMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/agency/hub_space_detail.html'
    hub_section = 'space'

    def get(self, request, *args, **kwargs):
        item = get_space_item_for_user(request.user, kwargs['item_id'])
        if not item:
            return redirect('workspace:agency_hub_space')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_hub_shell(self.request, self.hub_section))
        item = get_space_item_for_user(self.request.user, self.kwargs['item_id'])
        payload = serialize_space_item(item, self.request.user, detail=True)
        agency = get_user_space_agency(self.request.user)
        ctx.update({
            'space_item': item,
            'space_payload': payload,
            'space_api_item_url': reverse(
                'workspace:api_agency_space_item',
                kwargs={'item_id': item.pk},
            ),
            'space_api_moderate_url': reverse(
                'workspace:api_agency_space_moderate',
                kwargs={'item_id': item.pk},
            ),
            'can_moderate_space': can_moderate_agency_space(self.request.user, agency),
            'space_team_members': [
                m for m in agency_members(agency)
                if m.is_active and m.user_id != self.request.user.id
            ] if agency else [],
        })
        from workspace.services.agency_space_ui_context import apply_agency_space_item_detail_context

        apply_agency_space_item_detail_context(
            ctx, self.request.user, item, payload or {},
        )
        return ctx

