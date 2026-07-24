"""رندر HTML بخش امکانات و دسترسی‌های منطقه در مقالات بازار."""
from __future__ import annotations

import html
from typing import Any

from workspace.services.jalali_input import to_persian_digits


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ''), quote=True)


def _n(value: Any) -> str:
    try:
        return _e(to_persian_digits(int(value)))
    except (TypeError, ValueError):
        return _e(value)


def render_district_access_section(access: Any, *, city: str, district: str) -> str:
    if not isinstance(access, dict):
        return ''
    if not access.get('ok'):
        reason = access.get('reason') or ''
        if reason in ('skipped', 'no_geo'):
            return ''
        msg = _e(access.get('message') or 'سرویس نقشه موقتاً در دسترس نیست.')
        return (
            '<section class="mk-market-section mk-access-section" id="district-access">'
            '<h2>امکانات و دسترسی‌های منطقه</h2>'
            f'<p class="mk-access-unavailable">'
            f'<i class="fas fa-triangle-exclamation" aria-hidden="true"></i> '
            f'برای {_e(district)} {_e(city)} هنوز امکانات محله محاسبه نشد: {msg} '
            f'پس از در دسترس بودن نقشه، پیش‌نمایش را دوباره بسازید.'
            f'</p></section>'
        )

    score = int(access.get('score') or 0)
    grade = _e(access.get('grade') or '—')
    grade_label = _e(access.get('grade_label') or '')
    radius = _e(access.get('radius_label') or access.get('radius_m') or '—')
    summary = _e(access.get('summary') or '')
    found = int(access.get('found_count') or 0)
    total = int(access.get('total_count') or 0)
    missing = int(access.get('missing_count') or max(0, total - found))
    total_pois = int(access.get('total_pois') or 0)

    hi_cards: list[str] = []
    for h in (access.get('highlights') or [])[:4]:
        parts = [
            f'<article class="mk-poi-chip" style="--acc-color:{_e(h.get("color") or "#0d9488")}">',
            '<span class="mk-poi-chip__icon" aria-hidden="true">',
            f'<i class="fas {_e(h.get("icon") or "fa-location-dot")}"></i></span>',
            '<span class="mk-poi-chip__body">',
            f'<em>{_e(h.get("label"))}</em>',
            f'<strong>{_e(h.get("distance_label") or "")}</strong>',
        ]
        if h.get('name'):
            parts.append(f'<span>{_e(h.get("name"))}</span>')
        if h.get('count'):
            parts.append(f'<em class="mk-poi-chip__count">{_n(h.get("count"))} مورد</em>')
        parts.append('</span></article>')
        hi_cards.append(''.join(parts))

    hi_block = ''
    if hi_cards:
        hi_block = (
            '<div class="mk-poi-highlights" aria-label="نزدیک‌ترین موارد">'
            + ''.join(hi_cards)
            + '</div>'
        )

    group_blocks: list[str] = []
    for g in access.get('groups') or []:
        rows: list[str] = []
        for item in g.get('items') or []:
            found_item = bool(item.get('found'))
            count = int(item.get('count') or 0)
            color = _e(item.get('color') or ('#0d9488' if found_item else '#94a3b8'))
            icon = _e(item.get('icon') or 'fa-location-dot')
            label = _e(item.get('label'))
            if found_item:
                row = [
                    f'<li class="mk-poi-item" style="--acc-color:{color}">',
                    f'<span class="mk-poi-item__icon" aria-hidden="true"><i class="fas {icon}"></i></span>',
                    '<div class="mk-poi-item__main">',
                    f'<span class="mk-poi-item__label">{label}</span>',
                ]
                if item.get('name'):
                    row.append(f'<span class="mk-poi-item__name">{_e(item.get("name"))}</span>')
                if item.get('key') != 'street_type' and count > 0:
                    row.append(f'<span class="mk-poi-item__count">{_n(count)} مورد</span>')
                row.append('</div><div class="mk-poi-item__side">')
                row.append(f'<strong>{_e(item.get("distance_label") or "")}</strong>')
                if item.get('walk_label'):
                    row.append(f'<small>{_e(item.get("walk_label"))}</small>')
                row.append('</div></li>')
                rows.append(''.join(row))
            else:
                empty = _e(item.get('empty_label') or 'یافت نشد')
                rows.append(
                    f'<li class="mk-poi-item mk-poi-item--missing" style="--acc-color:{color}">'
                    f'<span class="mk-poi-item__icon" aria-hidden="true"><i class="fas {icon}"></i></span>'
                    f'<div class="mk-poi-item__main">'
                    f'<span class="mk-poi-item__label">{label}</span>'
                    f'<span class="mk-poi-item__name">{empty}</span></div>'
                    f'<div class="mk-poi-item__side"><strong>—</strong></div></li>'
                )
        if not rows:
            continue
        group_blocks.append(
            '<section class="mk-poi-group">'
            f'<h3 class="mk-poi-group__title">{_e(g.get("label"))}</h3>'
            f'<ul class="mk-poi-list">{"".join(rows)}</ul>'
            '</section>'
        )

    missing_note = ''
    if missing:
        missing_note = (
            f'<p class="mk-poi-missing-note">{_n(missing)} مورد یافت‌نشده در شعاع {_e(radius)}</p>'
        )
    pois_bit = f' · {_n(total_pois)} نقطه خدماتی' if total_pois else ''

    return (
        '<section class="mk-market-section mk-access-section" id="district-access">'
        '<header class="mk-poi-head"><div class="mk-poi-head__lead">'
        '<span class="mk-poi-head__mark" aria-hidden="true"><i class="fas fa-map-location-dot"></i></span>'
        '<div>'
        '<h2>امکانات و دسترسی‌های منطقه</h2>'
        f'<p class="mk-poi-head__sub">دسترسی محلی · {_n(found)} از {_n(total)} مورد · شعاع {_e(radius)}{pois_bit}</p>'
        '</div></div></header>'
        f'<p>برای محله {_e(district)} در {_e(city)}، امکانات اطراف مرکز تراکم فایل‌ها از OpenStreetMap '
        'خوانده شده‌اند — همان منطق پنل فایل شخصی، با شمارش تعداد هر دسته '
        '(کلانتری، آتش‌نشانی، کافه، رستوران و …).</p>'
        f'<div class="mk-access-hero">'
        f'<div class="mk-access-score" style="--access-score:{score}">'
        '<div class="mk-access-score__ring" aria-hidden="true"></div>'
        f'<div class="mk-access-score__core"><strong>{_n(score)}</strong><span>از ۱۰۰</span></div></div>'
        f'<div class="mk-access-score__copy">'
        f'<p class="mk-access-grade"><span>{grade}</span> {grade_label}</p>'
        f'<p>{summary}</p></div></div>'
        f'{hi_block}'
        f'<div class="mk-poi-groups">{"".join(group_blocks)}</div>'
        f'{missing_note}'
        '<p class="mk-market-tip">فاصله‌ها خط مستقیم‌اند و تقریبی‌اند. '
        'تعدادها برای مقایسه محله‌هاست، نه جایگزین بازدید میدانی.</p>'
        '</section>'
    )
