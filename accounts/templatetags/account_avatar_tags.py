from django import template

from accounts.avatar_catalog import (
    account_avatar_url_for_request,
    consultant_portrait_url,
)
from accounts.services.account_catalog_labels import (
    license_product_line,
    order_product_line,
    plan_account_label,
    product_account_label,
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


@register.filter(name='account_product_label')
def account_product_label_filter(product):
    return product_account_label(product)


@register.filter(name='account_plan_label')
def account_plan_label_filter(plan):
    return plan_account_label(plan)


@register.filter(name='account_order_product_line')
def account_order_product_line_filter(order):
    return order_product_line(order)


@register.filter(name='account_license_line')
def account_license_line_filter(license_obj):
    return license_product_line(license_obj)
