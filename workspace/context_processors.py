"""Context processor برای workspace."""
from ai_workspace.constants import is_ai_enabled
from workspace.forms import DatasetUploadForm, ReminderForm, WorkspaceSettingsForm
from workspace.mixins import get_or_create_settings
from workspace.services.access import get_bot_access_state, get_bot_product_buy_url
from workspace.services.jalali_input import format_jalali_today_label
from workspace.crm_views import _crm_nav_counts


def workspace_context(request):
    ctx = {'today_jalali': format_jalali_today_label()}
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return ctx
    settings_obj = get_or_create_settings(user)
    access = get_bot_access_state(user)
    ctx.update({
        'ws_settings': settings_obj,
        'bot_buy_url': get_bot_product_buy_url(),
        'crm_nav_counts': _crm_nav_counts(user),
        'ai_enabled': is_ai_enabled(),
        **access,
    })
    if request.path.startswith('/workspace'):
        force_tour = request.GET.get('tour') in ('1', 'true', 'yes')
        show_onboarding = (
            request.resolver_match
            and request.resolver_match.url_name == 'home'
            and (force_tour or not settings_obj.onboarding_completed)
        )
        ctx.update({
            'is_workspace': True,
            'ws_settings_form': WorkspaceSettingsForm(instance=settings_obj),
            'ws_reminder_form': ReminderForm(),
            'open_modal': request.GET.get('open', ''),
            'show_onboarding': show_onboarding,
            'onboarding_force': force_tour,
        })
        if access['has_bot_license']:
            ctx['ws_upload_form'] = DatasetUploadForm()
    return ctx
