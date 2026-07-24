"""رندر تصویر شاخص و نقشه‌های مقاله — زوم نزدیک، تایل کامل، هیت‌مپ‌های متنوع."""
from __future__ import annotations

import io
import logging
import math
import random
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

TILE_STREET_TMPL = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'
TILE_SAT_TMPL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
STREET_SUBS = 'abcd'


def render_featured_image(
    *,
    city: str,
    district: str,
    tx_label: str,
    metric_label: str,
    metric_fmt: str,
    trend_fmt: str,
    valid_count: int,
    confidence_score: Any,
    geo_points: list[dict] | None = None,
) -> ContentFile:
    img = None
    if geo_points and len(geo_points) >= 8:
        img = _compose_map_canvas(
            geo_points,
            width=OG_WIDTH,
            height=OG_HEIGHT,
            style='street',
            overlay='heat',
            header=f'نقشه نزدیک بازار · {district} · {city}',
            footer=f'{tx_label} · {metric_label} {metric_fmt} · {valid_count} فایل · اعتماد {confidence_score}',
            brand=True,
            tight=True,
        )
    if img is None:
        img = _render_kpi_card(
            city, district, tx_label, metric_label, metric_fmt, trend_fmt, valid_count, confidence_score,
        )
    return _to_content_file(img, f'market-og-{_safe(city)}-{_safe(district)}.png')


def render_article_maps(
    *,
    city: str,
    district: str,
    tx_label: str,
    metric_label: str,
    metric_fmt: str,
    valid_count: int,
    confidence_score: Any,
    geo_points: list[dict] | None = None,
) -> dict[str, ContentFile]:
    """نقشه‌های متنوع بدنه مقاله."""
    out: dict[str, ContentFile] = {}
    if not geo_points or len(geo_points) < 8:
        return out

    specs = [
        (
            'street_heat', 'street', 'heat',
            f'تراکم فایل‌ها · نقشه شهری نزدیک · {district} {city}',
            f'{tx_label} · هیت‌مپ تراکم · {valid_count} فایل',
        ),
        (
            'street_grid', 'street', 'grid',
            f'شبکه تراکم محله · {district} {city}',
            'هر خانه شبکه = تجمیع چند فایل نزدیک هم',
        ),
        (
            'street_value', 'street', 'value',
            f'سطح {metric_label} · نقشه شهری · {district} {city}',
            f'{metric_label}: {metric_fmt} · رنگ گرم‌تر = بالاتر',
        ),
        (
            'satellite_heat', 'satellite', 'heat',
            f'تراکم روی تصویر ماهواره‌ای · {district} {city}',
            'لایه هیت‌مپ روی ماهواره — بدون موقعیت دقیق آگهی',
        ),
        (
            'satellite_value', 'satellite', 'value',
            f'سطح قیمت/رهن روی ماهواره · {district} {city}',
            f'{metric_label}: {metric_fmt}',
        ),
        (
            'street_dots', 'street', 'dots',
            f'پراکنش تجمیعی فایل‌ها · {district} {city}',
            'نقاط درشت = سلول‌های پرتراکم‌تر',
        ),
    ]
    for key, style, overlay, header, footer in specs:
        img = _compose_map_canvas(
            geo_points,
            width=ARTICLE_MAP_W,
            height=ARTICLE_MAP_H,
            style=style,
            overlay=overlay,
            header=header,
            footer=footer,
            brand=True,
            tight=True,
        )
        if img:
            out[key] = _to_content_file(img, f'market-{key}-{_safe(city)}-{_safe(district)}.png')
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


def _percentile_bbox(points: list[dict], lo: float = 0.08, hi: float = 0.92) -> tuple[float, float, float, float]:
    """bbox بدون نقاط پرت — زوم نزدیک‌تر و دقیق‌تر."""
    lats = sorted(float(p['lat']) for p in points)
    lngs = sorted(float(p['lng']) for p in points)
    n = len(lats)
    i0 = max(0, int(n * lo))
    i1 = min(n - 1, int(n * hi))
    min_lat, max_lat = lats[i0], lats[i1]
    min_lng, max_lng = lngs[i0], lngs[i1]
    if max_lat - min_lat < 0.0015:
        mid = (max_lat + min_lat) / 2
        min_lat, max_lat = mid - 0.0012, mid + 0.0012
    if max_lng - min_lng < 0.0015:
        mid = (max_lng + min_lng) / 2
        min_lng, max_lng = mid - 0.0012, mid + 0.0012
    return min_lat, max_lat, min_lng, max_lng


def _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w: int, map_h: int, *, tight: bool) -> int:
    """نزدیک‌ترین زومی که bbox هنوز در کادر جا شود."""
    fill = 0.78 if tight else 0.90
    best = 13
    for z in range(17, 11, -1):
        x0, y0 = _latlon_to_world_px(max_lat, min_lng, z)
        x1, y1 = _latlon_to_world_px(min_lat, max_lng, z)
        bw, bh = abs(x1 - x0), abs(y1 - y0)
        if bw <= map_w * fill and bh <= map_h * fill:
            return z
        best = z
    return best


def _fetch_tile(url: str, *, retries: int = 3) -> Image.Image | None:
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            return Image.open(io.BytesIO(data)).convert('RGB')
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            last_err = exc
            continue
    logger.debug('tile fetch failed %s: %s', url, last_err)
    return None


def _tile_url(style: str, z: int, x: int, y: int) -> str:
    if style == 'satellite':
        return TILE_SAT_TMPL.format(z=z, y=y, x=x)
    sub = random.choice(list(STREET_SUBS))
    return TILE_STREET_TMPL.format(s=sub, z=z, x=x, y=y)


def _build_basemap(
    *,
    style: str,
    zoom: int,
    min_tx: int,
    max_tx: int,
    min_ty: int,
    max_ty: int,
) -> Image.Image | None:
    cols = max_tx - min_tx + 1
    rows = max_ty - min_ty + 1
    total = cols * rows
    if total > 64 or total < 1:
        return None

    canvas = Image.new('RGB', (cols * TILE_SIZE, rows * TILE_SIZE), '#cfd8e3')
    jobs = [
        (tx, ty, _tile_url(style, zoom, tx, ty))
        for ty in range(min_ty, max_ty + 1)
        for tx in range(min_tx, max_tx + 1)
    ]

    ok = 0
    failed: list[tuple[int, int]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch_tile, url): (tx, ty) for tx, ty, url in jobs}
        for fut in as_completed(futures):
            tx, ty = futures[fut]
            tile = fut.result()
            if tile is None:
                failed.append((tx, ty))
                continue
            ok += 1
            canvas.paste(tile, ((tx - min_tx) * TILE_SIZE, (ty - min_ty) * TILE_SIZE))

    # retry failed once more
    if failed:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(_fetch_tile, _tile_url(style, zoom, tx, ty), retries=4): (tx, ty)
                for tx, ty in failed
            }
            for fut in as_completed(futures):
                tx, ty = futures[fut]
                tile = fut.result()
                if tile is None:
                    continue
                ok += 1
                canvas.paste(tile, ((tx - min_tx) * TILE_SIZE, (ty - min_ty) * TILE_SIZE))

    if ok < max(1, int(total * 0.85)):
        logger.warning('basemap incomplete: %s/%s tiles', ok, total)
        return None
    return canvas


def _aggregate_cells(points: list[dict], bins: int = 36) -> list[dict]:
    lats = [float(p['lat']) for p in points]
    lngs = [float(p['lng']) for p in points]
    min_lat, max_lat, min_lng, max_lng = _percentile_bbox(points, 0.02, 0.98)
    if max_lat == min_lat:
        max_lat += 0.001
    if max_lng == min_lng:
        max_lng += 0.001

    cells: dict[tuple[int, int], dict] = {}
    for p in points:
        lat = float(p['lat'])
        lng = float(p['lng'])
        if not (min_lat <= lat <= max_lat and min_lng <= lng <= max_lng):
            continue
        gx = int((lng - min_lng) / (max_lng - min_lng) * (bins - 1))
        gy = int((lat - min_lat) / (max_lat - min_lat) * (bins - 1))
        key = (max(0, min(bins - 1, gx)), max(0, min(bins - 1, gy)))
        cell = cells.setdefault(key, {'n': 0, 'w': 0.0, 'value': 0.0, 'lat': 0.0, 'lng': 0.0})
        cell['n'] += 1
        cell['w'] += float(p.get('w') or 1.0)
        cell['value'] += float(p.get('value') or p.get('pps') or 0.0)
        cell['lat'] += lat
        cell['lng'] += lng

    out = []
    for (gx, gy), cell in cells.items():
        n = max(cell['n'], 1)
        out.append({
            'gx': gx, 'gy': gy, 'bins': bins,
            'lat': cell['lat'] / n,
            'lng': cell['lng'] / n,
            'n': n,
            'w': cell['w'] / n,
            'value': cell['value'] / n if cell['value'] else 0.0,
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
    tight: bool = True,
) -> Image.Image | None:
    from django.conf import settings
    if getattr(settings, 'MARKET_ARTICLE_SKIP_MAP_TILES', False):
        return None

    header_h, footer_h = 72, 72
    map_h = height - header_h - footer_h
    map_w = width
    if map_h < 200:
        return None

    min_lat, max_lat, min_lng, max_lng = _percentile_bbox(points)
    pad_lat = max((max_lat - min_lat) * (0.05 if tight else 0.1), 0.0008)
    pad_lng = max((max_lng - min_lng) * (0.05 if tight else 0.1), 0.0008)
    min_lat -= pad_lat
    max_lat += pad_lat
    min_lng -= pad_lng
    max_lng += pad_lng

    zoom = _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w, map_h, tight=tight)
    wx0, wy0 = _latlon_to_world_px(max_lat, min_lng, zoom)
    wx1, wy1 = _latlon_to_world_px(min_lat, max_lng, zoom)
    center_x = (wx0 + wx1) / 2
    center_y = (wy0 + wy1) / 2
    # اگر bbox خیلی کوچک است، کمی زوم مفهومی با محدود کردن center کافی است
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

    crop_x = int(left - min_tx * TILE_SIZE)
    crop_y = int(top - min_ty * TILE_SIZE)
    view = Image.new('RGB', (map_w, map_h), '#cfd8e3')
    view.paste(basemap, (-crop_x, -crop_y))

    cells = _aggregate_cells(points)
    heat = Image.new('RGBA', (map_w, map_h), (0, 0, 0, 0))
    draw_heat = ImageDraw.Draw(heat)
    values = [c['value'] for c in cells if c.get('value')]
    v_lo = min(values) if values else 0
    v_hi = max(values) if values else 1
    if v_hi <= v_lo:
        v_hi = v_lo + 1

    def project(lat, lng):
        wx, wy = _latlon_to_world_px(lat, lng, zoom)
        return wx - left, wy - top

    if overlay == 'grid':
        # draw cell rectangles from grid indices using projected centers
        for c in cells:
            x, y = project(c['lat'], c['lng'])
            if not (0 <= x < map_w and 0 <= y < map_h):
                continue
            intensity = min(1.0, 0.25 + 0.2 * math.log1p(c['n']))
            half = 18 + min(22, 4 * math.sqrt(c['n']))
            color = (15, 118, 110, int(40 + 130 * intensity))
            draw_heat.rectangle((x - half, y - half, x + half, y + half), fill=color)
    elif overlay == 'value':
        for c in cells:
            x, y = project(c['lat'], c['lng'])
            if not (0 <= x < map_w and 0 <= y < map_h):
                continue
            t = (c['value'] - v_lo) / (v_hi - v_lo) if c.get('value') else 0.4
            intensity = min(1.0, 0.35 + 0.18 * math.log1p(c['n']))
            r = 16 + min(26, 5 * math.sqrt(c['n']))
            color = _value_color(t, alpha=int(70 + 120 * intensity))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=color)
    elif overlay == 'dots':
        for c in cells:
            x, y = project(c['lat'], c['lng'])
            if not (0 <= x < map_w and 0 <= y < map_h):
                continue
            r = 6 + min(18, 3.5 * math.sqrt(c['n']))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=(13, 148, 136, 200))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 160))
    else:  # heat
        for c in cells:
            x, y = project(c['lat'], c['lng'])
            if not (0 <= x < map_w and 0 <= y < map_h):
                continue
            intensity = min(1.0, 0.35 + 0.2 * math.log1p(c['n']))
            r = 18 + min(34, 7 * math.sqrt(c['n']))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=(20, 184, 166, int(55 + 120 * intensity)))

    blur = 4 if overlay in ('grid', 'dots') else 10
    heat = heat.filter(ImageFilter.GaussianBlur(radius=blur))
    view = Image.alpha_composite(view.convert('RGBA'), heat).convert('RGB')

    frame = Image.new('RGB', (width, height), '#0f172a')
    frame.paste(view, (0, header_h))
    draw = ImageDraw.Draw(frame)
    title_font = _font(26 if width >= 1100 else 20)
    small = _font(17)
    draw.rectangle((0, 0, width, header_h), fill='#0f172a')
    draw.rectangle((0, height - footer_h, width, height), fill='#0f172a')
    draw.text((32, 20), header, fill='#f8fafc', font=title_font, anchor='lt')
    if brand:
        draw.text((width - 32, 24), 'فایلینگ دیوار', fill='#5eead4', font=small, anchor='rt')
    draw.text((32, height - footer_h + 16), footer, fill='#cbd5e1', font=small, anchor='lt')
    draw.text((width - 32, height - 26), f'زوم {zoom} · تجمیعی · OSM/Esri', fill='#64748b', font=small, anchor='rb')
    if overlay == 'value':
        _draw_value_legend(draw, width - 210, header_h + 12, small)
    return frame


def _value_color(t: float, *, alpha: int) -> tuple[int, int, int, int]:
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


def _draw_value_legend(draw: ImageDraw.ImageDraw, x: int, y: int, font) -> None:
    draw.rounded_rectangle((x, y, x + 180, y + 64), radius=10, fill='#0f172a')
    draw.text((x + 12, y + 6), 'سطح ارزش', fill='#e2e8f0', font=font, anchor='lt')
    for i, col in enumerate(['#3b82f6', '#14b8a6', '#f59e0b', '#ef4444']):
        bx = x + 12 + i * 40
        draw.rectangle((bx, y + 32, bx + 32, y + 46), fill=col)
    draw.text((x + 12, y + 48), 'پایین', fill='#94a3b8', font=font, anchor='lt')
    draw.text((x + 168, y + 48), 'بالا', fill='#94a3b8', font=font, anchor='rt')


def _render_kpi_card(city, district, tx_label, metric_label, metric_fmt, trend, valid_count, confidence) -> Image.Image:
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#0f172a')
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, OG_WIDTH, 180), fill='#134e4a')
    title_font = _font(40)
    sub_font = _font(24)
    big_font = _font(44)
    small_font = _font(20)
    draw.text((64, 48), 'فایلینگ دیوار', fill='#5eead4', font=sub_font, anchor='lt')
    draw.text((64, 100), f'{district} · {city}', fill='#f8fafc', font=title_font, anchor='lt')
    draw.text((64, 165), f'تحلیل داده‌محور بازار {tx_label}', fill='#94a3b8', font=sub_font, anchor='lt')
    draw.rounded_rectangle((64, 240, 1136, 420), radius=24, fill='#1e293b')
    draw.text((96, 270), metric_label, fill='#94a3b8', font=small_font, anchor='lt')
    draw.text((96, 320), str(metric_fmt or '—'), fill='#f8fafc', font=big_font, anchor='lt')
    draw.text((64, 470), f'{valid_count} فایل معتبر · اعتماد {confidence}', fill='#e2e8f0', font=sub_font, anchor='lt')
    draw.text((64, 530), f'روند: {trend or "—"}', fill='#94a3b8', font=small_font, anchor='lt')
    return img
