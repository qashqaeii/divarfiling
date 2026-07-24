"""رندر HTML بخش امکانات و دسترسی‌های منطقه در مقالات بازار — فقط تعداد."""
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
            f'امکانات {_e(district)} {_e(city)} فعلاً محاسبه نشد: {msg}'
            f'</p></section>'
        )

    score = int(access.get('score') or 0)
    grade = _e(access.get('grade') or '—')
    grade_label = _e(access.get('grade_label') or '')
    radius = _e(access.get('radius_label') or access.get('radius_m') or '—')
    summary = _e(access.get('summary') or '')
    total_pois = int(access.get('total_pois') or 0)
    category_found = int(access.get('found_count') or 0)
    category_total = int(access.get('total_count') or 0)

    hi_cards: list[str] = []
    for h in (access.get('highlights') or [])[:4]:
        count = int(h.get('count') or 0)
        if count <= 0:
            continue
        hi_cards.append(
            f'<article class="mk-poi-chip" style="--acc-color:{_e(h.get("color") or "#0d9488")}">'
            f'<span class="mk-poi-chip__icon" aria-hidden="true">'
            f'<i class="fas {_e(h.get("icon") or "fa-location-dot")}"></i></span>'
            f'<span class="mk-poi-chip__body">'
            f'<em>{_e(h.get("label"))}</em>'
            f'<strong>{_n(count)} مورد</strong>'
            f'</span></article>'
        )
    hi_block = ''
    if hi_cards:
        hi_block = (
            '<div class="mk-poi-highlights" aria-label="بیشترین امکانات">'
            + ''.join(hi_cards)
            + '</div>'
        )

    group_blocks: list[str] = []
    for g in access.get('groups') or []:
        rows: list[str] = []
        for item in g.get('items') or []:
            if item.get('key') == 'street_type':
                continue
            count = int(item.get('count') or 0)
            if count <= 0:
                continue
            color = _e(item.get('color') or '#0d9488')
            icon = _e(item.get('icon') or 'fa-location-dot')
            rows.append(
                f'<li class="mk-poi-item mk-poi-item--count" style="--acc-color:{color}">'
                f'<span class="mk-poi-item__icon" aria-hidden="true"><i class="fas {icon}"></i></span>'
                f'<div class="mk-poi-item__main">'
                f'<span class="mk-poi-item__label">{_e(item.get("label"))}</span>'
                f'</div>'
                f'<div class="mk-poi-item__side">'
                f'<strong>{_n(count)}</strong><small>مورد</small>'
                f'</div></li>'
            )
        if not rows:
            continue
        group_blocks.append(
            '<section class="mk-poi-group">'
            f'<h3 class="mk-poi-group__title">{_e(g.get("label"))}</h3>'
            f'<ul class="mk-poi-list">{"".join(rows)}</ul>'
            '</section>'
        )

    missing = [
        g for g in (access.get('gaps') or [])
        if g.get('key') != 'street_type'
    ][:6]
    missing_note = ''
    if missing:
        chips = '، '.join(_e(m.get('label')) for m in missing if m.get('label'))
        if chips:
            missing_note = f'<p class="mk-poi-missing-note">در شعاع بررسی یافت نشد: {chips}</p>'

    sub_bits = [f'شعاع {_e(radius)}']
    if total_pois:
        sub_bits.append(f'{_n(total_pois)} نقطه خدماتی')
    if category_found and category_total:
        sub_bits.append(f'{_n(category_found)} از {_n(category_total)} دسته')
    sub = ' · '.join(sub_bits)

    return (
        '<section class="mk-market-section mk-access-section" id="district-access">'
        '<header class="mk-poi-head"><div class="mk-poi-head__lead">'
        '<span class="mk-poi-head__mark" aria-hidden="true"><i class="fas fa-map-location-dot"></i></span>'
        '<div>'
        '<h2>امکانات و دسترسی‌های منطقه</h2>'
        f'<p class="mk-poi-head__sub">{sub}</p>'
        '</div></div></header>'
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
        '</section>'
    )
