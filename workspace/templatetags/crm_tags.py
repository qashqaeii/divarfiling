from django import template
from django.templatetags.static import static
from django.utils.html import format_html

from accounts.avatar_catalog import (
    DEFAULT_AVATAR_KEY,
    avatar_static_relative_path,
    resolve_contact_avatar_display,
)
from workspace.constants import (
    AGENCY_ROLE_STYLES, DEAL_STAGE_COLORS, DEAL_STAGE_ICONS, PROPERTY_TX_COLORS, ROLE_COLORS, shows_lease_deadline,
)
from workspace.services.crm import role_color

register = template.Library()


@register.simple_tag
def crm_agency_role_style(role):
    bg, fg = AGENCY_ROLE_STYLES.get(role, ('#f1f5f9', '#475569'))
    return f'background:{bg};color:{fg}'


@register.simple_tag
def crm_role_style(role):
    bg, fg = role_color(role)
    return f'background:{bg};color:{fg}'


@register.simple_tag
def crm_role_style_attr(role):
    """خروجی attribute کامل style برای جلوگیری از خطای linter در قالب."""
    bg, fg = role_color(role)
    return format_html('style="background:{};color:{}"', bg, fg)


@register.filter
def nav_badge_count(value):
    """نمایش شمارنده ناوبری — حداکثر ۹۹+."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ''
    if n <= 0:
        return ''
    if n > 99:
        return '99+'
    return str(n)


@register.filter
def shows_lease_deadline_filter(customer_type):
    """آیا فیلد مهلت اجاره برای این نوع مخاطب نمایش داده شود؟"""
    return shows_lease_deadline(customer_type)


@register.simple_tag
def crm_default_avatar_url():
    return static(avatar_static_relative_path(DEFAULT_AVATAR_KEY))


@register.simple_tag(takes_context=True)
def crm_contact_avatar_url(context, customer):
    """URL نمایش آواتار مخاطب: عکس اختصاصی یا آواتار نقش/جنسیت."""
    request = context.get('request')
    display = resolve_contact_avatar_display(customer, request=request)
    return display['photo_url'] or ''


@register.filter
def crm_initials(name):
    """حرف اول نام برای آواتار."""
    if not name:
        return '؟'
    parts = str(name).strip().split()
    if not parts:
        return '؟'
    if len(parts) >= 2:
        return f'{parts[0][0]}{parts[1][0]}'
    return parts[0][0]


@register.filter
def crm_avatar_hue(name):
    """شاخص رنگ آواتار (۰–۵) از روی نام."""
    if not name:
        return 0
    stripped = str(name).strip()
    if not stripped:
        return 0
    return sum(ord(c) for c in stripped) % 6


@register.filter
def split_tags(value, sep=','):
    if not value:
        return []
    return [t.strip() for t in str(value).split(sep) if t.strip()]


@register.filter
def split_areas(value):
    from workspace.services.crm_matching import _parse_areas
    return _parse_areas(value or '')


STATUS_STYLES = {
    'جدید': ('#eff6ff', '#1d4ed8', '#3b82f6'),
    'در حال پیگیری': ('#fffbeb', '#b45309', '#f59e0b'),
    'بازدید انجام شد': ('#f0fdf4', '#15803d', '#22c55e'),
    'قرارداد': ('#f5f3ff', '#6d28d9', '#8b5cf6'),
    'بایگانی': ('#f8fafc', '#64748b', '#94a3b8'),
}


@register.simple_tag
def crm_status_style(status):
    bg, fg, dot = STATUS_STYLES.get(status, ('#f1f5f9', '#475569', '#94a3b8'))
    return f'background:{bg};color:{fg}'


@register.filter
def crm_status_dot(status):
    return STATUS_STYLES.get(status, ('', '', '#94a3b8'))[2]


@register.filter
def crm_follow_due_class(customer):
    """کلاس CSS برای تاریخ پیگیری: is-overdue | is-today."""
    follow = getattr(customer, 'next_follow_up', None)
    if not follow:
        return ''
    from django.utils import timezone
    today = timezone.now().date()
    if follow < today:
        return 'is-overdue'
    if follow == today:
        return 'is-today'
    return ''


@register.simple_tag(takes_context=True)
def crm_deal_stage_style(context, stage):
    meta = (context.get('deal_stage_meta') or {}).get(stage) or {}
    if meta.get('bg') or meta.get('color'):
        bg = meta.get('bg') or '#f1f5f9'
        fg = meta.get('color') or '#475569'
        return f'background:{bg};color:{fg}'
    bg, fg = DEAL_STAGE_COLORS.get(stage, ('#f1f5f9', '#475569'))
    return f'background:{bg};color:{fg}'


@register.filter
def crm_deal_stage_dot(stage, meta_map=None):
    if isinstance(meta_map, dict):
        row = meta_map.get(stage) or {}
        if row.get('color'):
            return row['color']
    return DEAL_STAGE_COLORS.get(stage, ('', '#94a3b8'))[1]


@register.simple_tag
def crm_tx_status_style(status):
    bg, fg, _dot = PROPERTY_TX_COLORS.get(status, ('#f1f5f9', '#475569', '#94a3b8'))
    return f'background:{bg};color:{fg}'


@register.filter
def crm_tx_status_dot(status):
    return PROPERTY_TX_COLORS.get(status, ('', '', '#94a3b8'))[2]


PROPERTY_TX_ICONS = {
    'فعال': 'fa-bolt',
    'در مذاکره': 'fa-comments',
    'قرارداد': 'fa-file-signature',
    'فروخته‌شده': 'fa-hand-holding-dollar',
    'اجاره‌رفته': 'fa-key',
    'بایگانی': 'fa-box-archive',
}


@register.filter
def crm_tx_status_icon(status):
    return PROPERTY_TX_ICONS.get(status, 'fa-building')


@register.filter
def crm_deal_stage_icon(stage, meta_map=None):
    if isinstance(meta_map, dict):
        row = meta_map.get(stage) or {}
        if row.get('icon'):
            return row['icon']
    return DEAL_STAGE_ICONS.get(stage, 'fa-handshake')


@register.filter
def crm_deal_is_stale(deal, meta_map=None):
    from workspace.services.crm_deals import is_deal_stale
    meta = None
    if isinstance(meta_map, dict):
        meta = meta_map.get(getattr(deal, 'stage', None))
    return is_deal_stale(deal, meta)


@register.simple_tag
def crm_deal_next_action(deal):
    from workspace.services.crm_deal_followup import serialize_next_action
    return serialize_next_action(deal)


@register.simple_tag
def crm_match_tab_count(match_data):
    """تعداد کل پیشنهادهای تطبیق — برای badge تب."""
    if not match_data or not match_data.get('eligible'):
        return 0
    if 'total_count' in match_data:
        return int(match_data['total_count'])
    groups = match_data.get('match_groups') or []
    if groups:
        return sum(
            len(g.get('crm_matches') or []) + len(g.get('divar_matches') or [])
            for g in groups
        )
    return len(match_data.get('crm_matches') or []) + len(match_data.get('divar_matches') or [])


@register.simple_tag
def crm_property_price_label(prop):
    """برچسب قیمت ملک CRM برای کارت‌های پورتفولیو."""
    from workspace.services.formatting import format_toman
    if not prop:
        return ''
    parts = []
    if prop.deposit:
        parts.append(f'رهن {format_toman(prop.deposit)}')
    if prop.monthly_rent:
        parts.append(f'اجاره {format_toman(prop.monthly_rent)}')
    if parts:
        return ' · '.join(parts)
    if prop.sale_price:
        return format_toman(prop.sale_price)
    return ''


@register.filter
def crm_area_metric(value):
    """عدد متراژ تمیز برای هدر کارت — بدون تکرار «متر»."""
    if value in (None, ''):
        return ''
    text = str(value).strip()
    for junk in ('متر مربع', 'مترمربع', 'متر', 'm2', 'm²', 'M2'):
        text = text.replace(junk, '')
    text = text.strip(' .،,')
    if not text:
        return ''
    try:
        return str(int(round(float(text.replace(',', '')))) )
    except (TypeError, ValueError):
        return text


@register.filter
def crm_amenity_chips(amenities, limit=3):
    """چند امکان اول ملک برای کارت پورتفولیو."""
    if not amenities:
        return []
    raw = str(amenities).replace('،', ',').replace('\n', ',')
    items = [x.strip() for x in raw.split(',') if x.strip()]
    return items[: int(limit)]


@register.filter
def crm_audit_label(event):
    from workspace.services.crm_audit import audit_event_label
    return audit_event_label(event or '')


@register.filter
def crm_audit_icon(event):
    from workspace.services.crm_audit import get_audit_event_meta
    return get_audit_event_meta(event or '').get('icon', 'fa-circle-info')


@register.simple_tag
def crm_portfolio_suggested_count(property_links, linked_listings):
    n = sum(1 for l in property_links if l.role == 'پیشنهادی')
    n += sum(1 for l in linked_listings if l.role == 'پیشنهادی')
    return n


@register.inclusion_tag('workspace/crm/includes/crm_field.html')
def crm_field(field, label=None, extra_class='', label_class='', show_label=True, voice=False):
    return {
        'field': field,
        'label': label if label is not None else field.label,
        'extra_class': extra_class,
        'label_class': label_class,
        'show_label': show_label,
        'voice': bool(voice),
    }


@register.filter
def crm_activity_day_label(dt):
    """برچسب روز برای گروه‌بندی تایم‌لاین فعالیت (امروز / دیروز / تاریخ شمسی)."""
    if not dt:
        return ''
    from datetime import timedelta

    from django.utils import timezone

    from workspace.services.jalali_input import format_jalali_date

    local = timezone.localtime(dt)
    today = timezone.localtime(timezone.now()).date()
    d = local.date()
    if d == today:
        return 'امروز'
    if d == today - timedelta(days=1):
        return 'دیروز'
    return format_jalali_date(dt) or ''


@register.filter
def crm_activity_day_secondary(dt):
    """تاریخ شمسی ثانویه برای امروز/دیروز در گروه‌بندی فعالیت."""
    if not dt:
        return ''
    from datetime import timedelta

    from django.utils import timezone

    from workspace.services.jalali_input import format_jalali_date

    local = timezone.localtime(dt)
    today = timezone.localtime(timezone.now()).date()
    d = local.date()
    if d == today or d == today - timedelta(days=1):
        return format_jalali_date(dt) or ''
    return ''


@register.filter
def crm_activity_icon(activity_type):
    icons = {
        'تماس': 'fas fa-phone',
        'پیامک': 'fas fa-sms',
        'واتساپ': 'fab fa-whatsapp',
        'پیام': 'fas fa-comment',
        'بازدید': 'fas fa-door-open',
        'پیگیری': 'fas fa-calendar-check',
        'جلسه': 'fas fa-handshake',
        'یادداشت': 'fas fa-sticky-note',
        'وظیفه': 'fas fa-list-check',
        'یادآور': 'fas fa-bell',
        'تغییر وضعیت': 'fas fa-arrows-rotate',
        'املاک': 'fas fa-house',
        'پیشنهاد': 'fas fa-house',
        'ایمیل': 'fas fa-envelope',
    }
    return icons.get(activity_type, 'fas fa-circle')


@register.filter
def crm_cal_event_icon(event_type):
    icons = {
        'followup': 'fa-phone',
        'reminder': 'fa-bell',
        'visit': 'fa-door-open',
        'contract': 'fa-file-signature',
    }
    return icons.get(event_type, 'fa-calendar-day')


@register.filter
def crm_cal_event_type_label(event_type):
    labels = {
        'followup': 'پیگیری',
        'reminder': 'یادآور',
        'visit': 'بازدید',
        'contract': 'قرارداد',
    }
    return labels.get(event_type, 'رویداد')


@register.filter
def to_persian_digits(value):
    from workspace.services.jalali_input import to_persian_digits as _to_pd
    if value is None:
        return ''
    return _to_pd(value)


@register.filter
def crm_reminder_tone(reminder):
    """بازه فوریت: overdue | today | upcoming | done."""
    from datetime import timedelta

    from django.utils import timezone

    if reminder.is_done:
        return 'done'
    now = timezone.now()
    if reminder.due_at < now:
        return 'overdue'
    local = timezone.localtime(reminder.due_at)
    local_now = timezone.localtime(now)
    if local.date() == local_now.date():
        return 'today'
    tomorrow = local_now.date() + timedelta(days=1)
    if local.date() == tomorrow:
        return 'tomorrow'
    return 'upcoming'


@register.filter
def crm_reminder_time_only(value):
    """ساعت سررسید به شمسی."""
    from django.utils import timezone

    from workspace.services.jalali_input import to_persian_digits

    if not value:
        return '—'
    dt = timezone.localtime(value)
    try:
        import jdatetime
        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return to_persian_digits(f'{j.hour:02d}:{j.minute:02d}')
    except Exception:
        return to_persian_digits(f'{dt.hour:02d}:{dt.minute:02d}')


@register.filter
def crm_reminder_rel_label(reminder):
    """برچسب نسبی سررسید."""
    from datetime import timedelta

    from django.utils import timezone

    from workspace.services.jalali_input import format_jalali_date, to_persian_digits

    if reminder.is_done:
        return 'انجام‌شده'
    now = timezone.now()
    due = timezone.localtime(reminder.due_at)
    local_now = timezone.localtime(now)
    if reminder.due_at < now:
        days = (local_now.date() - due.date()).days
        if days <= 0:
            return 'معوق'
        if days == 1:
            return 'دیروز'
        return to_persian_digits(f'{days} روز معوق')
    if due.date() == local_now.date():
        return 'امروز'
    tomorrow = local_now.date() + timedelta(days=1)
    if due.date() == tomorrow:
        return 'فردا'
    days = (due.date() - local_now.date()).days
    if days <= 7:
        return to_persian_digits(f'{days} روز دیگر')
    return format_jalali_date(reminder.due_at) or '—'


@register.filter
def crm_reminder_show_note(reminder):
    """یادداشت تکراری با عنوان یا چیپ مخاطب را در لیست نشان نده."""
    note = (getattr(reminder, 'note', None) or '').strip()
    if not note:
        return False
    title = (getattr(reminder, 'title', None) or '').strip()
    if note == title:
        return False
    customer = getattr(reminder, 'customer', None)
    name = getattr(customer, 'name', None) if customer else None
    if name and name in note and 'یادآور' in note and len(note) <= len(name) + 24:
        return False
    return True


@register.filter
def crm_reminder_overdue_stale(reminder):
    """معوقی‌های بسیار دیرکرد — تاکید بصری بیشتر در موبایل."""
    from django.utils import timezone

    if getattr(reminder, 'is_done', False):
        return False
    due_at = getattr(reminder, 'due_at', None)
    if not due_at or due_at >= timezone.now():
        return False
    due = timezone.localtime(due_at).date()
    local_now = timezone.localtime(timezone.now()).date()
    return (local_now - due).days >= 14


@register.filter
def crm_property_type_icon(property_type):
    icons = {
        'آپارتمان': 'fa-building',
        'ویلا': 'fa-house-chimney',
        'کلنگی': 'fa-warehouse',
        'اداری': 'fa-briefcase',
        'مغازه': 'fa-store',
        'زمین': 'fa-map',
        'سایر': 'fa-layer-group',
    }
    return icons.get(property_type, 'fa-building')


@register.filter
def crm_template_sample(body):
    from workspace.services.crm_templates import preview_template_body
    return preview_template_body(body or '')


@register.filter
def crm_template_category_icon(category):
    icons = {
        'پیگیری': 'fa-phone',
        'بازدید': 'fa-door-open',
        'پیشنهاد': 'fa-building',
        'خوش‌آمد': 'fa-hand-sparkles',
        'سفارشی': 'fa-pen-fancy',
    }
    return icons.get(category, 'fa-message')


@register.simple_tag
def crm_placeholder_meta():
    return [
        ('{name}', 'نام', 'fa-user'),
        ('{phone}', 'تلفن', 'fa-phone'),
        ('{type}', 'نوع', 'fa-tag'),
        ('{status}', 'وضعیت', 'fa-signal'),
        ('{areas}', 'منطقه', 'fa-location-dot'),
        ('{agency}', 'آژانس', 'fa-building'),
    ]


def _normalized_mobile(phone: str) -> str:
    from workspace.services.crm import normalize_phone
    return normalize_phone(phone or '')


@register.filter
def phone_tel_href(phone):
    """href برای تماس تلفنی."""
    key = _normalized_mobile(phone)
    return f'tel:{key}' if key else ''


@register.filter
def phone_wa_href(phone):
    """لینک واتساپ (wa.me) از شماره ایران."""
    key = _normalized_mobile(phone)
    if not key:
        return ''
    digits = key[1:] if key.startswith('0') else key
    if digits.startswith('98'):
        return f'https://wa.me/{digits}'
    return f'https://wa.me/98{digits}'


@register.filter
def phone_sms_href(phone):
    """href برای پیامک."""
    key = _normalized_mobile(phone)
    return f'sms:{key}' if key else ''


@register.inclusion_tag('workspace/crm/includes/contact_social_channels.html')
def crm_contact_channels_form(form):
    from workspace.services.contact_channels import contact_channels_form_list_for_form
    return {'channels': contact_channels_form_list_for_form(form)}


@register.inclusion_tag('workspace/crm/includes/contact_areas_picker.html')
def crm_contact_areas_picker(form, field_name, label, wrapper_class='', dataset_neighborhoods=None):
    return {
        'field': form[field_name],
        'field_name': field_name,
        'label': label,
        'wrapper_class': wrapper_class,
        'dataset_neighborhoods': dataset_neighborhoods or [],
    }


@register.filter
def dict_get(mapping, key):
    if not mapping:
        return key
    return mapping.get(key, key)


@register.simple_tag
def contact_followup_mob(follow_date, today):
    """برچسب پیگیری برای لیست موبایل مخاطبین."""
    from workspace.services.jalali_input import format_jalali_date, to_persian_digits

    empty = {'tone': '', 'label': '', 'sublabel': ''}
    if not follow_date:
        return empty
    jalali = to_persian_digits(format_jalali_date(follow_date) or '')
    if follow_date < today:
        days = (today - follow_date).days
        if days <= 1:
            label = 'دیروز' if days == 1 else 'معوق'
        else:
            label = f'{to_persian_digits(days)} روز گذشته'
        return {'tone': 'overdue', 'label': label, 'sublabel': jalali}
    if follow_date == today:
        return {'tone': 'today', 'label': 'امروز پیگیری', 'sublabel': jalali}
    return {'tone': 'future', 'label': jalali, 'sublabel': ''}
