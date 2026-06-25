"""ابزارهای مشترک بلاگ."""
from __future__ import annotations

import re

from django.utils.text import slugify

from blog.models import Post, Tag

_PERSIAN_MAP = {
    'ا': 'a', 'آ': 'a', 'أ': 'a', 'إ': 'a', 'ء': 'a',
    'ب': 'b', 'پ': 'p', 'ت': 't', 'ث': 's', 'ج': 'j',
    'چ': 'ch', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'z',
    'ر': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's', 'ش': 'sh',
    'ص': 's', 'ض': 'z', 'ط': 't', 'ظ': 'z', 'ع': 'a',
    'غ': 'gh', 'ف': 'f', 'ق': 'gh', 'ک': 'k', 'گ': 'g',
    'ل': 'l', 'م': 'm', 'ن': 'n', 'و': 'v', 'ه': 'h',
    'ی': 'y', 'ي': 'y', 'ئ': 'y', 'ة': 'h', 'ك': 'k',
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
}


def persian_to_slug(text: str) -> str:
    if not text:
        return ''
    result = []
    for char in text:
        if char in _PERSIAN_MAP:
            result.append(_PERSIAN_MAP[char])
        elif char.isalnum() or char in ('-', '_', ' '):
            result.append(char)
        else:
            result.append(' ')
    slug = slugify(''.join(result))
    return re.sub(r'-+', '-', slug).strip('-')


def normalize_persian_tag_name(text: str) -> str:
    """یکسان‌سازی نام برچسب — نیم‌فاصله و فاصله‌های اضافه."""
    if not text:
        return ''
    text = text.replace('\u200c', ' ')
    text = text.replace('\u00a0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def unique_tag_slug(base: str) -> str:
    slug = persian_to_slug(base) or 'tag'
    candidate = slug
    counter = 1
    while Tag.objects.filter(slug=candidate).exists():
        candidate = f'{slug}-{counter}'
        counter += 1
    return candidate


def get_or_create_tag(tag_name: str) -> Tag:
    """
    برچسب را بدون تداخل slug برمی‌گرداند.

    نام‌هایی مثل «قیمت گذاری ملک» و «قیمت‌گذاری ملک» slug یکسان دارند؛
    اگر برچسب با همان slug وجود داشته باشد، همان برگردانده می‌شود.
    """
    tag = Tag.objects.filter(name=tag_name).first()
    if tag:
        return tag

    normalized = normalize_persian_tag_name(tag_name)
    if normalized and normalized != tag_name:
        tag = Tag.objects.filter(name=normalized).first()
        if tag:
            return tag

    base_slug = persian_to_slug(normalized or tag_name)
    if base_slug:
        tag = Tag.objects.filter(slug=base_slug).first()
        if tag:
            return tag

    slug = unique_tag_slug(normalized or tag_name)
    return Tag.objects.create(name=tag_name, slug=slug)


def unique_post_slug(base: str) -> str:
    slug = persian_to_slug(base) or 'post'
    candidate = slug
    counter = 1
    while Post.objects.filter(slug=candidate).exists():
        candidate = f'{slug}-{counter}'
        counter += 1
    return candidate
