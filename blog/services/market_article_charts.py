"""نمودارهای PNG حرفه‌ای برای مقالات تحلیل بازار — فقط با Pillow."""
from __future__ import annotations

from typing import Any

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

from blog.services.market_article_assets import _draw_text, _font, _to_content_file

CHART_W = 1400
CHART_H = 780

_PALETTE = (
    (13, 148, 136),
    (14, 165, 233),
    (245, 158, 11),
    (239, 68, 68),
    (139, 92, 246),
    (16, 185, 129),
    (99, 102, 241),
    (236, 72, 153),
)


def render_article_charts(
    *,
    report: dict[str, Any],
    city: str,
    district: str,
    is_rent: bool,
) -> dict[str, ContentFile]:
    out: dict[str, ContentFile] = {}
    place = f'{district} · {city}'

    img = _chart_price_ladder(report, place=place, is_rent=is_rent)
    if img:
        out['chart_price_ladder'] = _to_content_file(img, f'chart-ladder-{_safe(city)}.png')

    img = _chart_area_segments(report, place=place)
    if img:
        out['chart_area_share'] = _to_content_file(img, f'chart-area-{_safe(city)}.png')

    img = _chart_market_depth(report, place=place)
    if img:
        out['chart_market_depth'] = _to_content_file(img, f'chart-depth-{_safe(city)}.png')

    img = _chart_access_groups(report, place=place)
    if img:
        out['chart_access'] = _to_content_file(img, f'chart-access-{_safe(city)}.png')

    img = _chart_amenities(report, place=place)
    if img:
        out['chart_amenities'] = _to_content_file(img, f'chart-amenities-{_safe(city)}.png')

    return out


def _safe(text: str) -> str:
    return ''.join(c if c.isalnum() else '-' for c in (text or 'x'))[:40]


def _blank(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new('RGB', (CHART_W, CHART_H), '#0b1220')
    overlay = Image.new('RGBA', (CHART_W, CHART_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-120, -160, 520, 420), fill=(13, 148, 136, 40))
    od.ellipse((CHART_W - 480, CHART_H - 360, CHART_W + 80, CHART_H + 120), fill=(14, 165, 233, 28))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (48, 48, CHART_W - 48, CHART_H - 48),
        radius=28,
        fill=(15, 23, 42),
        outline=(51, 65, 85),
        width=2,
    )
    _draw_text(draw, (72, 72), title, fill='#f8fafc', font=_font(34, 'bold'))
    _draw_text(draw, (72, 118), subtitle, fill='#94a3b8', font=_font(20, 'medium'))
    return img, draw


def _parse_num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
    text = text.replace(',', '').replace('٬', '').replace(' ', '')
    digits = ''.join(ch if ch.isdigit() or ch in '.-' else '' for ch in text)
    try:
        return float(digits) if digits not in ('', '-', '.', '-.') else None
    except ValueError:
        return None


def _chart_price_ladder(report: dict, *, place: str, is_rent: bool) -> Image.Image | None:
    pa = report.get('price_analysis') or {}
    if is_rent:
        src = pa.get('full_deposit') or pa.get('deposit') or {}
        title = 'نردبان رهن کامل'
    else:
        src = pa.get('price_per_sqm') or pa.get('price') or {}
        title = 'نردبان قیمت هر متر'

    rows = []
    for key, label in (
        ('p10', 'دهک پایین'),
        ('p25', 'چارک اول'),
        ('median', 'میانه'),
        ('p75', 'چارک سوم'),
        ('p90', 'دهک بالا'),
    ):
        fmt = src.get(f'{key}_fmt') or (src.get('median_fmt') if key == 'median' else None)
        num = _parse_num(src.get(key)) or _parse_num(fmt)
        if num is None:
            continue
        rows.append((label, num, fmt or str(int(num))))
    if len(rows) < 3:
        return None

    img, draw = _blank(title, f'{place} · توزیع چارک‌ها و دهک‌ها')
    vals = [r[1] for r in rows]
    vmin, vmax = min(vals), max(vals)
    if vmax <= vmin:
        vmax = vmin + 1
    left = 120
    top, bar_h, gap = 190, 68, 18
    for i, (label, num, fmt) in enumerate(rows):
        y = top + i * (bar_h + gap)
        width = 180 + ((num - vmin) / (vmax - vmin)) * (CHART_W - 440)
        color = _PALETTE[i % len(_PALETTE)]
        draw.rounded_rectangle((left, y, left + width, y + bar_h), radius=14, fill=color)
        _draw_text(draw, (left + 18, y + bar_h / 2), label, fill='#f8fafc', font=_font(22, 'semibold'), anchor='lm')
        _draw_text(draw, (left + width - 18, y + bar_h / 2), str(fmt), fill='#f8fafc', font=_font(22, 'bold'), anchor='rm')
    return img


def _chart_area_segments(report: dict, *, place: str) -> Image.Image | None:
    rows = []
    for seg in (report.get('area_segments') or [])[:8]:
        if not isinstance(seg, dict):
            continue
        label = (
            seg.get('bucket_plain')
            or seg.get('label')
            or seg.get('name')
            or seg.get('bucket')
            or 'بازه'
        )
        share = seg.get('share_pct') or seg.get('pct') or seg.get('percent')
        count = seg.get('count') or seg.get('n')
        val = _parse_num(share)
        if val is None and count is not None:
            val = float(count)
        if val is None:
            continue
        rows.append((str(label), val, share if share is not None else count))
    if len(rows) < 2:
        return None

    img, draw = _blank('سهم بازه‌های متراژ', f'{place} · عمق عرضه در هر باند متراژ')
    total = sum(r[1] for r in rows) or 1
    left, right, top = 120, CHART_W - 120, 200
    for i, (label, val, raw) in enumerate(rows):
        y = top + i * 70
        width = max(24, (val / total) * (right - left))
        color = _PALETTE[i % len(_PALETTE)]
        draw.rounded_rectangle((left, y, right, y + 42), radius=12, fill=(30, 41, 59))
        draw.rounded_rectangle((left, y, left + width, y + 42), radius=12, fill=color)
        _draw_text(draw, (left, y - 22), label, fill='#cbd5e1', font=_font(18, 'medium'))
        raw_num = _parse_num(raw)
        pct = f'{val:.0f}%' if raw_num is not None and raw_num <= 100 else str(raw)
        _draw_text(draw, (right, y + 21), pct, fill='#f8fafc', font=_font(20, 'bold'), anchor='rm')
    return img


def _chart_market_depth(report: dict, *, place: str) -> Image.Image | None:
    depth = report.get('market_depth') or {}
    under = _parse_num(depth.get('under_pct'))
    over = _parse_num(depth.get('over_pct'))
    mid = _parse_num(depth.get('fair_pct') or depth.get('mid_pct'))
    if under is None and over is None:
        return None
    under = under or 0.0
    over = over or 0.0
    if mid is None:
        mid = max(0.0, 100.0 - under - over)
    parts = [p for p in (
        ('زیر عرف', under, (16, 185, 129)),
        ('نزدیک عرف', mid, (14, 165, 233)),
        ('بالای عرف', over, (239, 68, 68)),
    ) if p[1] > 0]
    if not parts:
        return None

    img, draw = _blank('عمق بازار نسبت به عرف', f'{place} · سهم فایل‌های زیر/نزدیک/بالای عرف')
    cx, cy, r = CHART_W // 2 - 80, CHART_H // 2 + 40, 170
    total = sum(p[1] for p in parts) or 1
    start = -90.0
    for _, val, color in parts:
        sweep = 360.0 * (val / total)
        draw.pieslice((cx - r, cy - r, cx + r, cy + r), start=start, end=start + sweep, fill=color)
        start += sweep
    draw.ellipse((cx - 88, cy - 88, cx + 88, cy + 88), fill=(15, 23, 42))
    _draw_text(draw, (cx, cy - 12), 'عمق', fill='#94a3b8', font=_font(20, 'medium'), anchor='mm')
    _draw_text(draw, (cx, cy + 18), 'بازار', fill='#f8fafc', font=_font(28, 'bold'), anchor='mm')
    legend_x, legend_y = cx + r + 70, cy - 90
    for i, (label, val, color) in enumerate(parts):
        y = legend_y + i * 58
        draw.rounded_rectangle((legend_x, y, legend_x + 28, y + 28), radius=8, fill=color)
        _draw_text(draw, (legend_x + 42, y + 4), label, fill='#e2e8f0', font=_font(22, 'semibold'))
        _draw_text(draw, (legend_x + 42, y + 30), f'{val:.0f}٪', fill='#94a3b8', font=_font(18, 'medium'))
    return img


def _chart_access_groups(report: dict, *, place: str) -> Image.Image | None:
    access = report.get('district_access') or {}
    if not access.get('ok'):
        return None
    rows = []
    for g in access.get('groups') or []:
        count = int(g.get('count') or 0)
        if count <= 0:
            count = sum(int(i.get('count') or 0) for i in (g.get('items') or []))
        if count > 0:
            rows.append((g.get('label') or g.get('key') or 'گروه', count))
    if len(rows) < 2:
        return None

    img, draw = _blank('تعداد امکانات به‌تفکیک گروه', f'{place} · شعاع {access.get("radius_label") or "منطقه"}')
    vmax = max(r[1] for r in rows) or 1
    left, top = 120, 200
    for i, (label, count) in enumerate(rows):
        y = top + i * 68
        width = 80 + (count / vmax) * (CHART_W - 280)
        color = _PALETTE[i % len(_PALETTE)]
        draw.rounded_rectangle((left, y, left + width, y + 46), radius=12, fill=color)
        _draw_text(draw, (left + 16, y + 23), str(label), fill='#f8fafc', font=_font(20, 'semibold'), anchor='lm')
        _draw_text(draw, (left + width - 16, y + 23), str(count), fill='#f8fafc', font=_font(22, 'bold'), anchor='rm')
    return img


def _chart_amenities(report: dict, *, place: str) -> Image.Image | None:
    am = report.get('amenities_coverage') or {}
    items: list = []
    if isinstance(am, list):
        items = am
    elif isinstance(am, dict):
        items = am.get('items') or am.get('top') or []
        if not items:
            for k, v in am.items():
                if k in {'summary', 'count', 'items', 'top'}:
                    continue
                if isinstance(v, dict):
                    items.append({
                        'label': k,
                        'pct': v.get('pct') or v.get('coverage_pct') or v.get('share'),
                    })
                elif isinstance(v, (int, float)):
                    items.append({'label': k, 'pct': v})
    rows = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        label = item.get('label') or item.get('name') or item.get('key')
        pct = _parse_num(
            item.get('pct')
            or item.get('coverage')
            or item.get('coverage_pct')
            or item.get('share')
        )
        if label and pct is not None:
            rows.append((str(label), pct))
    if len(rows) < 2:
        return None

    img, draw = _blank('پوشش امکانات داخل فایل‌ها', f'{place} · درصد فایل‌هایی که هر امکان را دارند')
    left, right, top = 120, CHART_W - 120, 200
    for i, (label, pct) in enumerate(rows):
        y = top + i * 60
        width = max(20, min(100.0, pct) / 100.0 * (right - left))
        color = _PALETTE[i % len(_PALETTE)]
        draw.rounded_rectangle((left, y, right, y + 40), radius=10, fill=(30, 41, 59))
        draw.rounded_rectangle((left, y, left + width, y + 40), radius=10, fill=color)
        _draw_text(draw, (left, y - 20), label, fill='#cbd5e1', font=_font(17, 'medium'))
        _draw_text(draw, (right, y + 20), f'{pct:.0f}٪', fill='#f8fafc', font=_font(18, 'bold'), anchor='rm')
    return img
