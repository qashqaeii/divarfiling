"""رندر تصویر شاخص و نقشه‌های مقاله — با basemap شهری/ماهواره‌ای واقعی."""
from __future__ import annotations

import io
import logging
import math
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

OG_WIDTH = 1200
OG_HEIGHT = 630
ARTICLE_MAP_W = 1200
ARTICLE_MAP_H = 720
TILE_SIZE = 256
USER_AGENT = 'DivarFilingMarketArticle/1.0 (https://divarfiling.ir; market-report)'

# CARTO Voyager — نقشه شهری واضح (همان basemap میزکار)
TILE_STREET = 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'
# Esri World Imagery — ماهواره‌ای
TILE_SAT = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'


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
    """PNG 1200×630 — نقشه شهری واقعی + هیت‌مپ تجمیعی، یا کارت KPI."""
    img = None
    if geo_points and len(geo_points) >= 8:
        img = _compose_map_canvas(
            geo_points,
            width=OG_WIDTH,
            height=OG_HEIGHT,
            style='street',
            overlay='heat',
            header=f'نقشه بازار · {district} · {city}',
            footer=(
                f'{tx_label} · میانه هر متر {pps_median_fmt} · '
                f'{valid_count} فایل · اعتماد {confidence_score}'
            ),
            brand=True,
        )
    if img is None:
        img = _render_kpi_card(
            city, district, tx_label, pps_median_fmt, trend_fmt, valid_count, confidence_score,
        )
    return _to_content_file(img, f'market-og-{_safe(city)}-{_safe(district)}.png')


def render_article_maps(
    *,
    city: str,
    district: str,
    tx_label: str,
    pps_median_fmt: str,
    valid_count: int,
    confidence_score: Any,
    geo_points: list[dict] | None = None,
) -> dict[str, ContentFile]:
    """نقشه‌های تکمیلی بدنه مقاله: شهری+تراکم، ماهواره، سطح قیمت."""
    out: dict[str, ContentFile] = {}
    if not geo_points or len(geo_points) < 8:
        return out

    street = _compose_map_canvas(
        geo_points,
        width=ARTICLE_MAP_W,
        height=ARTICLE_MAP_H,
        style='street',
        overlay='heat',
        header=f'تراکم فایل‌ها روی نقشه شهری · {district} {city}',
        footer=f'{tx_label} · {valid_count} فایل معتبر · نمایش شبکه‌ای و تجمیعی',
        brand=True,
    )
    if street:
        out['street_heat'] = _to_content_file(
            street, f'market-street-{_safe(city)}-{_safe(district)}.png',
        )

    sat = _compose_map_canvas(
        geo_points,
        width=ARTICLE_MAP_W,
        height=ARTICLE_MAP_H,
        style='satellite',
        overlay='heat',
        header=f'نمای ماهواره‌ای منطقه · {district} {city}',
        footer='لایه تراکم روی تصویر ماهواره‌ای — بدون نشان‌دادن موقعیت دقیق آگهی',
        brand=True,
    )
    if sat:
        out['satellite'] = _to_content_file(
            sat, f'market-sat-{_safe(city)}-{_safe(district)}.png',
        )

    price = _compose_map_canvas(
        geo_points,
        width=ARTICLE_MAP_W,
        height=ARTICLE_MAP_H,
        style='street',
        overlay='price',
        header=f'سطح قیمت هر متر · {district} {city}',
        footer=f'میانه بازار {pps_median_fmt} · رنگ گرم‌تر = گران‌تر (شبکه تجمیعی)',
        brand=True,
    )
    if price:
        out['price'] = _to_content_file(
            price, f'market-price-{_safe(city)}-{_safe(district)}.png',
        )
    return out


def _to_content_file(img: Image.Image, name: str) -> ContentFile:
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
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


def _latlon_to_world_px(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat = max(min(lat, 85.05112878), -85.05112878)
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE
    return x, y


def _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w: int, map_h: int) -> int:
    for z in range(16, 10, -1):
        x0, y0 = _latlon_to_world_px(max_lat, min_lng, z)
        x1, y1 = _latlon_to_world_px(min_lat, max_lng, z)
        if abs(x1 - x0) <= map_w * 0.92 and abs(y1 - y0) <= map_h * 0.92:
            return z
    return 12


def _fetch_tile(url: str) -> Image.Image | None:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert('RGB')
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        logger.debug('tile fetch failed %s: %s', url, exc)
        return None


def _build_basemap(
    *,
    style: str,
    zoom: int,
    min_tx: int,
    max_tx: int,
    min_ty: int,
    max_ty: int,
) -> Image.Image | None:
    template = TILE_STREET if style == 'street' else TILE_SAT
    cols = max_tx - min_tx + 1
    rows = max_ty - min_ty + 1
    if cols * rows > 80:
        return None

    canvas = Image.new('RGB', (cols * TILE_SIZE, rows * TILE_SIZE), '#dce3ea')
    jobs = []
    for ty in range(min_ty, max_ty + 1):
        for tx in range(min_tx, max_tx + 1):
            url = template.format(z=zoom, x=tx, y=ty)
            jobs.append((tx, ty, url))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_tile, url): (tx, ty) for tx, ty, url in jobs}
        ok = 0
        for fut in as_completed(futures):
            tx, ty = futures[fut]
            tile = fut.result()
            if tile is None:
                continue
            ok += 1
            px = (tx - min_tx) * TILE_SIZE
            py = (ty - min_ty) * TILE_SIZE
            canvas.paste(tile, (px, py))
    if ok < max(1, len(jobs) // 3):
        return None
    return canvas


def _aggregate_cells(points: list[dict], zoom: int, bins: int = 28) -> list[dict]:
    """شبکه تجمیعی — هیچ نقطهٔ تکی آگهی روی نقشه نمی‌رود."""
    lats = [float(p['lat']) for p in points]
    lngs = [float(p['lng']) for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    if max_lat == min_lat:
        max_lat += 0.001
    if max_lng == min_lng:
        max_lng += 0.001

    cells: dict[tuple[int, int], dict] = {}
    for p in points:
        lat = float(p['lat'])
        lng = float(p['lng'])
        gx = int((lng - min_lng) / (max_lng - min_lng) * (bins - 1))
        gy = int((lat - min_lat) / (max_lat - min_lat) * (bins - 1))
        key = (gx, gy)
        cell = cells.setdefault(key, {'n': 0, 'w': 0.0, 'pps': 0.0, 'lat': 0.0, 'lng': 0.0})
        cell['n'] += 1
        cell['w'] += float(p.get('w') or 1.0)
        cell['pps'] += float(p.get('pps') or 0.0)
        cell['lat'] += lat
        cell['lng'] += lng

    out = []
    for cell in cells.values():
        n = max(cell['n'], 1)
        out.append({
            'lat': cell['lat'] / n,
            'lng': cell['lng'] / n,
            'n': n,
            'w': cell['w'] / n,
            'pps': cell['pps'] / n if cell['pps'] else 0.0,
        })
    return out


def _compose_map_canvas(
    points: list[dict],
    *,
    width: int,
    height: int,
    style: str,
    overlay: str,
    header: str,
    footer: str,
    brand: bool,
) -> Image.Image | None:
    from django.conf import settings
    if getattr(settings, 'MARKET_ARTICLE_SKIP_MAP_TILES', False):
        return None
    header_h = 78
    footer_h = 78
    map_h = height - header_h - footer_h
    map_w = width
    if map_h < 200:
        return None

    lats = [float(p['lat']) for p in points]
    lngs = [float(p['lng']) for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    pad_lat = max((max_lat - min_lat) * 0.12, 0.003)
    pad_lng = max((max_lng - min_lng) * 0.12, 0.003)
    min_lat -= pad_lat
    max_lat += pad_lat
    min_lng -= pad_lng
    max_lng += pad_lng

    zoom = _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w, map_h)
    wx0, wy0 = _latlon_to_world_px(max_lat, min_lng, zoom)
    wx1, wy1 = _latlon_to_world_px(min_lat, max_lng, zoom)
    center_x = (wx0 + wx1) / 2
    center_y = (wy0 + wy1) / 2
    left = center_x - map_w / 2
    top = center_y - map_h / 2

    min_tx = max(0, int(math.floor(left / TILE_SIZE)))
    max_tx = int(math.floor((left + map_w - 1) / TILE_SIZE))
    min_ty = max(0, int(math.floor(top / TILE_SIZE)))
    max_ty = int(math.floor((top + map_h - 1) / TILE_SIZE))

    basemap = _build_basemap(
        style=style, zoom=zoom,
        min_tx=min_tx, max_tx=max_tx, min_ty=min_ty, max_ty=max_ty,
    )
    if basemap is None:
        return None

    # Crop basemap to exact viewport
    crop_x = int(left - min_tx * TILE_SIZE)
    crop_y = int(top - min_ty * TILE_SIZE)
    view = Image.new('RGB', (map_w, map_h), '#dce3ea')
    view.paste(basemap, (-crop_x, -crop_y))

    cells = _aggregate_cells(points, zoom)
    heat = Image.new('RGBA', (map_w, map_h), (0, 0, 0, 0))
    draw_heat = ImageDraw.Draw(heat)

    pps_vals = [c['pps'] for c in cells if c.get('pps')]
    pps_lo = min(pps_vals) if pps_vals else 0
    pps_hi = max(pps_vals) if pps_vals else 1
    if pps_hi <= pps_lo:
        pps_hi = pps_lo + 1

    for c in cells:
        wx, wy = _latlon_to_world_px(c['lat'], c['lng'], zoom)
        x = wx - left
        y = wy - top
        if not (0 <= x < map_w and 0 <= y < map_h):
            continue
        intensity = min(1.0, 0.35 + 0.15 * math.log1p(c['n']))
        r = 14 + min(28, 6 * math.sqrt(c['n']))
        if overlay == 'price' and c.get('pps'):
            t = (c['pps'] - pps_lo) / (pps_hi - pps_lo)
            # blue (cheap) -> teal -> amber -> red (expensive)
            color = _price_color(t, alpha=int(55 + 120 * intensity))
        else:
            color = (20, 184, 166, int(50 + 110 * intensity))
        draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=color)

    heat = heat.filter(ImageFilter.GaussianBlur(radius=8))
    view = Image.alpha_composite(view.convert('RGBA'), heat).convert('RGB')

    # Final frame with header/footer
    frame = Image.new('RGB', (width, height), '#0f172a')
    frame.paste(view, (0, header_h))
    draw = ImageDraw.Draw(frame)
    title_font = _font(28 if width >= 1100 else 22)
    small = _font(18)
    draw.rectangle((0, 0, width, header_h), fill='#0f172a')
    draw.rectangle((0, height - footer_h, width, height), fill='#0f172a')
    draw.text((36, 22), header, fill='#f8fafc', font=title_font, anchor='lt')
    if brand:
        draw.text((width - 36, 26), 'فایلینگ دیوار', fill='#5eead4', font=small, anchor='rt')
    draw.text((36, height - footer_h + 18), footer, fill='#cbd5e1', font=small, anchor='lt')
    draw.text(
        (width - 36, height - 28),
        'نمایش تجمیعی · OSM/Esri',
        fill='#64748b',
        font=small,
        anchor='rb',
    )

    # Legend for price maps
    if overlay == 'price':
        _draw_price_legend(draw, width - 220, header_h + 16, small)

    return frame


def _price_color(t: float, *, alpha: int) -> tuple[int, int, int, int]:
    t = max(0.0, min(1.0, t))
    if t < 0.33:
        u = t / 0.33
        r, g, b = int(59 + u * (20 - 59)), int(130 + u * (184 - 130)), int(246 + u * (166 - 246))
    elif t < 0.66:
        u = (t - 0.33) / 0.33
        r, g, b = int(20 + u * (245 - 20)), int(184 + u * (158 - 184)), int(166 + u * (11 - 166))
    else:
        u = (t - 0.66) / 0.34
        r, g, b = int(245 + u * (239 - 245)), int(158 + u * (68 - 158)), int(11 + u * (68 - 11))
    return (r, g, b, alpha)


def _draw_price_legend(draw: ImageDraw.ImageDraw, x: int, y: int, font) -> None:
    draw.rounded_rectangle((x, y, x + 190, y + 70), radius=10, fill='#0f172a')
    draw.text((x + 12, y + 8), 'سطح قیمت', fill='#e2e8f0', font=font, anchor='lt')
    colors = ['#3b82f6', '#14b8a6', '#f59e0b', '#ef4444']
    for i, col in enumerate(colors):
        bx = x + 12 + i * 42
        draw.rectangle((bx, y + 36, bx + 34, y + 52), fill=col)
    draw.text((x + 12, y + 54), 'ارزان', fill='#94a3b8', font=font, anchor='lt')
    draw.text((x + 178, y + 54), 'گران', fill='#94a3b8', font=font, anchor='rt')


def _render_kpi_card(city, district, tx_label, pps, trend, valid_count, confidence) -> Image.Image:
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#0f172a')
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, OG_WIDTH, 180), fill='#134e4a')
    draw.ellipse((-120, 400, 420, 900), fill='#115e59')
    draw.ellipse((800, -80, 1400, 420), fill='#1e293b')

    title_font = _font(42)
    sub_font = _font(26)
    big_font = _font(48)
    small_font = _font(22)

    draw.text((64, 48), 'فایلینگ دیوار', fill='#5eead4', font=sub_font, anchor='lt')
    draw.text((64, 100), f'{district} · {city}', fill='#f8fafc', font=title_font, anchor='lt')
    draw.text((64, 170), f'تحلیل داده‌محور بازار {tx_label}', fill='#94a3b8', font=sub_font, anchor='lt')

    draw.rounded_rectangle((64, 250, 560, 420), radius=24, fill='#1e293b')
    draw.text((96, 280), 'قیمت میانه هر متر', fill='#94a3b8', font=small_font, anchor='lt')
    draw.text((96, 330), str(pps or '—'), fill='#f8fafc', font=big_font, anchor='lt')

    draw.rounded_rectangle((600, 250, 1136, 420), radius=24, fill='#1e293b')
    draw.text((632, 280), 'اعتماد تحلیل', fill='#94a3b8', font=small_font, anchor='lt')
    draw.text((632, 330), str(confidence if confidence is not None else '—'), fill='#5eead4', font=big_font, anchor='lt')

    draw.text((64, 480), f'{valid_count} فایل معتبر پس از پالایش', fill='#e2e8f0', font=sub_font, anchor='lt')
    draw.text((64, 540), f'روند: {trend or "—"}', fill='#94a3b8', font=small_font, anchor='lt')
    draw.text((1136, 580), 'divarfiling.ir', fill='#64748b', font=small_font, anchor='rt')
    return img
