"""نمودارهای PNG حرفه‌ای برای مقالات تحلیل بازار — فقط با Pillow."""
from __future__ import annotations

from typing import Any

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

from blog.services.market_article_assets import (
    _draw_text,
    _font,
    _prepare_persian_draw,
    _to_content_file,
)

CHART_W = 1400
CHART_H_MIN = 780
_PAD = 48
_INNER_L = 72
_INNER_R = CHART_W - 72
_HEADER_BOTTOM = 168

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


def _measure_text(text: str, font) -> tuple[int, int]:
    """عرض/ارتفاع واقعی متن بعد از آماده‌سازی فارسی."""
    prepared, _kwargs = _prepare_persian_draw(str(text or ''))
    if not prepared:
        return 0, 0
    try:
        bbox = font.getbbox(prepared)
        return max(0, bbox[2] - bbox[0]), max(0, bbox[3] - bbox[1])
    except Exception:
        return len(prepared) * max(8, getattr(font, 'size', 16) // 2), getattr(font, 'size', 16)


def _blank(title: str, subtitle: str, *, height: int | None = None) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    h = max(CHART_H_MIN, int(height or CHART_H_MIN))
    img = Image.new('RGB', (CHART_W, h), '#0b1220')
    overlay = Image.new('RGBA', (CHART_W, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-120, -160, 520, 420), fill=(13, 148, 136, 40))
    od.ellipse((CHART_W - 480, h - 360, CHART_W + 80, h + 120), fill=(14, 165, 233, 28))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (_PAD, _PAD, CHART_W - _PAD, h - _PAD),
        radius=28,
        fill=(15, 23, 42),
        outline=(51, 65, 85),
        width=2,
    )
    _draw_text(draw, (_INNER_L, 72), title, fill='#f8fafc', font=_font(34, 'bold'))
    _draw_text(draw, (_INNER_L, 118), subtitle, fill='#94a3b8', font=_font(20, 'medium'))
    return img, draw, h


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


def _label_column_width(labels: list[str], font, *, pad: int = 28, minimum: int = 160, maximum: int = 360) -> int:
    widest = max((_measure_text(lbl, font)[0] for lbl in labels), default=0)
    return max(minimum, min(maximum, widest + pad))


def _chart_height_for_rows(n: int, row_h: int, *, top: int = _HEADER_BOTTOM, bottom_pad: int = 72) -> int:
    return max(CHART_H_MIN, top + n * row_h + bottom_pad)


def _draw_hbar_rows(
    draw: ImageDraw.ImageDraw,
    rows: list[tuple[str, float, str]],
    *,
    top: int,
    row_h: int,
    bar_h: int,
    label_w: int,
    track: bool = False,
    value_suffix: str = '',
) -> None:
    """
    چیدمان بدون هم‌پوشانی:
    [برچسب در ستون چپ] [میله] [مقدار در ستون راست]
    """
    label_font = _font(20, 'semibold')
    value_font = _font(20, 'bold')
    vals = [r[1] for r in rows]
    vmax = max(vals) if vals else 1.0
    if vmax <= 0:
        vmax = 1.0

    value_texts = [f'{r[2]}{value_suffix}' for r in rows]
    value_col_w = max(72, max((_measure_text(t, value_font)[0] for t in value_texts), default=48) + 16)
    bar_left = _INNER_L + label_w + 16
    bar_right = _INNER_R - value_col_w - 12
    span = max(40, bar_right - bar_left)

    for i, (label, num, fmt) in enumerate(rows):
        y0 = top + i * row_h
        cy = y0 + row_h / 2
        bar_y0 = cy - bar_h / 2
        bar_y1 = cy + bar_h / 2
        width = max(18.0, (float(num) / vmax) * span)
        color = _PALETTE[i % len(_PALETTE)]

        if track:
            draw.rounded_rectangle(
                (bar_left, bar_y0, bar_right, bar_y1),
                radius=12,
                fill=(30, 41, 59),
            )
        draw.rounded_rectangle(
            (bar_left, bar_y0, bar_left + width, bar_y1),
            radius=12,
            fill=color,
        )
        _draw_text(
            draw,
            (_INNER_L + label_w, cy),
            label,
            fill='#e2e8f0',
            font=label_font,
            anchor='rm',
        )
        _draw_text(
            draw,
            (_INNER_R, cy),
            f'{fmt}{value_suffix}',
            fill='#f8fafc',
            font=value_font,
            anchor='rm',
        )


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

    row_h, bar_h = 92, 52
    label_w = _label_column_width([r[0] for r in rows], _font(20, 'semibold'))
    img, draw, _h = _blank(
        title,
        f'{place} · توزیع چارک‌ها و دهک‌ها',
        height=_chart_height_for_rows(len(rows), row_h),
    )
    _draw_hbar_rows(draw, rows, top=_HEADER_BOTTOM, row_h=row_h, bar_h=bar_h, label_w=label_w)
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
        raw_num = _parse_num(share if share is not None else count)
        if raw_num is not None and share is not None and raw_num <= 100:
            fmt = f'{val:.0f}٪'
        else:
            fmt = str(share if share is not None else count)
        rows.append((str(label), val, fmt))
    if len(rows) < 2:
        return None

    row_h, bar_h = 78, 36
    label_w = _label_column_width([r[0] for r in rows], _font(20, 'semibold'), maximum=420)
    img, draw, _h = _blank(
        'سهم بازه‌های متراژ',
        f'{place} · عمق عرضه در هر باند متراژ',
        height=_chart_height_for_rows(len(rows), row_h),
    )
    _draw_hbar_rows(
        draw,
        rows,
        top=_HEADER_BOTTOM,
        row_h=row_h,
        bar_h=bar_h,
        label_w=label_w,
        track=True,
    )
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

    img, draw, h = _blank('عمق بازار نسبت به عرف', f'{place} · سهم فایل‌های زیر/نزدیک/بالای عرف')
    cx, cy, r = CHART_W // 2 - 160, h // 2 + 28, 170
    total = sum(p[1] for p in parts) or 1
    start = -90.0
    for _, val, color in parts:
        sweep = 360.0 * (val / total)
        draw.pieslice((cx - r, cy - r, cx + r, cy + r), start=start, end=start + sweep, fill=color)
        start += sweep
    draw.ellipse((cx - 88, cy - 88, cx + 88, cy + 88), fill=(15, 23, 42))
    _draw_text(draw, (cx, cy - 14), 'عمق', fill='#94a3b8', font=_font(20, 'medium'), anchor='mm')
    _draw_text(draw, (cx, cy + 18), 'بازار', fill='#f8fafc', font=_font(28, 'bold'), anchor='mm')

    legend_x = cx + r + 56
    legend_y = cy - (len(parts) * 72) / 2
    label_font = _font(22, 'semibold')
    value_font = _font(18, 'medium')
    for i, (label, val, color) in enumerate(parts):
        y = legend_y + i * 72
        draw.rounded_rectangle((legend_x, y + 8, legend_x + 28, y + 36), radius=8, fill=color)
        _draw_text(draw, (legend_x + 42, y + 8), label, fill='#e2e8f0', font=label_font)
        _draw_text(draw, (legend_x + 42, y + 40), f'{val:.0f}٪', fill='#94a3b8', font=value_font)
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
            rows.append((str(g.get('label') or g.get('key') or 'گروه'), float(count), str(count)))
    if len(rows) < 2:
        return None

    row_h, bar_h = 86, 46
    label_w = _label_column_width([r[0] for r in rows], _font(20, 'semibold'), maximum=420)
    img, draw, _h = _blank(
        'تعداد امکانات به‌تفکیک گروه',
        f'{place} · شعاع {access.get("radius_label") or "منطقه"}',
        height=_chart_height_for_rows(len(rows), row_h),
    )
    _draw_hbar_rows(draw, rows, top=_HEADER_BOTTOM, row_h=row_h, bar_h=bar_h, label_w=label_w)
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
            rows.append((str(label), float(pct), f'{pct:.0f}٪'))
    if len(rows) < 2:
        return None

    row_h, bar_h = 78, 36
    label_w = _label_column_width([r[0] for r in rows], _font(20, 'semibold'), maximum=360)
    img, draw, _h = _blank(
        'پوشش امکانات داخل فایل‌ها',
        f'{place} · درصد فایل‌هایی که هر امکان را دارند',
        height=_chart_height_for_rows(len(rows), row_h),
    )
    _draw_hbar_rows(
        draw,
        rows,
        top=_HEADER_BOTTOM,
        row_h=row_h,
        bar_h=bar_h,
        label_w=label_w,
        track=True,
    )
    return img
