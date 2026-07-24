"""رندر تصویر شاخص OG برای مقالات سیستماتیک."""
from __future__ import annotations

import io
import math
from typing import Any

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


OG_WIDTH = 1200
OG_HEIGHT = 630


def render_featured_image(
    *,
    city: str,
    district: str,
    tx_label: str,
    pps_median_fmt: str,
    trend_fmt: str,
    valid_count: int,
    confidence_score: Any,
    geo_points: list[dict] | None = None,
) -> ContentFile:
    """PNG 1200×630 — heatmap/density در صورت وجود نقطه، وگرنه کارت KPI."""
    if geo_points and len(geo_points) >= 12:
        img = _render_density_map(geo_points, city, district, tx_label, pps_median_fmt, valid_count, confidence_score)
    else:
        img = _render_kpi_card(
            city, district, tx_label, pps_median_fmt, trend_fmt, valid_count, confidence_score,
        )
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    name = f'market-{_safe(city)}-{_safe(district)}.png'
    return ContentFile(buf.read(), name=name)


def _safe(text: str) -> str:
    return ''.join(c if c.isalnum() else '-' for c in (text or 'x'))[:40]


def _font(size: int):
    for path in (
        'C:/Windows/Fonts/tahoma.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_kpi_card(city, district, tx_label, pps, trend, valid_count, confidence) -> Image.Image:
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#0f172a')
    draw = ImageDraw.Draw(img)
    # ambient gradient blocks
    draw.rectangle((0, 0, OG_WIDTH, 180), fill='#134e4a')
    draw.ellipse((-120, 400, 420, 900), fill='#115e59')
    draw.ellipse((800, -80, 1400, 420), fill='#1e293b')

    title_font = _font(42)
    sub_font = _font(26)
    big_font = _font(56)
    small_font = _font(22)

    draw.text((64, 48), 'فایلینگ دیوار', fill='#5eead4', font=sub_font, anchor='lt')
    draw.text((64, 100), f'{district} · {city}', fill='#f8fafc', font=title_font, anchor='lt')
    draw.text((64, 170), f'تحلیل بازار {tx_label}', fill='#94a3b8', font=sub_font, anchor='lt')

    draw.rounded_rectangle((64, 250, 560, 420), radius=24, fill='#1e293b')
    draw.text((96, 280), 'قیمت میانه هر متر', fill='#94a3b8', font=small_font, anchor='lt')
    draw.text((96, 330), str(pps or '—'), fill='#f8fafc', font=big_font, anchor='lt')

    draw.rounded_rectangle((600, 250, 1136, 420), radius=24, fill='#1e293b')
    draw.text((632, 280), 'اعتماد تحلیل', fill='#94a3b8', font=small_font, anchor='lt')
    draw.text((632, 330), str(confidence if confidence is not None else '—'), fill='#5eead4', font=big_font, anchor='lt')

    draw.text((64, 480), f'{valid_count} فایل معتبر', fill='#e2e8f0', font=sub_font, anchor='lt')
    draw.text((64, 540), f'روند: {trend or "—"}', fill='#94a3b8', font=small_font, anchor='lt')
    draw.text((1136, 580), 'divarfiling.ir', fill='#64748b', font=small_font, anchor='rt')
    return img


def _render_density_map(points, city, district, tx_label, pps, valid_count, confidence) -> Image.Image:
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#0b1220')
    draw = ImageDraw.Draw(img, 'RGBA')

    lats = [p['lat'] for p in points]
    lngs = [p['lng'] for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    pad_lat = max((max_lat - min_lat) * 0.08, 0.002)
    pad_lng = max((max_lng - min_lng) * 0.08, 0.002)
    min_lat -= pad_lat
    max_lat += pad_lat
    min_lng -= pad_lng
    max_lng += pad_lng

    map_top, map_bottom = 90, 520
    map_left, map_right = 40, 1160

    # soft grid
    for i in range(8):
        x = map_left + i * (map_right - map_left) / 7
        draw.line((x, map_top, x, map_bottom), fill=(30, 41, 59, 120), width=1)
    for i in range(5):
        y = map_top + i * (map_bottom - map_top) / 4
        draw.line((map_left, y, map_right, y), fill=(30, 41, 59, 120), width=1)

    def project(lat, lng):
        x = map_left + (lng - min_lng) / max(max_lng - min_lng, 1e-9) * (map_right - map_left)
        y = map_bottom - (lat - min_lat) / max(max_lat - min_lat, 1e-9) * (map_bottom - map_top)
        return x, y

    # heat blobs (aggregated — no single-point identity)
    for p in points:
        x, y = project(p['lat'], p['lng'])
        w = float(p.get('w') or 1.0)
        r = 10 + 8 * min(w, 2.5)
        alpha = int(40 + 50 * min(w, 2.0))
        color = (20, 184, 166, alpha)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)

    # overlay header/footer
    draw.rectangle((0, 0, OG_WIDTH, 78), fill=(15, 23, 42, 230))
    draw.rectangle((0, 540, OG_WIDTH, OG_HEIGHT), fill=(15, 23, 42, 235))
    title_font = _font(30)
    small = _font(20)
    draw.text((40, 24), f'نقشه تراکم · {district} · {city}', fill='#f8fafc', font=title_font, anchor='lt')
    draw.text((1160, 28), 'فایلینگ دیوار', fill='#5eead4', font=small, anchor='rt')
    draw.text((40, 565), f'{tx_label} · میانه هر متر {pps} · {valid_count} فایل · اعتماد {confidence}', fill='#cbd5e1', font=small, anchor='lt')
    draw.text((1160, 590), 'نمایش تجمیعی — بدون موقعیت دقیق آگهی', fill='#64748b', font=small, anchor='rt')
    return img.convert('RGB')
