from django import template

from product_hub.services.privacy import public_submitter_label
from product_hub.models import (
    BUG_SEVERITY_CHOICES,
    BUG_STATUS_CHOICES,
    CHANGE_TYPE_CHOICES,
    FEATURE_CATEGORY_CHOICES,
    FEATURE_STATUS_CHOICES,
    REQUEST_PRIORITY_CHOICES,
    REQUEST_STATUS_CHOICES,
)

register = template.Library()

FEATURE_STATUS_CLASS = {
    'active': 'ph-badge--green',
    'in_progress': 'ph-badge--blue',
    'planned': 'ph-badge--gray',
    'beta': 'ph-badge--amber',
}

REQUEST_STATUS_CLASS = {
    'submitted': 'ph-badge--gray',
    'reviewing': 'ph-badge--amber',
    'approved': 'ph-badge--blue',
    'in_development': 'ph-badge--purple',
    'completed': 'ph-badge--green',
    'rejected': 'ph-badge--red',
}

BUG_STATUS_CLASS = {
    'reported': 'ph-badge--gray',
    'reviewing': 'ph-badge--amber',
    'fixing': 'ph-badge--blue',
    'resolved': 'ph-badge--green',
}

BUG_SEVERITY_CLASS = {
    'critical': 'ph-badge--red',
    'high': 'ph-badge--amber',
    'medium': 'ph-badge--blue',
    'low': 'ph-badge--gray',
}

CHANGE_TYPE_CLASS = {
    'feature': 'ph-change--feature',
    'fix': 'ph-change--fix',
    'improvement': 'ph-change--improvement',
    'security': 'ph-change--security',
    'performance': 'ph-change--performance',
}


@register.simple_tag
def ph_feature_status_class(status):
    return FEATURE_STATUS_CLASS.get(status, 'ph-badge--gray')


@register.simple_tag
def ph_request_status_class(status):
    return REQUEST_STATUS_CLASS.get(status, 'ph-badge--gray')


@register.simple_tag
def ph_bug_status_class(status):
    return BUG_STATUS_CLASS.get(status, 'ph-badge--gray')


@register.simple_tag
def ph_bug_severity_class(severity):
    return BUG_SEVERITY_CLASS.get(severity, 'ph-badge--gray')


@register.simple_tag
def ph_change_type_class(change_type):
    return CHANGE_TYPE_CLASS.get(change_type, '')


@register.filter
def ph_submitter(user):
    return public_submitter_label(user)


@register.filter
def ph_label(value, kind):
    maps = {
        'category': dict(FEATURE_CATEGORY_CHOICES),
        'feature_status': dict(FEATURE_STATUS_CHOICES),
        'request_status': dict(REQUEST_STATUS_CHOICES),
        'priority': dict(REQUEST_PRIORITY_CHOICES),
        'bug_status': dict(BUG_STATUS_CHOICES),
        'severity': dict(BUG_SEVERITY_CHOICES),
        'change_type': dict(CHANGE_TYPE_CHOICES),
    }
    return maps.get(kind, {}).get(value, value)
