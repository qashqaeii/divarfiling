"""جستجوی آکادمی — آموزش‌های فعال و کلیدواژه‌های فارسی."""
from __future__ import annotations

import re
from typing import Iterable

from django.urls import reverse

from workspace.academy.curriculum import ordered_videos

# کلیدواژه‌های اضافه برای جستجوی فارسی (علاوه بر عنوان، توضیح و زیرعنوان)
EXTRA_KEYWORDS_BY_SLUG: dict[str, tuple[str, ...]] = {
    'academy-what-is-divar-filing': ('فایلینگ دیوار', 'فایلینگ'),
    'academy-dashboard-overview': ('داشبورد',),
    'academy-license-purchase-activation': ('لایسنس', 'خرید لایسنس', 'فعال‌سازی'),
    'academy-extract-divar-listings': ('استخراج', 'دیوار', 'پوشه استخراج'),
    'academy-filter-files': ('فیلتر',),
    'academy-review-analyze-file': ('تحلیل فایل', 'تحلیل', 'بررسی فایل'),
    'academy-personal-files-map': ('فایل شخصی', 'فایل‌های شخصی', 'نقشه',),
    'academy-file-cabinets-folders': ('زونکن', 'کمد', 'کمد فایل',),
    'academy-what-is-crm': ('CRM', 'مدیریت مشتری', 'مشتری',),
    'academy-adding-a-new-contact-to-crm': ('ثبت مخاطب', 'مخاطب', 'ثبت مشتری',),
    'academy-crm-reminders-and-follow-ups': ('یادآوری', 'پیگیری', 'پیگیری مشتری',),
    'academy-personal-files-and-sharing-with-customers': (
        'اشتراک فایل', 'لینک مشتری', 'ارسال ملک', 'فایل شخصی',
    ),
}


def _normalize_query(raw: str) -> str:
    text = (raw or '').strip().lower()
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = re.sub(r'\s+', ' ', text)
    return text


def _video_search_blob(video) -> str:
    parts = [
        video.title or '',
        getattr(video, 'description', '') or '',
        video.subtitle or '',
        video.slug or '',
    ]
    for kw in EXTRA_KEYWORDS_BY_SLUG.get(video.slug, ()):
        parts.append(kw)
    blob = ' '.join(parts)
    return _normalize_query(blob)


def _match_score(video, query: str) -> int:
    q = _normalize_query(query)
    if not q:
        return 0
    blob = _video_search_blob(video)
    score = 0
    if q in blob:
        score += 100
    for kw in EXTRA_KEYWORDS_BY_SLUG.get(video.slug, ()):
        nkw = _normalize_query(kw)
        if q == nkw:
            score += 90
        elif q in nkw or nkw in q:
            score += 70
    for token in q.split():
        if len(token) >= 2 and token in blob:
            score += 12
    return score


def video_matches_query(video, query: str) -> bool:
    return _match_score(video, query) > 0


def find_videos_by_query(query: str) -> list:
    ranked = [
        (video, _match_score(video, query))
        for video in ordered_videos()
    ]
    ranked = [(v, s) for v, s in ranked if s > 0]
    ranked.sort(key=lambda row: (-row[1], row[0].path.order, row[0].order))
    return [v for v, _ in ranked]


def academy_search_entries(*, workspace: bool = True) -> list[dict]:
    """ورودی‌های JSON برای جستجوی سمت کلاینت."""
    entries = []
    for video in ordered_videos():
        if workspace:
            url = reverse('workspace:academy_video', kwargs={'slug': video.slug})
        else:
            url = reverse('public_academy_video', kwargs={'slug': video.slug})
        entries.append({
            'slug': video.slug,
            'title': video.title,
            'url': url,
            'path': video.path.title if video.path_id else '',
            'keywords': list(EXTRA_KEYWORDS_BY_SLUG.get(video.slug, ())),
            'searchText': _video_search_blob(video),
        })
    return entries


def admin_video_search_blob(video) -> str:
    """متن جستجو برای پنل ادمین (عنوان + slug + مسیر + کلیدواژه)."""
    parts = [video.title, video.slug]
    if video.path_id:
        parts.append(video.path.title)
    parts.extend(EXTRA_KEYWORDS_BY_SLUG.get(video.slug, ()))
    return ' '.join(p for p in parts if p)
