from urllib.parse import urlencode

from django import template

from workspace.services.display import to_jalali_display, transaction_profile
from workspace.services.jalali_input import format_jalali_date
from workspace.services.formatting import (
    format_area, format_pct, format_toman, format_toman_compact, format_toman_short, round_pct,
)

register = template.Library()


@register.inclusion_tag('workspace/includes/fields.html')
def render_fields(form, columns=1):
    return {'form': form, 'columns': columns}


@register.inclusion_tag('workspace/includes/page_header.html')
def mk_page_header(eyebrow, title, desc='', actions=None):
    """هدر یکپارچه صفحات — eyebrow، عنوان، توضیح، لیست actions."""
    return {
        'eyebrow': eyebrow,
        'title': title,
        'desc': desc,
        'actions': actions or [],
    }


@register.filter
def dict_get(mapping, key):
    if not mapping:
        return None
    return mapping.get(key)


@register.filter
def ws_money(value, arg=''):
    """arg: per_sqm"""
    per_sqm = arg == 'per_sqm'
    return format_toman(value, per_sqm=per_sqm)


@register.filter
def ws_money_short(value):
    return format_toman_short(value)


@register.filter
def ws_money_compact(value):
    return format_toman_compact(value)


@register.filter
def ws_pct(value):
    return format_pct(value)


@register.filter
def ws_area(value):
    return format_area(value)


@register.filter
def ws_jalali(value):
    return to_jalali_display(value)


@register.filter
def ws_jalali_date(value):
    """تاریخ شمسی بدون ساعت."""
    return format_jalali_date(value) or '—'


@register.filter
def ws_time(value):
    """ساعت محلی با ارقام فارسی."""
    from django.utils import timezone
    from workspace.services.jalali_input import to_persian_digits

    if not value:
        return '—'
    dt = timezone.localtime(value) if hasattr(value, 'hour') else value
    try:
        import jdatetime
        if hasattr(dt, 'hour'):
            j = jdatetime.datetime.fromgregorian(datetime=dt)
            return to_persian_digits(f'{j.hour:02d}:{j.minute:02d}')
    except Exception:
        pass
    if hasattr(dt, 'hour'):
        return to_persian_digits(f'{dt.hour:02d}:{dt.minute:02d}')
    return '—'


@register.filter
def ws_tx_profile(transaction_type):
    return transaction_profile(transaction_type)


@register.simple_tag
def ws_sort_url(filters, field, current_sort='', filter_qs=''):
    """لینک مرتب‌سازی ستون."""
    new_sort = f'-{field}' if current_sort == field else field
    if current_sort == f'-{field}':
        new_sort = field
    parts = []
    if filter_qs:
        parts.append(str(filter_qs))
    parts.append(f'sort={new_sort}')
    return '?' + '&'.join(parts)


@register.inclusion_tag('workspace/includes/amenity_icons.html')
def amenity_icons(features):
    return {'feat': features or {}}


@register.inclusion_tag('workspace/includes/pagination.html')
def mk_pagination(page_obj, query_params=None, aria_label='صفحه‌بندی'):
    """صفحه‌بندی با شماره صفحات و لینک‌های تمیز."""
    base = {
        k: v for k, v in (query_params or {}).items()
        if v not in ('', None) and k != 'page'
    }

    def page_href(page_number):
        return '?' + urlencode({**base, 'page': page_number})

    paginator = page_obj.paginator
    page_range = paginator.get_elided_page_range(
        number=page_obj.number,
        on_each_side=1,
        on_ends=1,
    )
    pages = []
    for num in page_range:
        if num == paginator.ELLIPSIS:
            pages.append({'type': 'ellipsis'})
        else:
            pages.append({
                'type': 'page',
                'num': num,
                'url': page_href(num),
                'active': num == page_obj.number,
            })

    return {
        'page_obj': page_obj,
        'pages': pages,
        'prev_url': page_href(page_obj.previous_page_number) if page_obj.has_previous else None,
        'next_url': page_href(page_obj.next_page_number) if page_obj.has_next else None,
        'start_index': page_obj.start_index(),
        'end_index': page_obj.end_index(),
        'total_count': paginator.count,
        'aria_label': aria_label,
    }


@register.filter
def ws_confidence(data):
    """Normalize report confidence for templates (dict with safe defaults)."""
    if data is None or isinstance(data, str):
        out = {}
    elif isinstance(data, dict):
        out = dict(data)
    else:
        out = {}
    raw = out.get('display_score', out.get('score', 0))
    try:
        display = min(100, int(raw))
    except (TypeError, ValueError):
        display = 0
    out.setdefault('score', display)
    out.setdefault('display_score', display)
    out.setdefault('level_plain', out.get('level') or '—')
    out.setdefault('level_hint', '')
    return out


@register.filter
def ws_conf_score(data):
    """Safe confidence score 0–100 for CSS/HTML."""
    if not isinstance(data, dict):
        return 0
    for key in ('display_score', 'score'):
        val = data.get(key)
        if val not in (None, ''):
            try:
                return min(100, int(val))
            except (TypeError, ValueError):
                pass
    return 0


@register.filter
def ws_conf_score_attr(data):
    """ASCII score string for CSS custom properties (avoids fa-IR digit localization)."""
    return str(ws_conf_score(data))


@register.filter
def ws_value_badge(score):
    if score is None:
        return ''
    try:
        if score != score:
            return ''
    except TypeError:
        pass
    if score <= -12:
        return 'below'
    if score >= 12:
        return 'above'
    return 'fair'


@register.filter
def feature_icon(label):
    """آیکون Font Awesome مناسب برای برچسب ویژگی / امکان / مشخصه."""
    from workspace.services.listing_features import _icon_for_key
    return _icon_for_key(label)
