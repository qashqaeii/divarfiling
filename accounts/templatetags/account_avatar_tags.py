from django import template

from accounts.avatar_catalog import (
    account_avatar_url_for_request,
    consultant_portrait_url,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def account_user_avatar_url(context, user):
    request = context.get('request')
    return account_avatar_url_for_request(user, request=request)


@register.simple_tag(takes_context=True)
def consultant_portrait_url_tag(context, user, ws_settings=None):
    request = context.get('request')
    return consultant_portrait_url(user, ws_settings, request=request)
