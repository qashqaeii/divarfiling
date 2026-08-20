"""Context processor برای workspace."""
from ai_workspace.constants import CRM_MESSAGE_TONE_CHOICES, is_ai_enabled
from workspace.forms import DatasetUploadForm, ReminderForm, WorkspaceSettingsForm
from workspace.mixins import get_or_create_settings
from workspace.services.access import (
    get_bot_access_state,
    get_bot_license_display,
    get_bot_product_buy_url,
)
from workspace.services.jalali_input import format_jalali_today_label
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


def _ws_nav_flags(request, has_agency_membership):
    match = getattr(request, 'resolver_match', None)
    url_name = getattr(match, 'url_name', '') or ''
    path = request.path or ''
    more_open = (
        url_name in _WS_NAV_MORE_URL_NAMES
        or path.startswith('/workspace/academy')
        or path.startswith('/workspace/product')
        or path.startswith('/workspace/support')
        or path.startswith('/workspace/ai')
        or (url_name == 'crm_team' and not has_agency_membership)
    )
    return {
        'ws_show_agency_nav': has_agency_membership,
        'ws_nav_more_open': more_open,
    }


def workspace_context(request):
    ctx = {'today_jalali': format_jalali_today_label()}
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return ctx
    settings_obj = get_or_create_settings(user)
    access = get_bot_access_state(user)
    try:
        from product_hub.services.notifications import unread_count as product_hub_unread_count
        product_hub_unread = product_hub_unread_count(user)
    except Exception:
        product_hub_unread = 0
    ctx.update({
        'ws_settings': settings_obj,
        'bot_license_display': get_bot_license_display(user),
        'bot_buy_url': get_bot_product_buy_url(),
        'crm_nav_counts': _crm_nav_counts(user),
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
        has_agency_membership = False
        try:
            from workspace.services.crm_scope import get_membership
            has_agency_membership = get_membership(user) is not None
        except Exception:
            has_agency_membership = False
        ctx.update(_ws_nav_flags(request, has_agency_membership))
    return ctx
