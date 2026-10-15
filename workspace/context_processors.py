"""Context processor برای workspace."""
from divar_shop.db_safe import DB_CONTEXT_ERRORS
from workspace.carto_basemap import get_carto_basemap_api_key
from ai_workspace.constants import CRM_MESSAGE_TONE_CHOICES, is_ai_enabled
from workspace.forms import DatasetUploadForm, ReminderForm, WorkspaceSettingsForm
from workspace.mixins import get_or_create_settings
from workspace.services.access import (
    get_bot_access_state,
    get_bot_license_display,
    get_bot_product_buy_url,
)
from workspace.services.jalali_input import format_jalali_today_label
from workspace.services.listing_retention_calendar import filing_listing_retention_days
from workspace.services.support_tickets import get_user_ticket_stats
from workspace.crm_views import _crm_nav_counts

_WS_NAV_MORE_URL_NAMES = frozenset({
    'crm_dashboard',
    'crm_reminders',
    'crm_templates',
    'crm_automation',
    'tools',
    'compare',
    'docs_api',
    'upgrade',
    'help',
    'support_list',
    'support_create',
    'support_detail',
})


def _ws_nav_flags(request, user, show_agency_nav: bool):
    match = getattr(request, 'resolver_match', None)
    url_name = getattr(match, 'url_name', '') or ''
    path = request.path or ''
    more_open = (
        url_name in _WS_NAV_MORE_URL_NAMES
        or path.startswith('/workspace/academy')
        or path.startswith('/workspace/product')
        or path.startswith('/workspace/support')
        or path.startswith('/workspace/ai')
        or path.startswith('/workspace/crm/agency')
    )
    return {
        'ws_show_agency_nav': show_agency_nav,
        'ws_nav_more_open': more_open,
    }


def workspace_context(request):
    ctx = {
        'today_jalali': format_jalali_today_label(),
        'carto_basemap_key': get_carto_basemap_api_key(),
        'filing_listing_retention_days': filing_listing_retention_days(),
    }
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return ctx
    try:
        return _build_workspace_context(request, user, ctx)
    except DB_CONTEXT_ERRORS:
        return ctx


def _build_workspace_context(request, user, ctx):
    settings_obj = get_or_create_settings(user)
    access = get_bot_access_state(user)
    try:
        from product_hub.services.notifications import unread_count as product_hub_unread_count
        product_hub_unread = product_hub_unread_count(user)
    except Exception:
        product_hub_unread = 0
    from workspace.services.agency_entitlement import (
        agency_hub_access_level,
        can_manage_agency,
        get_active_subscription_for_owner,
        seat_usage_summary,
    )
    from workspace.services.agency_entitlement import can_access_agency_hub

    agency_access = agency_hub_access_level(user)
    agency_sub = get_active_subscription_for_owner(user) if agency_access in ('owner', 'owner_locked') else None
    agency_onboarding_cta = None
    if agency_sub and can_manage_agency(user):
        from workspace.services.agency_onboarding import get_owner_agency
        owner_agency = get_owner_agency(user)
        if not owner_agency or not owner_agency.onboarding_completed_at:
            from django.urls import reverse
            agency_onboarding_cta = reverse('workspace:agency_onboarding')

    ctx.update({
        'ws_settings': settings_obj,
        'bot_license_display': get_bot_license_display(user),
        'bot_buy_url': get_bot_product_buy_url(),
        'crm_nav_counts': _crm_nav_counts(user),
        'ws_agency_access_level': agency_access,
        'ws_agency_subscription': agency_sub,
        'ws_agency_seat_usage': seat_usage_summary(agency_sub) if agency_sub else None,
        'ws_can_manage_agency': can_manage_agency(user),
        'ws_agency_onboarding_cta': agency_onboarding_cta,
        'support_nav_counts': get_user_ticket_stats(user),
        'product_hub_unread': product_hub_unread,
        'ai_enabled': is_ai_enabled(),
        'crm_message_tones': CRM_MESSAGE_TONE_CHOICES,
        **access,
    })
    if request.path.startswith('/workspace'):
        force_tour = request.GET.get('tour') in ('1', 'true', 'yes')
        show_onboarding = (
            request.resolver_match
            and request.resolver_match.url_name == 'home'
            and (force_tour or not settings_obj.onboarding_completed)
        )
        from workspace.services.public_share_common import social_networks_form_list
        ctx.update({
            'is_workspace': True,
            'ws_settings_form': WorkspaceSettingsForm(instance=settings_obj),
            'ws_reminder_form': ReminderForm(),
            'open_modal': request.GET.get('open', ''),
            'show_onboarding': show_onboarding,
            'onboarding_force': force_tour,
            'ws_consultant_social_networks': social_networks_form_list(settings_obj.social_links),
            'ws_agency_social_networks': social_networks_form_list(settings_obj.agency_social_links),
        })
        if access['has_bot_license']:
            ctx['ws_upload_form'] = DatasetUploadForm()
        show_agency_nav = can_access_agency_hub(user)
        ctx.update(_ws_nav_flags(request, user, show_agency_nav))
        if show_agency_nav:
            from workspace.services.workspace_agency_home import resolve_workspace_agency_nav_url

            ctx['ws_agency_nav_url'] = resolve_workspace_agency_nav_url(user)
        from workspace.services.agency_rbac import (
            PERM_CONTRACTS_VIEW_TEAM,
            PERM_FINANCE_VIEW,
            has_agency_permission,
            is_agency_rbac_v2_enabled,
            resolve_nav_profile,
        )
        from workspace.services.crm_scope import get_membership

        _m = get_membership(user)
        _agency = _m.agency if _m else None
        _rbac = is_agency_rbac_v2_enabled(_agency) if _agency else False
        ctx['ws_agency_rbac_v2'] = _rbac
        profile = resolve_nav_profile(user) if _agency else ''
        ctx['ws_agency_nav_profile'] = profile
        ctx['ws_show_crm_deals_finance'] = True
        ctx['ws_show_crm_deals_nav'] = True
        ctx['ws_show_crm_contracts_nav'] = True
        if _rbac:
            if profile == 'secretary':
                ctx['ws_show_crm_deals_finance'] = False
                ctx['ws_show_crm_deals_nav'] = False
                ctx['ws_show_crm_contracts_nav'] = False
            elif profile == 'advisor':
                ctx['ws_show_crm_deals_finance'] = True
                ctx['ws_show_crm_deals_nav'] = True
                ctx['ws_show_crm_contracts_nav'] = True
            else:
                ctx['ws_show_crm_deals_finance'] = has_agency_permission(user, PERM_FINANCE_VIEW)
                ctx['ws_show_crm_deals_nav'] = True
                ctx['ws_show_crm_contracts_nav'] = has_agency_permission(
                    user, PERM_CONTRACTS_VIEW_TEAM,
                )
    return ctx
