from django import template

from workspace.support_constants import (
    TICKET_PRIORITY_BADGE_CLASS,
    TICKET_STATUS_BADGE_CLASS,
)

register = template.Library()


@register.filter
def sup_status_badge_class(status):
    return TICKET_STATUS_BADGE_CLASS.get(status, 'sup-badge--default')


@register.filter
def sup_priority_badge_class(priority):
    return TICKET_PRIORITY_BADGE_CLASS.get(priority, 'sup-priority--normal')


@register.inclusion_tag('workspace/support/includes/badges.html')
def sup_ticket_badges(ticket):
    return {'ticket': ticket}
