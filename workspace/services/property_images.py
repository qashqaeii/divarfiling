"""آپلود و مدیریت تصاویر فایل شخصی CRM."""
from __future__ import annotations

import json
import os
import uuid
from typing import List

from django.core.files.storage import default_storage

ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PROPERTY_IMAGES = 12


def validate_image_file(uploaded_file) -> None:
    name = getattr(uploaded_file, 'name', '') or ''
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError('فرمت تصویر پشتیبانی نمی‌شود. (JPG, PNG, WebP, GIF)')
    size = getattr(uploaded_file, 'size', 0) or 0
    if size > MAX_IMAGE_BYTES:
        raise ValueError('حجم هر تصویر حداکثر ۵ مگابایت است.')


def store_property_image(user, prop, uploaded_file) -> str:
    """ذخیره فایل در media و برگرداندن URL عمومی."""
    validate_image_file(uploaded_file)
    ext = os.path.splitext(uploaded_file.name or '')[1].lower() or '.jpg'
    rel_path = f'workspace/crm/properties/{user.pk}/{prop.pk}/{uuid.uuid4().hex}{ext}'
    saved = default_storage.save(rel_path, uploaded_file)
    return default_storage.url(saved)


def parse_images_payload(raw) -> List[str]:
    if raw is None or raw == '':
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            items = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        url = normalize_image_url(str(item or '').strip())
        if url:
            out.append(url)
    return out[:MAX_PROPERTY_IMAGES]


def normalize_image_url(url: str) -> str:
    url = str(url or '').strip()
    if not url:
        return ''
    if url.startswith('/media/'):
        return url
    if url.startswith('http://') or url.startswith('https://'):
        return url
    raise ValueError('آدرس تصویر باید با http یا https شروع شود.')


def normalize_external_image_url(url: str) -> str:
    """نرمال‌سازی URL تصاویر خارجی (دیوار، CDN و ...)."""
    url = str(url or '').strip()
    if not url or url.lower() in ('nan', 'none', '-'):
        return ''
    if url.startswith('//'):
        return f'https:{url}'
    if url.startswith('/media/'):
        return url
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if '.' in url:
        return f'https://{url.lstrip("/")}'
    return ''


_DIVAR_THUMBNAIL_MARKERS = ('/webp_thumbnail/', '/thumbnail/')


def divar_image_file_id(url: str) -> str:
    """شناسه فایل مشترک بین نسخه post و thumbnail یک عکس."""
    clean = str(url or '').split('?', 1)[0].rstrip('/')
    name = clean.rsplit('/', 1)[-1].lower()
    return name if name and '.' in name else ''


def divar_image_quality_score(url: str) -> int:
    lower = str(url or '').lower()
    if '/webp_post/' in lower:
        return 0
    if any(marker in lower for marker in _DIVAR_THUMBNAIL_MARKERS):
        return 2
    return 1


def deduplicate_divar_image_urls(urls: List[str]) -> List[str]:
    """یک URL برای هر عکس دیوار — نسخه با کیفیت (webp_post) بر thumbnail ترجیح دارد."""
    best_by_file: dict[str, tuple[int, int, str]] = {}
    passthrough: list[tuple[int, str]] = []

    for idx, raw in enumerate(urls):
        url = normalize_external_image_url(str(raw or ''))
        if not url:
            continue
        file_id = divar_image_file_id(url)
        if file_id and 'divar' in url.lower():
            score = divar_image_quality_score(url)
            cur = best_by_file.get(file_id)
            if cur is None or score < cur[0] or (score == cur[0] and idx < cur[1]):
                best_by_file[file_id] = (score, idx, url)
        else:
            passthrough.append((idx, url))

    out: List[str] = []
    seen_files: set[str] = set()
    seen_urls: set[str] = set()

    for idx, raw in enumerate(urls):
        url = normalize_external_image_url(str(raw or ''))
        if not url:
            continue
        file_id = divar_image_file_id(url)
        if file_id and 'divar' in url.lower():
            if file_id in seen_files:
                continue
            seen_files.add(file_id)
            best = best_by_file[file_id][2]
            if best not in seen_urls:
                out.append(best)
                seen_urls.add(best)
            continue
        if url not in seen_urls:
            out.append(url)
            seen_urls.add(url)

    return out


def best_divar_image_url_from_mapping(image: dict, item: dict | None = None) -> str:
    """بهترین لینک از آبجکت image/item — url کامل قبل از thumbnail."""
    item = item or {}
    image = image or {}
    for key in ('url', 'webp_url', 'image_url', 'thumbnail_url', 'thumbnail'):
        raw = str(image.get(key) or item.get(key) or '').strip()
        url = normalize_external_image_url(raw)
        if url:
            return url
    return ''
