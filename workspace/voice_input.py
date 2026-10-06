"""Workspace voice-input eligibility for free-text form fields."""
from django import forms

VOICE_FIELD_NAMES = frozenset({
    'title', 'name', 'subject', 'description', 'notes', 'note', 'details', 'content',
    'body', 'message', 'comment', 'summary', 'reason', 'result', 'address', 'district',
    'neighborhood', 'amenities_extra', 'owner_name', 'tenant_name', 'tags', 'job',
    'company_name', 'transition_note', 'transition_note_progress', 'lost_reason_other',
    'payout_notes', 'next_action_note', 'reject_reason', 'reason_text',
    'problem', 'why_important', 'agency_address', 'share_message',
})

VOICE_EXCLUDED_NAMES = frozenset({
    'q', 'search', 'query', 'phone', 'mobile', 'tel', 'email', 'url', 'link',
    'username', 'password', 'slug', 'token', 'secret', 'national_id', 'postal_code',
    'zip', 'code', 'otp', 'latitude', 'longitude', 'agency_latitude', 'agency_longitude',
    'agency_landline', 'agency_landline_alt', 'agency_website', 'agency_slug',
    'area', 'area_min', 'area_max', 'price', 'price_min', 'price_max', 'rooms',
    'year_min', 'year_max', 'age_max', 'min_price', 'max_price', 'value',
    'buyer_commission_amount', 'seller_commission_amount', 'deal_costs', 'received_amount',
    'contract_amount', 'contract_number', 'deposit', 'rent', 'monthly_rent', 'sale_price',
    'trigger_days', 'action_reminder_days', 'duration_minutes', 'visit_date', 'due_at',
    'next_follow_up', 'next_action_at', 'at', 'event_type', 'agency_member_q',
    'region', 'agency_city', 'action_reminder_title', 'trigger_statuses',
    'category', 'channel', 'doc_type', 'stage', 'customer_id', 'property_id',
})

VOICE_EXCLUDED_TYPES = frozenset({
    'hidden', 'checkbox', 'radio', 'number', 'tel', 'email', 'url', 'search',
    'date', 'time', 'datetime-local', 'file', 'password',
})


def _field_name(field) -> str:
    return (getattr(field, 'name', None) or '').lower()


def _widget_attrs(field) -> dict:
    widget = field.field.widget
    return getattr(widget, 'attrs', None) or {}


def field_allows_workspace_voice(field) -> bool:
    """Whether render_fields should wrap this field with the shared voice mic."""
    if field is None:
        return False
    name = _field_name(field)
    attrs = _widget_attrs(field)
    if 'data-voice-input' in attrs:
        return attrs.get('data-voice-input') != 'off'
    if name in VOICE_EXCLUDED_NAMES:
        return False
    if attrs.get('readonly') or attrs.get('disabled'):
        return False
    if attrs.get('data-money') or attrs.get('data-jdp'):
        return False
    inputmode = (attrs.get('inputmode') or '').lower()
    if inputmode in ('numeric', 'decimal', 'tel'):
        return False

    widget = field.field.widget
    input_type = getattr(widget, 'input_type', None) or ''
    if input_type in VOICE_EXCLUDED_TYPES:
        return False

    if isinstance(widget, forms.Textarea):
        return name in VOICE_FIELD_NAMES or name.endswith('_note') or name.endswith('_notes')

    if input_type == 'text':
        return name in VOICE_FIELD_NAMES or name.endswith('_note')

    return False


def apply_voice_input_off(field, off: bool = True) -> None:
    """Mark a form field widget as excluded from auto voice (data-voice-input=off)."""
    if field is None:
        return
    field.field.widget.attrs['data-voice-input'] = 'off' if off else ''
