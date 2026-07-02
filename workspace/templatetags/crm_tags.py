from django import template
from django.utils.html import format_html

from workspace.constants import AGENCY_ROLE_STYLES, DEAL_STAGE_COLORS, PROPERTY_TX_COLORS, ROLE_COLORS
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
def crm_initials(name):
    """حرف اول نام برای آواتار."""
    if not name:
        return '؟'
    parts = str(name).strip().split()
    if len(parts) >= 2:
        return f'{parts[0][0]}{parts[1][0]}'
    return parts[0][0]


@register.filter
def crm_avatar_hue(name):
    """شاخص رنگ آواتار (۰–۵) از روی نام."""
    if not name:
        return 0
    return sum(ord(c) for c in str(name)) % 6


@register.filter
def split_tags(value, sep=','):
    if not value:
        return []
    return [t.strip() for t in str(value).split(sep) if t.strip()]


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


@register.simple_tag
def crm_deal_stage_style(stage):
    bg, fg = DEAL_STAGE_COLORS.get(stage, ('#f1f5f9', '#475569'))
    return f'background:{bg};color:{fg}'


@register.filter
def crm_deal_stage_dot(stage):
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


DEAL_STAGE_ICONS = {
    'سرنخ': 'fa-seedling',
    'مذاکره': 'fa-comments',
    'بازدید': 'fa-door-open',
    'پیش‌قرارداد': 'fa-file-signature',
    'قرارداد': 'fa-file-contract',
    'بسته‌شده': 'fa-trophy',
    'از دست رفته': 'fa-circle-xmark',
}


@register.filter
def crm_deal_stage_icon(stage):
    return DEAL_STAGE_ICONS.get(stage, 'fa-handshake')


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
    if prop.deal_mode == 'فروش' and prop.sale_price:
        return format_toman(prop.sale_price)
    parts = []
    if prop.deposit:
        parts.append(f'رهن {format_toman(prop.deposit)}')
    if prop.monthly_rent:
        parts.append(f'اجاره {format_toman(prop.monthly_rent)}')
    return ' · '.join(parts) if parts else ''


@register.simple_tag
def crm_portfolio_suggested_count(property_links, linked_listings):
    n = sum(1 for l in property_links if l.role == 'پیشنهادی')
    n += sum(1 for l in linked_listings if l.role == 'پیشنهادی')
    return n


@register.inclusion_tag('workspace/crm/includes/crm_field.html')
def crm_field(field, label=None, extra_class='', label_class='', show_label=True):
    return {
        'field': field,
        'label': label if label is not None else field.label,
        'extra_class': extra_class,
        'label_class': label_class,
        'show_label': show_label,
    }


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
        'املاک': 'fas fa-building',
        'ایمیل': 'fas fa-envelope',
    }
    return icons.get(activity_type, 'fas fa-circle')


@register.filter
def crm_cal_event_icon(event_type):
    icons = {
        'followup': 'fa-phone',
        'reminder': 'fa-bell',
        'visit': 'fa-door-open',
    }
    return icons.get(event_type, 'fa-calendar-day')


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
