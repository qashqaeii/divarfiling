"""رندر حرفه‌ای تصویر شاخص و نقشه‌های مقاله — کارتوگرافی خوانا، دقیق و کاربردی."""
from __future__ import annotations

import io
import logging
import math
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

OG_WIDTH = 1200
OG_HEIGHT = 630
# رزولوشن بالاتر برای نمایش شارپ روی دسکتاپ/رтина
ARTICLE_MAP_W = 1600
ARTICLE_MAP_H = 960
TILE_SIZE = 256
USER_AGENT = 'DivarFilingMarketArticle/1.0 (https://divarfiling.ir; market-report)'

TILE_TEMPLATES = {
    'street': 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
    'light': 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
    'dark': 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
    'satellite': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
}
STREET_SUBS = 'abcd'

# ترکیب‌های متنوع basemap × لایه — ماهواره وزن بیشتر دارد تا عکس‌های شاخص شبیه هم نشوند
_FEATURED_COMBOS = (
    ('satellite', 'heat'),
    ('satellite', 'value'),
    ('satellite', 'hotspots'),
    ('satellite', 'grid'),
    ('satellite', 'dots'),
    ('satellite', 'heat'),
    ('satellite', 'value'),
    ('dark', 'heat'),
    ('dark', 'value'),
    ('dark', 'hotspots'),
    ('dark', 'dots'),
    ('light', 'heat'),
    ('light', 'value'),
    ('light', 'grid'),
    ('light', 'hotspots'),
    ('street', 'heat'),
    ('street', 'value'),
    ('street', 'hotspots'),
    ('street', 'grid'),
    ('street', 'dots'),
)

_ARTICLE_MAP_POOL = (
    ('map_sat_heat', 'satellite', 'heat', 'تراکم روی ماهواره', 'بافت شهری + هیت‌مپ عرضه'),
    ('map_sat_value', 'satellite', 'value', 'ارزش روی ماهواره', 'سطح قیمت/رهن روی تصویر ماهواره‌ای'),
    ('map_sat_hotspots', 'satellite', 'hotspots', 'کانون‌ها روی ماهواره', 'رتبه کانون‌های پرتراکم روی بافت واقعی'),
    ('map_sat_grid', 'satellite', 'grid', 'شبکه روی ماهواره', 'شمارش فایل در شبکه روی تصویر ماهواره‌ای'),
    ('map_sat_dots', 'satellite', 'dots', 'پراکنش روی ماهواره', 'نقاط تجمیعی عرضه روی بافت واقعی'),
    ('map_dark_heat', 'dark', 'heat', 'هیت‌مپ شب‌گونه', 'تراکم عرضه روی نقشه تیره'),
    ('map_dark_value', 'dark', 'value', 'ارزش شب‌گونه', 'سطح ارزش روی نقشه تیره'),
    ('map_dark_hotspots', 'dark', 'hotspots', 'کانون‌های شب‌گونه', 'رتبه‌بندی کانون‌ها روی نقشه تیره'),
    ('map_dark_dots', 'dark', 'dots', 'پراکنش شب‌گونه', 'نقاط تجمیعی روی نقشه تیره'),
    ('map_light_heat', 'light', 'heat', 'هیت‌مپ روشن', 'تراکم روی نقشه مینیمال روشن'),
    ('map_light_value', 'light', 'value', 'ارزش روشن', 'سطح ارزش روی نقشه روشن'),
    ('map_light_grid', 'light', 'grid', 'شبکه کمی روشن', 'شمارش فایل روی شبکه روشن'),
    ('map_light_hotspots', 'light', 'hotspots', 'کانون‌های روشن', 'رتبه کانون‌ها روی نقشه مینیمال'),
    ('map_street_heat', 'street', 'heat', 'هیت‌مپ شهری', 'تراکم روی نقشه خیابانی'),
    ('map_street_value', 'street', 'value', 'ارزش شهری', 'سطح ارزش روی نقشه خیابانی'),
    ('map_street_hotspots', 'street', 'hotspots', 'کانون‌های شهری', 'اولویت بازدید روی نقشه خیابانی'),
    ('map_street_grid', 'street', 'grid', 'شبکه کمی شهری', 'عمق محلی عرضه روی نقشه خیابانی'),
    ('map_street_dots', 'street', 'dots', 'پراکنش شهری', 'نقاط تجمیعی روی نقشه خیابانی'),
)

# نگاشت سازگاری با کلیدهای قدیمی در مقالات قبلی
_LEGACY_KEY_ALIASES = {
    'street_heat': 'map_street_heat',
    'street_value': 'map_street_value',
    'street_grid': 'map_street_grid',
    'street_hotspots': 'map_street_hotspots',
    'satellite_heat': 'map_sat_heat',
    'satellite_value': 'map_sat_value',
    'satellite': 'map_sat_heat',
    'price': 'map_street_value',
}

_FONT_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
_FONT_FILES = {
    'regular': 'Vazirmatn-Regular.ttf',
    'medium': 'Vazirmatn-Medium.ttf',
    'semibold': 'Vazirmatn-SemiBold.ttf',
    'bold': 'Vazirmatn-Bold.ttf',
}


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
) -> tuple[ContentFile, dict[str, str]]:
    """عکس شاخص با basemap/لایه کاملاً تصادفی در هر ساخت تا مقالات شبیه هم نشوند."""
    img = None
    meta: dict[str, str] = {'featured_style': '', 'featured_overlay': ''}
    if geo_points and len(geo_points) >= 8:
        style, overlay = random.SystemRandom().choice(_FEATURED_COMBOS)
        meta = {'featured_style': style, 'featured_overlay': overlay}
        style_fa = {
            'satellite': 'ماهواره‌ای',
            'dark': 'تیره',
            'light': 'روشن',
            'street': 'شهری',
        }.get(style, 'شهری')
        overlay_fa = {
            'heat': 'تراکم فایل',
            'value': metric_label,
            'hotspots': 'کانون‌های پرتراکم',
            'grid': 'شبکه کمی',
            'dots': 'پراکنش تجمیعی',
        }.get(overlay, 'تحلیل مکانی')
        img = _compose_map_canvas(
            geo_points,
            width=OG_WIDTH,
            height=OG_HEIGHT,
            style=style,
            overlay=overlay,
            title=f'نقشه بازار · {district}',
            subtitle=f'{city} · {tx_label} · نمای {style_fa}',
            footer=f'{overlay_fa}: {metric_fmt} · {valid_count} فایل · اعتماد {confidence_score}',
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
        meta = {'featured_style': 'kpi', 'featured_overlay': ''}
    return _to_content_file(img, f'market-og-{_safe(city)}-{_safe(district)}.png'), meta


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
    access_markers: list[dict] | None = None,
) -> dict[str, ContentFile]:
    """نقشه‌های متنوع بدنه مقاله — ترکیب ماهواره/تیره/روشن/شهری برای هر بازار فرق می‌کند."""
    out: dict[str, ContentFile] = {}
    if not geo_points or len(geo_points) < 8:
        return out

    place = f'{district} · {city}'
    specs = _pick_article_map_specs(city=city, district=district, tx_label=tx_label)
    for key, style, overlay, title_core, footer_core in specs:
        markers = access_markers if style == 'satellite' else None
        img = _compose_map_canvas(
            geo_points,
            width=ARTICLE_MAP_W,
            height=ARTICLE_MAP_H,
            style=style,
            overlay=overlay,
            title=f'{title_core} · {district}',
            subtitle=place,
            footer=f'{footer_core} · {tx_label} · {valid_count} فایل · {metric_label}: {metric_fmt}',
            place=place,
            metric_label=metric_label,
            metric_fmt=metric_fmt,
            brand=True,
            tight=True,
            access_markers=markers,
        )
        if img:
            out[key] = _to_content_file(img, f'market-{key}-{_safe(city)}-{_safe(district)}.png')
    return out


def _pick_article_map_specs(*, city: str, district: str, tx_label: str) -> list[tuple]:
    """۶–۷ نقشه متنوع: حداقل ۳ ماهواره + سبک‌ها و لایه‌های غیرتکراری برای هر محله."""
    rng = random.Random(f'{city}|{district}|{tx_label}|maps-v3')
    sat = [x for x in _ARTICLE_MAP_POOL if x[1] == 'satellite']
    others = [x for x in _ARTICLE_MAP_POOL if x[1] != 'satellite']
    rng.shuffle(sat)
    rng.shuffle(others)

    picked: list[tuple] = list(sat[:3])
    used_overlays = {x[2] for x in picked}
    used_styles = {'satellite'}

    def _try_add(item: tuple) -> bool:
        if item in picked:
            return False
        style, overlay = item[1], item[2]
        # ترجیح: لایه و basemap تکراری کمتر
        if overlay in used_overlays and len(picked) < 5:
            return False
        picked.append(item)
        used_overlays.add(overlay)
        used_styles.add(style)
        return True

    for item in others:
        if len(picked) >= 7:
            break
        style = item[1]
        if style not in used_styles:
            _try_add(item)
    for item in others:
        if len(picked) >= 7:
            break
        _try_add(item)
    for item in others + sat:
        if len(picked) >= 6:
            break
        if item not in picked:
            picked.append(item)
    rng.shuffle(picked)
    # ماهواره‌ها را جلوتر نگه دار تا در مقاله زودتر دیده شوند
    picked.sort(key=lambda x: 0 if x[1] == 'satellite' else 1)
    return picked[:7]


def _e_plain(text: str) -> str:
    return str(text or '')


def _to_content_file(img: Image.Image, name: str) -> ContentFile:
    """PNG با فشرده‌سازی ملایم — کیفیت بصری حفظ می‌شود."""
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(
        buf,
        format='PNG',
        optimize=False,
        compress_level=3,
        dpi=(144, 144),
    )
    buf.seek(0)
    return ContentFile(buf.read(), name=name)


def _safe(text: str) -> str:
    return ''.join(c if c.isalnum() else '-' for c in (text or 'x'))[:40]


def _has_arabic(text: str) -> bool:
    return any(
        ('\u0600' <= ch <= '\u06FF')
        or ('\u0750' <= ch <= '\u077F')
        or ('\u08A0' <= ch <= '\u08FF')
        or ('\uFB50' <= ch <= '\uFDFF')
        or ('\uFE70' <= ch <= '\uFEFF')
        for ch in (text or '')
    )


def _bidi_display(text: str) -> str:
    """نسخه پایدار get_display؛ الگوریتم پایتون python-bidi (نه Rust) + base_dir=R."""
    try:
        from bidi.algorithm import get_display  # type: ignore
    except Exception:
        try:
            from bidi import get_display  # type: ignore
        except Exception as exc:
            logger.warning('python-bidi import failed: %s', exc)
            return text
    try:
        return get_display(text, base_dir='R')
    except TypeError:
        try:
            return get_display(text)
        except Exception as exc:
            logger.warning('get_display failed: %s', exc)
            return text
    except Exception as exc:
        logger.warning('get_display failed: %s', exc)
        return text


def _reshape_arabic(text: str) -> str:
    try:
        import arabic_reshaper
        return arabic_reshaper.reshape(text)
    except Exception as exc:
        logger.warning('arabic_reshaper failed: %s', exc)
        return text


def _shape_persian(text: str) -> str:
    """آماده‌سازی فارسی برای اندازه‌گیری عرض / مسیر bidi (بدون kwargs رندر)."""
    raw = str(text or '')
    if not raw or not _has_arabic(raw):
        return raw
    mode, _kwargs = _persian_render_mode()
    reshaped = _reshape_arabic(raw)
    if mode == 'rtl':
        return raw
    if mode == 'bidi':
        return _bidi_display(reshaped)
    if mode == 'reshape_rev':
        return reshaped[::-1]
    if mode == 'reshape':
        return reshaped
    return raw


@lru_cache(maxsize=64)
def _font(size: int, weight: str = 'regular'):
    """فونت Vazirmatn پروژه؛ در نبود، فونت‌های سیستم با پشتیبانی فارسی."""
    size = max(8, int(size))
    weight = weight if weight in _FONT_FILES else 'regular'
    candidates = [
        _FONT_DIR / _FONT_FILES[weight],
        _FONT_DIR / _FONT_FILES['regular'],
        Path('C:/Windows/Fonts/tahoma.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'),
    ]
    for path in candidates:
        try:
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=1)
def _pillow_supports_rtl() -> bool:
    """آیا Pillow با libraqm از direction=rtl پشتیبانی می‌کند؟"""
    try:
        img = Image.new('RGB', (8, 8), 'white')
        draw = ImageDraw.Draw(img)
        font = _font(16, 'bold')
        draw.text((0, 0), 'آ', font=font, direction='rtl', language='fa')
        return True
    except Exception:
        return False


def _glyph_on_right(full: str, glyph: str, font, draw_kwargs: dict = None) -> bool:
    """آیا گلیف `glyph` در سمت راست `full` رندر می‌شود؟ (برای تشخیص RTL واقعی)."""
    kwargs = dict(draw_kwargs or {})
    img = Image.new('L', (420, 96), 0)
    gimg = Image.new('L', (420, 96), 0)
    ImageDraw.Draw(img).text((24, 16), full, fill=255, font=font, **kwargs)
    ImageDraw.Draw(gimg).text((24, 16), glyph, fill=255, font=font, **kwargs)
    fa = img.load()
    ga = gimg.load()
    w, h = img.size

    def col_ink(px, x: int) -> bool:
        for y in range(h):
            if px[x, y] > 0:
                return True
        return False

    cols_f = [x for x in range(w) if col_ink(fa, x)]
    cols_g = [x for x in range(w) if col_ink(ga, x)]
    if not cols_f or not cols_g:
        return False
    left, right = cols_f[0], cols_f[-1]
    g_left, g_right = cols_g[0], cols_g[-1]
    gw = max(1, g_right - g_left + 1)

    def score(x0: int) -> float:
        matched = total = 0
        for dx in range(gw):
            x = x0 + dx
            if x < 0 or x >= w:
                continue
            for y in range(h):
                want = ga[g_left + dx, y] > 0
                got = fa[x, y] > 0
                if want or got:
                    total += 1
                    if want == got:
                        matched += 1
        return matched / total if total else 0.0

    left_score = score(left)
    right_score = score(right - gw + 1)
    return right_score >= left_score


@lru_cache(maxsize=1)
def _persian_render_mode() -> tuple[str, tuple]:
    """
    انتخاب تجربی مسیر رندر فارسی روی همین Pillow/FreeType:
    - rtl: متن منطقی + direction=rtl (libraqm)
    - bidi: reshape + get_display روی canvas LTR
    - reshape_rev / reshape / raw: مسیرهای پشتیبان
    دوبار اعمال کردن bidi + RTL فونت باعث برعکس شدن متن می‌شود.
    """
    font = _font(40, 'bold')
    probe = 'ژتراکم'  # ژ باید سمت راست باشد
    glyph = 'ژ'
    candidates: list[tuple[str, str, dict]] = []
    if _pillow_supports_rtl():
        candidates.append(('rtl', probe, {'direction': 'rtl', 'language': 'fa'}))
    reshaped = _reshape_arabic(probe)
    candidates.extend(
        [
            ('bidi', _bidi_display(reshaped), {}),
            ('reshape_rev', reshaped[::-1], {}),
            ('reshape', reshaped, {}),
            ('raw', probe, {}),
        ]
    )
    for mode, text, kwargs in candidates:
        try:
            if _glyph_on_right(text, glyph if mode == 'rtl' else _reshape_arabic(glyph), font, kwargs):
                logger.info('Persian map text render mode: %s', mode)
                return mode, tuple(sorted(kwargs.items()))
        except Exception as exc:
            logger.debug('Persian render probe failed for %s: %s', mode, exc)
    logger.warning('Persian render probe inconclusive; falling back to bidi')
    return 'bidi', tuple()


def _prepare_persian_draw(text: str) -> tuple[str, dict]:
    """متن + kwargs مناسب draw.text برای فارسی خوانا."""
    raw = str(text or '')
    if not raw or not _has_arabic(raw):
        return raw, {}
    mode, kw_items = _persian_render_mode()
    kwargs = dict(kw_items)
    if mode == 'rtl':
        return raw, kwargs
    reshaped = _reshape_arabic(raw)
    if mode == 'bidi':
        return _bidi_display(reshaped), {}
    if mode == 'reshape_rev':
        return reshaped[::-1], {}
    if mode == 'reshape':
        return reshaped, {}
    return raw, {}


def _draw_text(draw: ImageDraw.ImageDraw, xy, text: str, *, fill, font, anchor: str = 'lt') -> None:
    """رندر فارسی با مسیر انتخاب‌شدهٔ تجربی (جلوگیری از double-RTL)."""
    raw = str(text or '')
    if not raw:
        return
    prepared, kwargs = _prepare_persian_draw(raw)
    draw.text(xy, prepared, fill=fill, font=font, anchor=anchor, **kwargs)


def _latlon_to_world_px(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat = max(min(lat, 85.05112878), -85.05112878)
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE
    return x, y


def _meters_per_pixel(lat: float, zoom: int) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)


def _percentile_bbox(points: list[dict], lo: float = 0.10, hi: float = 0.90) -> tuple[float, float, float, float]:
    lats = sorted(float(p['lat']) for p in points)
    lngs = sorted(float(p['lng']) for p in points)
    n = len(lats)
    i0 = max(0, int(n * lo))
    i1 = min(n - 1, int(n * hi))
    min_lat, max_lat = lats[i0], lats[i1]
    min_lng, max_lng = lngs[i0], lngs[i1]
    if max_lat - min_lat < 0.0009:
        mid = (max_lat + min_lat) / 2
        min_lat, max_lat = mid - 0.00075, mid + 0.00075
    if max_lng - min_lng < 0.0009:
        mid = (max_lng + min_lng) / 2
        min_lng, max_lng = mid - 0.00075, mid + 0.00075
    return min_lat, max_lat, min_lng, max_lng


def _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w: int, map_h: int, *, tight: bool) -> int:
    # fill بالاتر = زوم نزدیک‌تر (bbox بخش بیشتری از کادر را پر می‌کند)
    fill = 0.86 if tight else 0.94
    best = 14
    for z in range(18, 12, -1):
        x0, y0 = _latlon_to_world_px(max_lat, min_lng, z)
        x1, y1 = _latlon_to_world_px(min_lat, max_lng, z)
        bw, bh = abs(x1 - x0), abs(y1 - y0)
        if bw <= map_w * fill and bh <= map_h * fill:
            return z
        best = z
    return best


def _fetch_tile(url: str, *, retries: int = 3, timeout: int = 10) -> Image.Image | None:
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            return Image.open(io.BytesIO(data)).convert('RGB')
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            last_err = exc
            if attempt + 1 < retries:
                time.sleep(0.25 * (attempt + 1))
            continue
    logger.debug('tile fetch failed %s: %s', url, last_err)
    return None


def _tile_url(style: str, z: int, x: int, y: int) -> str:
    if style == 'satellite':
        return TILE_TEMPLATES['satellite'].format(z=z, y=y, x=x)
    tmpl = TILE_TEMPLATES.get(style) or TILE_TEMPLATES['street']
    sub = random.choice(list(STREET_SUBS))
    return tmpl.format(s=sub, z=z, x=x, y=y)


def _build_basemap(
    *,
    style: str,
    zoom: int,
    min_tx: int,
    max_tx: int,
    min_ty: int,
    max_ty: int,
    deadline: float | None = None,
) -> Image.Image | None:
    cols = max_tx - min_tx + 1
    rows = max_ty - min_ty + 1
    total = cols * rows
    if total > 100 or total < 1:
        return None

    # ماهواره کندتر و حساس‌تر به تایل ناقص است — آستانه و تلاش بیشتر
    is_sat = style == 'satellite'
    min_ratio = 0.97 if is_sat else 0.88
    workers = 6 if is_sat else 12
    tile_timeout = 14 if is_sat else 10
    base_retries = 4 if is_sat else 3
    if deadline is None:
        # سقف زمانی برای جلوگیری از گیر کردن طولانی (پس‌زمینه هم محدود می‌ماند)
        deadline = time.monotonic() + (55 if is_sat else 35)

    fill = {'satellite': '#1e293b', 'dark': '#0f172a', 'light': '#e8eef5'}.get(style, '#d7dee8')
    canvas = Image.new('RGB', (cols * TILE_SIZE, rows * TILE_SIZE), fill)
    jobs = [
        (tx, ty, _tile_url(style, zoom, tx, ty))
        for ty in range(min_ty, max_ty + 1)
        for tx in range(min_tx, max_tx + 1)
    ]

    placed: set[tuple[int, int]] = set()
    failed: list[tuple[int, int]] = [(tx, ty) for tx, ty, _ in jobs]

    def _paste_batch(coords: list[tuple[int, int]], *, retries: int, pool_size: int) -> None:
        nonlocal failed
        still: list[tuple[int, int]] = []
        with ThreadPoolExecutor(max_workers=pool_size) as pool:
            futures = {
                pool.submit(
                    _fetch_tile,
                    _tile_url(style, zoom, tx, ty),
                    retries=retries,
                    timeout=tile_timeout,
                ): (tx, ty)
                for tx, ty in coords
            }
            for fut in as_completed(futures):
                tx, ty = futures[fut]
                tile = fut.result()
                if tile is None:
                    still.append((tx, ty))
                    continue
                placed.add((tx, ty))
                canvas.paste(tile, ((tx - min_tx) * TILE_SIZE, (ty - min_ty) * TILE_SIZE))
        failed = still

    _paste_batch(failed, retries=base_retries, pool_size=workers)

    # چند دور تکمیل برای تایل‌های جامانده (مخصوصاً ماهواره)
    max_rounds = 4 if is_sat else 2
    for round_i in range(max_rounds):
        if not failed:
            break
        if time.monotonic() >= deadline:
            logger.info('basemap deadline reached (%s): %s/%s ok', style, len(placed), total)
            break
        time.sleep(0.35 * (round_i + 1))
        _paste_batch(
            failed,
            retries=5 if is_sat else 4,
            pool_size=4 if is_sat else 8,
        )

    ok = len(placed)
    if ok < max(1, int(total * min_ratio)):
        logger.warning('basemap incomplete (%s): %s/%s tiles', style, ok, total)
        return None
    if failed:
        logger.info('basemap accepted with gaps (%s): %s/%s ok', style, ok, total)
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
    access_markers: list[dict] | None = None,
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
    pad_lat = max((max_lat - min_lat) * (0.03 if tight else 0.08), 0.00045)
    pad_lng = max((max_lng - min_lng) * (0.03 if tight else 0.08), 0.00045)
    min_lat -= pad_lat
    max_lat += pad_lat
    min_lng -= pad_lng
    max_lng += pad_lng

    zoom = _choose_zoom(min_lat, max_lat, min_lng, max_lng, map_w, map_h, tight=tight)
    # یک پله نزدیک‌تر اگر هنوز کادر را از حد معقول پر نکند
    if tight and zoom < 18:
        x0, y0 = _latlon_to_world_px(max_lat, min_lng, zoom + 1)
        x1, y1 = _latlon_to_world_px(min_lat, max_lng, zoom + 1)
        if abs(x1 - x0) <= map_w * 0.96 and abs(y1 - y0) <= map_h * 0.96:
            zoom += 1
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

    # خوانایی لایه روی basemapهای مختلف
    if style == 'satellite':
        shade = Image.new('RGBA', (map_w, map_h), (15, 23, 42, 55))
        view = Image.alpha_composite(view.convert('RGBA'), shade).convert('RGB')
    elif style == 'light':
        shade = Image.new('RGBA', (map_w, map_h), (15, 23, 42, 18))
        view = Image.alpha_composite(view.convert('RGBA'), shade).convert('RGB')
    elif style == 'dark':
        # کمی روشن‌تر تا رنگ لایه‌ها بهتر دیده شود
        lift = Image.new('RGBA', (map_w, map_h), (255, 255, 255, 18))
        view = Image.alpha_composite(view.convert('RGBA'), lift).convert('RGB')

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
    label_font = _font(16, 'semibold')
    tiny_font = _font(13, 'medium')
    count_font = _font(13, 'bold')

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
                draw_heat.text((cx, cy), str(c['n']), fill=(255, 255, 255, 230), font=count_font, anchor='mm')

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
        heat = heat.filter(ImageFilter.GaussianBlur(radius=6))
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
            draw_heat.rounded_rectangle((bx, by, bx + 58, by + 28), radius=8, fill=(15, 23, 42, 230))
            draw_heat.text((bx + 29, by + 14), f'#{badge} · {c["n"]}', fill=(248, 250, 252, 255), font=count_font, anchor='mm')

    elif overlay == 'dots':
        ranked = sorted(cells, key=lambda c: c['n'], reverse=True)
        for c in ranked:
            x, y = project(c['lat'], c['lng'])
            if not (-10 <= x < map_w + 10 and -10 <= y < map_h + 10):
                continue
            t = (c['n'] - n_lo) / (n_hi - n_lo)
            r = 5 + min(16, 3.2 * math.sqrt(c['n']))
            color = _density_color(t, alpha=int(120 + 100 * t))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=color)
            draw_heat.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 140), width=1)

    else:  # heat
        for c in cells:
            x, y = project(c['lat'], c['lng'])
            if not (-30 <= x < map_w + 30 and -30 <= y < map_h + 30):
                continue
            t = (c['n'] - n_lo) / (n_hi - n_lo)
            r = 20 + min(36, 7.5 * math.sqrt(c['n']))
            draw_heat.ellipse((x - r, y - r, x + r, y + r), fill=_density_color(t, alpha=int(45 + 130 * t)))

    if overlay in ('heat', 'value'):
        heat = heat.filter(ImageFilter.GaussianBlur(radius=7 if overlay == 'heat' else 4))
    elif overlay == 'grid':
        heat = heat.filter(ImageFilter.GaussianBlur(radius=0.8))
    elif overlay == 'dots':
        heat = heat.filter(ImageFilter.GaussianBlur(radius=0.6))

    view_rgba = Image.alpha_composite(view.convert('RGBA'), heat)

    if access_markers:
        poi_layer = Image.new('RGBA', (map_w, map_h), (0, 0, 0, 0))
        poi_draw = ImageDraw.Draw(poi_layer)
        for m in access_markers[:36]:
            try:
                mx, my = project(float(m['lat']), float(m['lng']))
            except (KeyError, TypeError, ValueError):
                continue
            if not (8 <= mx < map_w - 8 and 8 <= my < map_h - 8):
                continue
            color = _hex_rgb(m.get('color') or '#14b8a6', alpha=230)
            poi_draw.ellipse((mx - 7, my - 7, mx + 7, my + 7), fill=(255, 255, 255, 220))
            poi_draw.ellipse((mx - 5, my - 5, mx + 5, my + 5), fill=color)
        view_rgba = Image.alpha_composite(view_rgba, poi_layer)

    chrome = Image.new('RGBA', (map_w, map_h), (0, 0, 0, 0))
    draw_chrome = ImageDraw.Draw(chrome)
    _draw_north_arrow(draw_chrome, map_w - 42, 36)
    center_lat = (min_lat + max_lat) / 2
    _draw_scale_bar(draw_chrome, 28, map_h - 36, center_lat, zoom, tiny_font)
    _draw_place_badge(draw_chrome, 28, 24, place, label_font)
    _draw_legend_panel(
        draw_chrome,
        map_w - 230,
        map_h - (128 if overlay == 'value' else 112),
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
    title_font = _font(28 if width >= 1400 else (24 if width >= 1100 else 18), 'bold')
    sub_font = _font(17, 'medium')
    small = _font(16, 'regular')
    tiny_font = _font(13, 'regular')

    draw.rectangle((0, 0, width, header_h), fill='#0b1220')
    draw.rectangle((0, height - footer_h, width, height), fill='#0b1220')
    draw.rectangle((0, header_h - 3, width, header_h), fill='#14b8a6')
    _draw_text(draw, (28, 16), title, fill='#f8fafc', font=title_font, anchor='lt')
    _draw_text(draw, (28, 48), subtitle, fill='#94a3b8', font=sub_font, anchor='lt')
    if brand:
        _draw_text(draw, (width - 28, 20), 'فایلینگ دیوار', fill='#5eead4', font=_font(17, 'semibold'), anchor='rt')
        _draw_text(draw, (width - 28, 46), 'تحلیل داده‌محور بازار', fill='#64748b', font=tiny_font, anchor='rt')

    _draw_text(draw, (28, height - footer_h + 16), footer, fill='#cbd5e1', font=small, anchor='lt')
    _draw_text(
        draw,
        (28, height - 28),
        'نمایش تجمیعی شبکه‌ای · موقعیت تک‌آگهی نشان داده نمی‌شود',
        fill='#64748b',
        font=tiny_font,
        anchor='lt',
    )
    _draw_text(
        draw,
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


def _hex_rgb(color: str, *, alpha: int = 255) -> tuple[int, int, int, int]:
    raw = (color or '').strip().lstrip('#')
    if len(raw) == 3:
        raw = ''.join(ch * 2 for ch in raw)
    try:
        r = int(raw[0:2], 16)
        g = int(raw[2:4], 16)
        b = int(raw[4:6], 16)
        return (r, g, b, alpha)
    except (ValueError, IndexError):
        return (20, 184, 166, alpha)


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
    draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=(15, 23, 42, 210), outline=(255, 255, 255, 200))
    draw.polygon([(x, y - 12), (x - 7, y + 8), (x, y + 3), (x + 7, y + 8)], fill=(248, 250, 252))
    draw.text((x, y + 26), 'N', fill=(15, 23, 42), font=_font(12, 'bold'), anchor='mm')


def _draw_scale_bar(draw: ImageDraw.ImageDraw, x: int, y: int, lat: float, zoom: int, font) -> None:
    mpp = _meters_per_pixel(lat, zoom)
    target_m = 500
    for cand in (100, 200, 250, 500, 1000, 2000, 5000):
        px = cand / max(mpp, 1e-6)
        if 80 <= px <= 220:
            target_m = cand
            break
    else:
        target_m = max(100, int(round(140 * mpp / 100) * 100))
    px = target_m / max(mpp, 1e-6)
    label = f'{target_m} متر' if target_m < 1000 else f'{target_m / 1000:g} کیلومتر'
    draw.rounded_rectangle((x - 8, y - 24, x + px + 14, y + 12), radius=8, fill=(15, 23, 42, 210))
    draw.rectangle((x, y - 2, x + px, y + 2), fill=(248, 250, 252))
    draw.rectangle((x, y - 6, x + 2, y + 6), fill=(248, 250, 252))
    draw.rectangle((x + px - 2, y - 6, x + px, y + 6), fill=(248, 250, 252))
    _draw_text(draw, (x + px / 2, y - 13), label, fill=(226, 232, 240), font=font, anchor='mm')


def _draw_place_badge(draw: ImageDraw.ImageDraw, x: int, y: int, place: str, font) -> None:
    text = place or 'محله'
    sample, _ = _prepare_persian_draw(text)
    try:
        bbox = font.getbbox(sample)
        tw = max(140, min(420, (bbox[2] - bbox[0]) + 36))
    except Exception:
        tw = max(140, min(420, 14 + len(text) * 11))
    draw.rounded_rectangle((x, y, x + tw, y + 34), radius=10, fill=(15, 23, 42, 220))
    draw.rectangle((x, y + 7, x + 4, y + 27), fill=(20, 184, 166))
    _draw_text(draw, (x + 16, y + 17), text, fill=(248, 250, 252), font=font, anchor='lm')


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
    w, h = 210, 104 if overlay != 'value' else 118
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=(15, 23, 42, 230))

    if overlay == 'value':
        title = (metric_label or 'سطح ارزش')[:24]
        _draw_text(draw, (x + 12, y + 10), title, fill='#f8fafc', font=title_font, anchor='lt')
        colors = ['#3b82f6', '#14b8a6', '#f59e0b', '#ef4444']
        for i, col in enumerate(colors):
            bx = x + 14 + i * 46
            draw.rectangle((bx, y + 40, bx + 40, y + 54), fill=col)
        _draw_text(draw, (x + 12, y + 64), 'پایین', fill='#94a3b8', font=font, anchor='lt')
        _draw_text(draw, (x + w - 12, y + 64), 'بالا', fill='#94a3b8', font=font, anchor='rt')
        if metric_fmt:
            _draw_text(draw, (x + 12, y + 88), f'میانه: {metric_fmt}'[:30], fill='#cbd5e1', font=font, anchor='lt')
    elif overlay == 'hotspots':
        _draw_text(draw, (x + 12, y + 10), 'کانون عرضه', fill='#f8fafc', font=title_font, anchor='lt')
        _draw_text(draw, (x + 12, y + 42), 'شماره = رتبه تراکم', fill='#cbd5e1', font=font, anchor='lt')
        _draw_text(draw, (x + 12, y + 66), 'عدد کنار # = تعداد فایل', fill='#94a3b8', font=font, anchor='lt')
    elif overlay == 'grid':
        _draw_text(draw, (x + 12, y + 10), 'شبکه تراکم', fill='#f8fafc', font=title_font, anchor='lt')
        colors = ['#fde047', '#fb923c', '#ef4444', '#7f1d1d']
        for i, col in enumerate(colors):
            bx = x + 14 + i * 46
            draw.rectangle((bx, y + 40, bx + 40, y + 54), fill=col)
        _draw_text(draw, (x + 12, y + 66), 'کم فایل', fill='#94a3b8', font=font, anchor='lt')
        _draw_text(draw, (x + w - 12, y + 66), 'پر فایل', fill='#94a3b8', font=font, anchor='rt')
        _draw_text(draw, (x + 12, y + 86), 'عدد روی خانه = تعداد', fill='#cbd5e1', font=font, anchor='lt')
    elif overlay == 'dots':
        _draw_text(draw, (x + 12, y + 10), 'پراکنش تجمیعی', fill='#f8fafc', font=title_font, anchor='lt')
        _draw_text(draw, (x + 12, y + 42), 'نقطه درشت‌تر = سلول پرتراکم‌تر', fill='#cbd5e1', font=font, anchor='lt')
        _draw_text(draw, (x + 12, y + 66), 'بدون افشای موقعیت تک‌آگهی', fill='#94a3b8', font=font, anchor='lt')
    else:
        _draw_text(draw, (x + 12, y + 10), 'تراکم فایل‌ها', fill='#f8fafc', font=title_font, anchor='lt')
        colors = ['#fde047', '#fb923c', '#ef4444', '#7f1d1d']
        for i, col in enumerate(colors):
            bx = x + 14 + i * 46
            draw.rectangle((bx, y + 40, bx + 40, y + 54), fill=col)
        _draw_text(draw, (x + 12, y + 66), 'کم', fill='#94a3b8', font=font, anchor='lt')
        _draw_text(draw, (x + w - 12, y + 66), 'زیاد', fill='#94a3b8', font=font, anchor='rt')
        _draw_text(draw, (x + 12, y + 86), 'بدون موقعیت دقیق آگهی', fill='#cbd5e1', font=font, anchor='lt')


def _render_kpi_card(city, district, tx_label, metric_label, metric_fmt, trend, valid_count, confidence) -> Image.Image:
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), '#0b1220')
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, OG_WIDTH, 180), fill='#134e4a')
    title_font = _font(40, 'bold')
    sub_font = _font(24, 'semibold')
    big_font = _font(42, 'bold')
    small_font = _font(20, 'medium')
    _draw_text(draw, (64, 48), 'فایلینگ دیوار', fill='#5eead4', font=sub_font, anchor='lt')
    _draw_text(draw, (64, 100), f'{district} · {city}', fill='#f8fafc', font=title_font, anchor='lt')
    _draw_text(draw, (64, 165), f'تحلیل داده‌محور بازار {tx_label}', fill='#94a3b8', font=sub_font, anchor='lt')
    draw.rounded_rectangle((64, 240, 1136, 420), radius=24, fill='#1e293b')
    _draw_text(draw, (96, 270), metric_label, fill='#94a3b8', font=small_font, anchor='lt')
    _draw_text(draw, (96, 320), str(metric_fmt or '—'), fill='#f8fafc', font=big_font, anchor='lt')
    _draw_text(draw, (64, 470), f'{valid_count} فایل معتبر · اعتماد {confidence}', fill='#e2e8f0', font=sub_font, anchor='lt')
    _draw_text(draw, (64, 530), f'روند: {trend or "—"}', fill='#94a3b8', font=small_font, anchor='lt')
    return img
