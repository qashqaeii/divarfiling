"""رندر حرفه‌ای تصویر شاخص و نقشه‌های مقاله — کارتوگرافی خوانا، دقیق و کاربردی."""
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
ARTICLE_MAP_H = 760
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
            title=f'نقشه بازار · {district}',
            subtitle=f'{city} · {tx_label} · تراکم فایل‌ها',
            footer=f'{metric_label}: {metric_fmt} · {valid_count} فایل · اعتماد {confidence_score}',
            place=f'{district} · {city}',
            metric_label=metric_label,
            metric_fmt=metric_fmt,
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
    """نقشه‌های کاربردی بدنه مقاله — هر کدام یک سؤال مشخص را جواب می‌دهد."""
    out: dict[str, ContentFile] = {}
    if not geo_points or len(geo_points) < 8:
        return out

    place = f'{district} · {city}'
    specs = [
        (
            'street_heat', 'street', 'heat',
            f'کجا عرضه بیشتر است؟ · {district}',
            f'هیت‌مپ تراکم فایل · {tx_label} · {valid_count} فایل معتبر',
            'تراکم فایل‌ها روی نقشه شهری',
        ),
        (
            'street_value', 'street', 'value',
            f'کجا گران‌تر / ارزان‌تر است؟ · {district}',
            f'سطح {metric_label} · میانه بازار: {metric_fmt}',
            f'سطح {metric_label}',
        ),
        (
            'street_grid', 'street', 'grid',
            f'شبکه محله در یک نگاه · {district}',
            'هر خانه = تجمیع چند فایل نزدیک · شدت رنگ = تعداد فایل',
            'شبکه تراکم کمی',
        ),
        (
            'street_hotspots', 'street', 'hotspots',
            f'نقاط پرتراکم بازار · {district}',
            '۳ تا ۵ کانون عرضه برای اولویت بازدید و فیلتر فایل',
            'کانون‌های پرتراکم',
        ),
        (
            'satellite_heat', 'satellite', 'heat',
            f'بافت شهری روی ماهواره · {district}',
            'همان لایه تراکم روی تصویر ماهواره‌ای برای درک بافت محله',
            'تراکم روی ماهواره',
        ),
        (
            'satellite_value', 'satellite', 'value',
            f'{metric_label} روی ماهواره · {district}',
            f'رنگ گرم‌تر = {_e_plain(metric_label)} بالاتر · میانه: {metric_fmt}',
            f'سطح {metric_label} روی ماهواره',
        ),
    ]
    for key, style, overlay, title, footer, _purpose in specs:
        img = _compose_map_canvas(
            geo_points,
            width=ARTICLE_MAP_W,
            height=ARTICLE_MAP_H,
            style=style,
            overlay=overlay,
            title=title,
            subtitle=place,
            footer=footer,
            place=place,
            metric_label=metric_label,
            metric_fmt=metric_fmt,
            brand=True,
            tight=True,
        )
        if img:
            out[key] = _to_content_file(img, f'market-{key}-{_safe(city)}-{_safe(district)}.png')
    return out


def _e_plain(text: str) -> str:
    return str(text or '')


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


def _meters_per_pixel(lat: float, zoom: int) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)


def _percentile_bbox(points: list[dict], lo: float = 0.07, hi: float = 0.93) -> tuple[float, float, float, float]:
    lats = sorted(float(p['lat']) for p in points)
    lngs = sorted(float(p['lng']) for p in points)
    n = len(lats)
    i0 = max(0, int(n * lo))
    i1 = min(n - 1, int(n * hi))
    min_lat, max_lat = lats[i0], lats[i1]
    min_lng, max_lng = lngs[i0], lngs[i1]
    if max_lat - min_lat < 0.0012:
        mid = (max_lat + min_lat) / 2
        min_lat, max_lat = mid - 0.001, mid + 0.001
    if max_lng - min_lng < 0.0012:
        mid = (max_lng + min_lng) / 2
        min_lng, max_lng = mid - 0.001, mid + 0.001
    return min_lat, max_lat, min_lng, max_lng


def _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w: int, map_h: int, *, tight: bool) -> int:
    fill = 0.70 if tight else 0.88
    best = 13
    for z in range(18, 11, -1):
        x0, y0 = _latlon_to_world_px(max_lat, min_lng, z)
        x1, y1 = _latlon_to_world_px(min_lat, max_lng, z)
        bw, bh = abs(x1 - x0), abs(y1 - y0)
        if bw <= map_w * fill and bh <= map_h * fill:
            return z
        best = z
    return best


def _fetch_tile(url: str, *, retries: int = 3) -> Image.Image | None:
    last_err = None
    for _ in range(retries):
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
    if total > 72 or total < 1:
        return None

    canvas = Image.new('RGB', (cols * TILE_SIZE, rows * TILE_SIZE), '#d7dee8')
    jobs = [
        (tx, ty, _tile_url(style, zoom, tx, ty))
        for ty in range(min_ty, max_ty + 1)
        for tx in range(min_tx, max_tx + 1)
    ]

    ok = 0
    failed: list[tuple[int, int]] = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(_fetch_tile, url): (tx, ty) for tx, ty, url in jobs}
        for fut in as_completed(futures):
            tx, ty = futures[fut]
            tile = fut.result()
            if tile is None:
                failed.append((tx, ty))
                continue
            ok += 1
            canvas.paste(tile, ((tx - min_tx) * TILE_SIZE, (ty - min_ty) * TILE_SIZE))

    if failed:
        with ThreadPoolExecutor(max_workers=8) as pool:
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

    if ok < max(1, int(total * 0.88)):
        logger.warning('basemap incomplete: %s/%s tiles', ok, total)
        return None
    return canvas


def _adaptive_bins(n_points: int) -> int:
    if n_points >= 400:
        return 28
    if n_points >= 200:
        return 24
    if n_points >= 100:
        return 20
    return 16


def _aggregate_cells(points: list[dict], bins: int | None = None) -> tuple[list[dict], dict]:
    """تجمیع شبکه‌ای + متادیتای bbox برای رسم دقیق خانه‌ها."""
    bins = bins or _adaptive_bins(len(points))
    min_lat, max_lat, min_lng, max_lng = _percentile_bbox(points, 0.03, 0.97)
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
    meta = {
        'bins': bins,
        'min_lat': min_lat, 'max_lat': max_lat,
        'min_lng': min_lng, 'max_lng': max_lng,
    }
    return out, meta


def _cell_corners(cell: dict, meta: dict) -> tuple[float, float, float, float]:
    bins = meta['bins']
    dlat = (meta['max_lat'] - meta['min_lat']) / max(bins - 1, 1)
    dlng = (meta['max_lng'] - meta['min_lng']) / max(bins - 1, 1)
    gx, gy = cell['gx'], cell['gy']
    # cell center is at grid index; expand half-step
    lat0 = meta['min_lat'] + gy * dlat - dlat * 0.45
    lat1 = meta['min_lat'] + gy * dlat + dlat * 0.45
    lng0 = meta['min_lng'] + gx * dlng - dlng * 0.45
    lng1 = meta['min_lng'] + gx * dlng + dlng * 0.45
    return lat0, lat1, lng0, lng1


def _compose_map_canvas(
    points: list[dict],
    *,
    width: int,
    height: int,
    style: str,
    overlay: str,
    title: str,
    subtitle: str,
    footer: str,
    place: str,
    metric_label: str,
    metric_fmt: str,
    brand: bool,
    tight: bool = True,
) -> Image.Image | None:
    from django.conf import settings
    if getattr(settings, 'MARKET_ARTICLE_SKIP_MAP_TILES', False):
        return None

    header_h, footer_h = 78, 78
    map_h = height - header_h - footer_h
    map_w = width
    if map_h < 220:
        return None

    min_lat, max_lat, min_lng, max_lng = _percentile_bbox(points)
    pad_lat = max((max_lat - min_lat) * (0.06 if tight else 0.12), 0.0007)
    pad_lng = max((max_lng - min_lng) * (0.06 if tight else 0.12), 0.0007)
    min_lat -= pad_lat
    max_lat += pad_lat
    min_lng -= pad_lng
    max_lng += pad_lng

    zoom = _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w, map_h, tight=tight)
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

    crop_x = int(left - min_tx * TILE_SIZE)
    crop_y = int(top - min_ty * TILE_SIZE)
    view = Image.new('RGB', (map_w, map_h), '#d7dee8')
    view.paste(basemap, (-crop_x, -crop_y))

    # slight darken for overlay readability on satellite
    if style == 'satellite':
        shade = Image.new('RGBA', (map_w, map_h), (15, 23, 42, 55))
        view = Image.alpha_composite(view.convert('RGBA'), shade).convert('RGB')

    cells, meta = _aggregate_cells(points)
    if not cells:
        return None

    values = [c['value'] for c in cells if c.get('value')]
    counts = [c['n'] for c in cells]
    v_lo = min(values) if values else 0.0
    v_hi = max(values) if values else 1.0
    if v_hi <= v_lo:
        v_hi = v_lo + 1
    n_lo, n_hi = min(counts), max(counts)
    if n_hi <= n_lo:
        n_hi = n_lo + 1

    def project(lat, lng):
        wx, wy = _latlon_to_world_px(lat, lng, zoom)
        return wx - left, wy - top

    heat = Image.new('RGBA', (map_w, map_h), (0, 0, 0, 0))
    draw_heat = ImageDraw.Draw(heat)
    label_font = _font(14)
    tiny_font = _font(12)

    if overlay == 'grid':
        for c in cells:
            lat0, lat1, lng0, lng1 = _cell_corners(c, meta)
            x0, y1p = project(lat0, lng0)
            x1, y0p = project(lat1, lng1)
            xa, xb = sorted((x0, x1))
            ya, yb = sorted((y0p, y1p))
            if xb < 0 or yb < 0 or xa > map_w or ya > map_h:
                continue
            t = (c['n'] - n_lo) / (n_hi - n_lo)
            color = _density_color(t, alpha=int(55 + 140 * t))
            draw_heat.rectangle((xa, ya, xb, yb), fill=color, outline=(255, 255, 255, 70))
            if c['n'] >= max(2, int(n_hi * 0.45)) and (xb - xa) > 28:
                cx, cy = (xa + xb) / 2, (ya + yb) / 2
                draw_heat.text((cx, cy), str(c['n']), fill=(255, 255, 255, 230), font=tiny_font, anchor='mm')

    elif overlay == 'value':
        for c in cells:
            if not c.get('value'):
                continue
            x, y = project(c['lat'], c['lng'])
            if not (-20 <= x < map_w + 20 and -20 <= y < map_h + 20):
                continue
            t = (c['value'] - v_lo) / (v_hi - v_lo)
            r = 14 + min(22, 4.2 * math.sqrt(c['n']))
            color = _value_color(t, alpha=int(90 + 110 * min(1.0, 0.35 + 0.2 * math.log1p(c['n']))))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=color)
            draw_heat.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 90))

    elif overlay == 'hotspots':
        # soft density field first
        for c in cells:
            x, y = project(c['lat'], c['lng'])
            if not (0 <= x < map_w and 0 <= y < map_h):
                continue
            t = (c['n'] - n_lo) / (n_hi - n_lo)
            r = 16 + min(28, 6 * math.sqrt(c['n']))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=_density_color(t * 0.75, alpha=int(40 + 90 * t)))
        heat = heat.filter(ImageFilter.GaussianBlur(radius=8))
        draw_heat = ImageDraw.Draw(heat)
        ranked = sorted(cells, key=lambda c: c['n'], reverse=True)[:5]
        for i, c in enumerate(ranked, start=1):
            x, y = project(c['lat'], c['lng'])
            if not (20 <= x < map_w - 20 and 20 <= y < map_h - 20):
                continue
            r = 18 + min(10, c['n'])
            draw_heat.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 230), width=3)
            draw_heat.ellipse((x - r + 3, y - r + 3, x + r - 3, y + r - 3), outline=(220, 38, 38, 220), width=2)
            badge = f'{i}'
            bx, by = x + r + 6, y - r - 4
            draw_heat.rounded_rectangle((bx, by, bx + 54, by + 26), radius=8, fill=(15, 23, 42, 220))
            draw_heat.text((bx + 27, by + 13), f'#{badge} · {c["n"]}', fill=(248, 250, 252, 255), font=tiny_font, anchor='mm')

    else:  # heat
        for c in cells:
            x, y = project(c['lat'], c['lng'])
            if not (-30 <= x < map_w + 30 and -30 <= y < map_h + 30):
                continue
            t = (c['n'] - n_lo) / (n_hi - n_lo)
            r = 20 + min(36, 7.5 * math.sqrt(c['n']))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=_density_color(t, alpha=int(45 + 130 * t)))

    if overlay in ('heat', 'value'):
        heat = heat.filter(ImageFilter.GaussianBlur(radius=9 if overlay == 'heat' else 6))
    elif overlay == 'grid':
        heat = heat.filter(ImageFilter.GaussianBlur(radius=1))

    view_rgba = Image.alpha_composite(view.convert('RGBA'), heat)
    chrome = Image.new('RGBA', (map_w, map_h), (0, 0, 0, 0))
    draw_chrome = ImageDraw.Draw(chrome)
    _draw_north_arrow(draw_chrome, map_w - 42, 36)
    center_lat = (min_lat + max_lat) / 2
    _draw_scale_bar(draw_chrome, 28, map_h - 36, center_lat, zoom, tiny_font)
    _draw_place_badge(draw_chrome, 28, 24, place, label_font)
    _draw_legend_panel(
        draw_chrome,
        map_w - 208,
        map_h - (118 if overlay == 'value' else 102),
        overlay=overlay,
        metric_label=metric_label,
        metric_fmt=metric_fmt,
        font=tiny_font,
        title_font=label_font,
    )
    view = Image.alpha_composite(view_rgba, chrome).convert('RGB')

    frame = Image.new('RGB', (width, height), '#0b1220')
    frame.paste(view, (0, header_h))
    draw = ImageDraw.Draw(frame)
    title_font = _font(25 if width >= 1100 else 19)
    sub_font = _font(16)
    small = _font(15)

    draw.rectangle((0, 0, width, header_h), fill='#0b1220')
    draw.rectangle((0, height - footer_h, width, height), fill='#0b1220')
    draw.rectangle((0, header_h - 3, width, header_h), fill='#14b8a6')
    draw.text((28, 16), title, fill='#f8fafc', font=title_font, anchor='lt')
    draw.text((28, 48), subtitle, fill='#94a3b8', font=sub_font, anchor='lt')
    if brand:
        draw.text((width - 28, 22), 'فایلینگ دیوار', fill='#5eead4', font=sub_font, anchor='rt')
        draw.text((width - 28, 48), 'تحلیل داده‌محور بازار', fill='#64748b', font=tiny_font, anchor='rt')

    draw.text((28, height - footer_h + 18), footer, fill='#cbd5e1', font=small, anchor='lt')
    draw.text(
        (28, height - 28),
        'نمایش تجمیعی شبکه‌ای · موقعیت تک‌آگهی نشان داده نمی‌شود',
        fill='#64748b',
        font=tiny_font,
        anchor='lt',
    )
    draw.text(
        (width - 28, height - 28),
        f'زوم {zoom} · Carto/Esri',
        fill='#64748b',
        font=tiny_font,
        anchor='rb',
    )
    return frame


def _density_color(t: float, *, alpha: int) -> tuple[int, int, int, int]:
    """کم = زرد کمرنگ → زیاد = قرمز — متمایز از نقشه ارزش."""
    t = max(0.0, min(1.0, t))
    stops = [
        (0.0, (253, 224, 71)),
        (0.35, (251, 146, 60)),
        (0.65, (239, 68, 68)),
        (1.0, (127, 29, 29)),
    ]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            u = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            r = int(c0[0] + u * (c1[0] - c0[0]))
            g = int(c0[1] + u * (c1[1] - c0[1]))
            b = int(c0[2] + u * (c1[2] - c0[2]))
            return (r, g, b, alpha)
    return (*stops[-1][1], alpha)


def _value_color(t: float, *, alpha: int) -> tuple[int, int, int, int]:
    """پایین = آبی → میانه = فیروزه‌ای/کهربایی → بالا = قرمز."""
    t = max(0.0, min(1.0, t))
    stops = [
        (0.0, (59, 130, 246)),
        (0.33, (20, 184, 166)),
        (0.66, (245, 158, 11)),
        (1.0, (239, 68, 68)),
    ]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            u = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            r = int(c0[0] + u * (c1[0] - c0[0]))
            g = int(c0[1] + u * (c1[1] - c0[1]))
            b = int(c0[2] + u * (c1[2] - c0[2]))
            return (r, g, b, alpha)
    return (*stops[-1][1], alpha)


def _draw_north_arrow(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=(15, 23, 42, 200), outline=(255, 255, 255, 180))
    draw.polygon([(x, y - 12), (x - 7, y + 8), (x, y + 3), (x + 7, y + 8)], fill=(248, 250, 252))
    draw.text((x, y + 26), 'N', fill=(15, 23, 42), font=_font(11), anchor='mm')


def _draw_scale_bar(draw: ImageDraw.ImageDraw, x: int, y: int, lat: float, zoom: int, font) -> None:
    mpp = _meters_per_pixel(lat, zoom)
    target_m = 500
    for cand in (100, 200, 250, 500, 1000, 2000, 5000):
        px = cand / max(mpp, 1e-6)
        if 70 <= px <= 180:
            target_m = cand
            break
    else:
        target_m = max(100, int(round(120 * mpp / 100) * 100))
    px = target_m / max(mpp, 1e-6)
    label = f'{target_m} متر' if target_m < 1000 else f'{target_m / 1000:g} کیلومتر'
    draw.rounded_rectangle((x - 8, y - 22, x + px + 12, y + 10), radius=8, fill=(15, 23, 42, 200))
    draw.rectangle((x, y - 2, x + px, y + 2), fill=(248, 250, 252))
    draw.rectangle((x, y - 6, x + 2, y + 6), fill=(248, 250, 252))
    draw.rectangle((x + px - 2, y - 6, x + px, y + 6), fill=(248, 250, 252))
    draw.text((x + px / 2, y - 12), label, fill=(226, 232, 240), font=font, anchor='mm')


def _draw_place_badge(draw: ImageDraw.ImageDraw, x: int, y: int, place: str, font) -> None:
    text = place or 'محله'
    # approximate width
    tw = max(120, min(320, 10 + len(text) * 9))
    draw.rounded_rectangle((x, y, x + tw, y + 32), radius=10, fill=(15, 23, 42, 210))
    draw.rectangle((x, y + 6, x + 4, y + 26), fill=(20, 184, 166))
    draw.text((x + 14, y + 16), text, fill=(248, 250, 252), font=font, anchor='lm')


def _draw_legend_panel(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    *,
    overlay: str,
    metric_label: str,
    metric_fmt: str,
    font,
    title_font,
) -> None:
    w, h = 188, 96 if overlay != 'value' else 110
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=(15, 23, 42, 220))

    if overlay == 'value':
        title = (metric_label or 'سطح ارزش')[:22]
        draw.text((x + 12, y + 10), title, fill='#f8fafc', font=title_font, anchor='lt')
        colors = ['#3b82f6', '#14b8a6', '#f59e0b', '#ef4444']
        for i, col in enumerate(colors):
            bx = x + 12 + i * 40
            draw.rectangle((bx, y + 38, bx + 34, y + 52), fill=col)
        draw.text((x + 12, y + 60), 'پایین', fill='#94a3b8', font=font, anchor='lt')
        draw.text((x + w - 12, y + 60), 'بالا', fill='#94a3b8', font=font, anchor='rt')
        if metric_fmt:
            draw.text((x + 12, y + 82), f'میانه: {metric_fmt}'[:28], fill='#cbd5e1', font=font, anchor='lt')
    elif overlay == 'hotspots':
        draw.text((x + 12, y + 10), 'کانون عرضه', fill='#f8fafc', font=title_font, anchor='lt')
        draw.text((x + 12, y + 40), 'شماره = رتبه تراکم', fill='#cbd5e1', font=font, anchor='lt')
        draw.text((x + 12, y + 62), 'عدد کنار # = تعداد فایل', fill='#94a3b8', font=font, anchor='lt')
    elif overlay == 'grid':
        draw.text((x + 12, y + 10), 'شبکه تراکم', fill='#f8fafc', font=title_font, anchor='lt')
        colors = ['#fde047', '#fb923c', '#ef4444', '#7f1d1d']
        for i, col in enumerate(colors):
            bx = x + 12 + i * 40
            draw.rectangle((bx, y + 38, bx + 34, y + 52), fill=col)
        draw.text((x + 12, y + 62), 'کم فایل', fill='#94a3b8', font=font, anchor='lt')
        draw.text((x + w - 12, y + 62), 'پر فایل', fill='#94a3b8', font=font, anchor='rt')
        draw.text((x + 12, y + 80), 'عدد روی خانه = تعداد', fill='#cbd5e1', font=font, anchor='lt')
    else:
        draw.text((x + 12, y + 10), 'تراکم فایل‌ها', fill='#f8fafc', font=title_font, anchor='lt')
        colors = ['#fde047', '#fb923c', '#ef4444', '#7f1d1d']
        for i, col in enumerate(colors):
            bx = x + 12 + i * 40
            draw.rectangle((bx, y + 38, bx + 34, y + 52), fill=col)
        draw.text((x + 12, y + 62), 'کم', fill='#94a3b8', font=font, anchor='lt')
        draw.text((x + w - 12, y + 62), 'زیاد', fill='#94a3b8', font=font, anchor='rt')
        draw.text((x + 12, y + 80), 'بدون موقعیت دقیق آگهی', fill='#cbd5e1', font=font, anchor='lt')


def _render_kpi_card(city, district, tx_label, metric_label, metric_fmt, trend, valid_count, confidence) -> Image.Image:
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#0b1220')
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
