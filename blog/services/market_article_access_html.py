"""رندر HTML بخش امکانات و دسترسی‌های منطقه — مقاوم در برابر استایل prose بلاگ."""
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


def _distance_label(meters: Any) -> str:
    try:
        m = int(meters)
    except (TypeError, ValueError):
        return ''
    if m <= 0:
        return ''
    if m < 1000:
        return f'{_n(m)} متر'
    km = m / 1000.0
    if abs(km - round(km)) < 0.05:
        return f'{_n(int(round(km)))} کیلومتر'
    label = f'{km:.1f}'.rstrip('0').rstrip('.')
    return f'{_e(to_persian_digits(label))} کیلومتر'


def _iter_count_items(access: dict) -> list[dict[str, Any]]:
    """لیست یکدست از دسته‌های دارای تعداد — از groups یا categories/items."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def _push(item: dict[str, Any]) -> None:
        key = str(item.get('key') or item.get('label') or '')
        if not key or key in seen:
            return
        if key in {'street_type', 'motorway', 'main_road'}:
            return
        count = int(item.get('count') or 0)
        if count <= 0:
            return
        seen.add(key)
        out.append(item)

    for g in access.get('groups') or []:
        for item in g.get('items') or []:
            if isinstance(item, dict):
                _push(item)

    for key in ('categories', 'items', 'highlights'):
        for item in access.get(key) or []:
            if isinstance(item, dict):
                _push(item)

    out.sort(key=lambda x: int(x.get('count') or 0), reverse=True)
    return out


def render_district_access_section(access: Any, *, city: str, district: str) -> str:
    if not isinstance(access, dict) or not access:
        return ''
    if not access.get('ok'):
        reason = access.get('reason') or ''
        if reason in ('skipped', 'no_geo'):
            return ''
        msg = _e(access.get('message') or 'سرویس نقشه موقتاً در دسترس نیست.')
        return (
            '<section class="mk-access-section" id="district-access">'
            '<div class="mk-access-shell">'
            '<h2 class="mk-access-title">امکانات و دسترسی‌های منطقه</h2>'
            f'<p class="mk-access-unavailable">'
            f'<i class="fas fa-triangle-exclamation" aria-hidden="true"></i> '
            f'امکانات {_e(district)} {_e(city)} فعلاً محاسبه نشد: {msg}'
            f'</p></div></section>'
        )

    score = int(access.get('score') or 0)
    grade = _e(access.get('grade') or '—')
    grade_label = _e(access.get('grade_label') or '')
    radius = _e(access.get('radius_label') or access.get('radius_m') or '—')
    summary = _e(access.get('summary') or '')
    total_pois = int(access.get('total_pois') or 0)
    category_found = int(access.get('found_count') or 0)
    category_total = int(access.get('total_count') or 0)

    count_items = _iter_count_items(access)

    hi_cards: list[str] = []
    for h in count_items[:4]:
        count = int(h.get('count') or 0)
        nearest = _distance_label(h.get('nearest_m'))
        nearest_html = (
            f'<span class="mk-access-hi__near">نزدیک‌ترین: {nearest}</span>'
            if nearest else ''
        )
        hi_cards.append(
            f'<div class="mk-access-hi" style="--acc-color:{_e(h.get("color") or "#0d9488")}">'
            f'<span class="mk-access-hi__icon" aria-hidden="true">'
            f'<i class="fas {_e(h.get("icon") or "fa-location-dot")}"></i></span>'
            f'<span class="mk-access-hi__label">{_e(h.get("label"))}</span>'
            f'<span class="mk-access-hi__count">{_n(count)}</span>'
            f'{nearest_html}'
            f'</div>'
        )
    hi_block = (
        f'<div class="mk-access-hi-grid">{"".join(hi_cards)}</div>'
        if hi_cards else ''
    )

    # شبکه تخت همه دسته‌ها — همیشه با برچسب + عدد بزرگ (مثل کلینیک ۲۲۴)
    tally_cells: list[str] = []
    for item in count_items[:24]:
        color = _e(item.get('color') or '#0d9488')
        icon = _e(item.get('icon') or 'fa-location-dot')
        nearest = _distance_label(item.get('nearest_m'))
        near_bit = f'<span class="mk-access-tally__near">{nearest}</span>' if nearest else ''
        tally_cells.append(
            f'<div class="mk-access-tally" style="--acc-color:{color}">'
            f'<span class="mk-access-tally__icon" aria-hidden="true">'
            f'<i class="fas {icon}"></i></span>'
            f'<span class="mk-access-tally__label">{_e(item.get("label"))}</span>'
            f'<span class="mk-access-tally__count">{_n(item.get("count"))}</span>'
            f'{near_bit}'
            f'</div>'
        )
    tally_block = (
        f'<div class="mk-access-tally-block">'
        f'<div class="mk-access-tally-block__title">تعداد امکانات در شعاع بررسی</div>'
        f'<div class="mk-access-tally-grid">{"".join(tally_cells)}</div>'
        f'</div>'
        if tally_cells else ''
    )

    group_blocks: list[str] = []
    for g in access.get('groups') or []:
        cells: list[str] = []
        for item in g.get('items') or []:
            if item.get('key') in {'street_type', 'motorway', 'main_road'}:
                continue
            count = int(item.get('count') or 0)
            if count <= 0:
                continue
            color = _e(item.get('color') or '#0d9488')
            icon = _e(item.get('icon') or 'fa-location-dot')
            nearest = _distance_label(item.get('nearest_m'))
            near_bit = (
                f'<span class="mk-access-cell__near">{nearest}</span>'
                if nearest else ''
            )
            cells.append(
                f'<div class="mk-access-cell" style="--acc-color:{color}">'
                f'<span class="mk-access-cell__icon" aria-hidden="true">'
                f'<i class="fas {icon}"></i></span>'
                f'<span class="mk-access-cell__text">'
                f'<span class="mk-access-cell__label">{_e(item.get("label"))}</span>'
                f'{near_bit}'
                f'</span>'
                f'<span class="mk-access-cell__count">{_n(count)}</span>'
                f'</div>'
            )
        if not cells:
            continue
        group_blocks.append(
            f'<div class="mk-access-group-card">'
            f'<div class="mk-access-group-card__title">{_e(g.get("label"))}</div>'
            f'<div class="mk-access-cell-grid">{"".join(cells)}</div>'
            f'</div>'
        )

    groups_block = (
        f'<div class="mk-access-groups">{"".join(group_blocks)}</div>'
        if group_blocks else ''
    )

    missing = [
        g for g in (access.get('gaps') or [])
        if g.get('key') not in {'street_type', 'motorway', 'main_road'}
    ][:6]
    missing_block = ''
    if missing:
        chips = ''.join(
            f'<span class="mk-access-miss-chip">{_e(m.get("label"))}</span>'
            for m in missing if m.get('label')
        )
        if chips:
            missing_block = (
                f'<div class="mk-access-miss">'
                f'<span class="mk-access-miss__label">یافت‌نشده در شعاع بررسی</span>'
                f'<div class="mk-access-miss__chips">{chips}</div></div>'
            )

    meta_bits = [f'شعاع {_e(radius)}']
    if total_pois:
        meta_bits.append(f'{_n(total_pois)} نقطه خدماتی')
    if category_found and category_total:
        meta_bits.append(f'{_n(category_found)} از {_n(category_total)} دسته')
    meta = ' · '.join(meta_bits)

    if not tally_block and not groups_block and not hi_block:
        return (
            f'<section class="mk-access-section" id="district-access">'
            f'<div class="mk-access-shell">'
            f'<h2 class="mk-access-title">امکانات و دسترسی‌های منطقه</h2>'
            f'<p class="mk-access-unavailable">'
            f'برای {_e(district)} {_e(city)} نقطه خدماتی کافی در شعاع بررسی یافت نشد.'
            f'</p></div></section>'
        )

    return (
        f'<section class="mk-access-section" id="district-access" data-district="{_e(district)}" data-city="{_e(city)}">'
        f'<div class="mk-access-shell">'
        f'<header class="mk-access-head">'
        f'<span class="mk-access-head__mark" aria-hidden="true"><i class="fas fa-map-location-dot"></i></span>'
        f'<div class="mk-access-head__text">'
        f'<h2 class="mk-access-title">امکانات و دسترسی‌های منطقه</h2>'
        f'<p class="mk-access-meta">{meta}</p>'
        f'</div></header>'
        f'<div class="mk-access-hero">'
        f'<div class="mk-access-score" style="--access-score:{score}" aria-label="امتیاز {_n(score)} از ۱۰۰">'
        f'<div class="mk-access-score__ring" aria-hidden="true"></div>'
        f'<div class="mk-access-score__core">'
        f'<strong class="mk-access-score__num">{_n(score)}</strong>'
        f'<span class="mk-access-score__den">از ۱۰۰</span>'
        f'</div></div>'
        f'<div class="mk-access-hero__copy">'
        f'<p class="mk-access-grade"><span class="mk-access-grade__badge">{grade}</span>'
        f'<span class="mk-access-grade__label">{grade_label}</span></p>'
        f'<p class="mk-access-summary">{summary}</p>'
        f'</div></div>'
        f'{hi_block}'
        f'{tally_block}'
        f'{groups_block}'
        f'{missing_block}'
        f'</div></section>'
    )
