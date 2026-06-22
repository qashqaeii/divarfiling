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
