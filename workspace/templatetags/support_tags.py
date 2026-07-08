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


TICKET_CATEGORY_ICONS = {
    'account': 'fa-user-shield',
    'payment': 'fa-credit-card',
    'license': 'fa-key',
    'scraper': 'fa-robot',
    'upload': 'fa-cloud-arrow-up',
    'filing': 'fa-folder-open',
    'crm': 'fa-users',
    'feature': 'fa-lightbulb',
    'other': 'fa-circle-question',
}


@register.filter
def sup_category_icon(category):
    return TICKET_CATEGORY_ICONS.get(category, 'fa-headset')


@register.filter
def sup_status_step(status):
    """مرحله timeline بر اساس وضعیت (۱ تا ۵)."""
    order = {
        'open': 1,
        'in_review': 2,
        'answered': 3,
        'waiting_user': 4,
        'closed': 5,
    }
    return order.get(status, 1)
