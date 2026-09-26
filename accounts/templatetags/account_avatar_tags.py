from django import template

from accounts.avatar_catalog import (
    DEFAULT_AVATAR_KEY,
    avatar_static_relative_path,
    resolve_user_avatar_display,
)
from django.templatetags.static import static

register = template.Library()


@register.simple_tag(takes_context=True)
def account_user_avatar_url(context, user):
    profile = getattr(user, 'profile', None)
    display = resolve_user_avatar_display(profile, request=context.get('request'))
    if display['has_custom_avatar'] and display['url']:
        return display['url']
    key = display['avatar_key'] or DEFAULT_AVATAR_KEY
    return static(avatar_static_relative_path(key))
