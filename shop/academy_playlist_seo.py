"""SEO و Schema.org حرفه‌ای برای آکادمی عمومی، پلی‌لیست و ویدیوها."""
from __future__ import annotations

import json
from typing import Any, Optional

from django.urls import reverse

from shop.templatetags.seo_tags import get_site_name, get_site_url
from workspace.academy.services.public_playlist_service import (
    playlist_stats,
    video_item_seo,
)

# FAQ مشترک آکادمی عمومی — برای FAQPage روی لندینگ / پلی‌لیست / آموزش
ACADEMY_PUBLIC_FAQ: list[dict[str, str]] = [
    {
        'q': 'آکادمی فایلینگ دیوار رایگان است؟',
        'a': 'بله. پلی‌لیست ویدیوهای عمومی آکادمی رایگان است و برای تماشا نیازی به خرید ربات ندارید. '
             'ثبت‌نام رایگان برای تمرین در میزکار پیشنهاد می‌شود.',
    },
    {
        'q': 'از کجا شروع کنم؟',
        'a': 'از پلی‌لیست آکادمی ویدیویی شروع کنید — اول ویدیوی معرفی، بعد مسیر شروع سریع. '
             'اگر حساب دارید، ماموریت ۱۵ دقیقه‌ای داخل میزکار را هم ببینید.',
    },
    {
        'q': 'تفاوت صفحه آکادمی با پلی‌لیست ویدیوها چیست؟',
        'a': 'صفحه آکادمی معرفی مسیرها و ارزش یادگیری است. پلی‌لیست همان ویدیوها را با پخش‌کننده '
             'و فهرست کامل نشان می‌دهد تا پشت‌سرهم تماشا کنید.',
    },
    {
        'q': 'برای تماشای ویدیوها باید لایسنس ربات بخرم؟',
        'a': 'خیر. آموزش‌های عمومی برای همه مشاوران باز است. لایسنس ربات فقط برای استخراج خودکار '
             'آگهی دیوار لازم است.',
    },
]


def _abs(request, path: str, site_url: str) -> str:
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            pass
    if path.startswith('http'):
        return path
    return f'{site_url.rstrip("/")}{path}'


def _org_node(site_url: str, site_name: str) -> dict[str, Any]:
    return {
        '@type': 'Organization',
        'name': site_name,
        'url': site_url,
        'logo': {
            '@type': 'ImageObject',
            'url': f'{site_url}/static/logo.png',
        },
    }


def _free_offer(page_url: str) -> dict[str, Any]:
    return {
        '@type': 'Offer',
        'price': 0,
        'priceCurrency': 'IRR',
        'availability': 'https://schema.org/InStock',
        'url': page_url,
        'category': 'Free',
        'description': 'آموزش ویدیویی رایگان آکادمی فایلینگ دیوار',
    }


def _faq_entities(pairs: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    items = pairs if pairs is not None else ACADEMY_PUBLIC_FAQ
    return [
        {
            '@type': 'Question',
            'name': item['q'],
            'acceptedAnswer': {'@type': 'Answer', 'text': item['a']},
        }
        for item in items
    ]


def _first_poster_url(flat_items: list[dict], site_url: str) -> str:
    for item in flat_items:
        seo = video_item_seo(item, site_url=site_url)
        poster = seo.get('poster_url') or ''
        if poster and 'logo.png' not in poster:
            return poster
    return f'{site_url}/static/logo.png'


def _video_description(item: dict, *, fallback: str = '') -> str:
    video = item['video']
    text = (video.subtitle or '').strip() or (fallback or '').strip()
    if text:
        return text[:500]
    path_title = ''
    if item.get('path') is not None:
        path_title = getattr(item['path'], 'title', '') or ''
    if path_title:
        return f'ویدیوی آموزشی «{video.title}» در مسیر {path_title} — آکادمی فایلینگ دیوار.'
    return f'ویدیوی آموزشی «{video.title}» در آکادمی رایگان فایلینگ دیوار برای مشاوران املاک.'


def _build_video_object(
    item: dict,
    *,
    site_url: str,
    page_url: str,
    org: dict[str, Any],
    item_list_id: str | None = None,
    node_id: str | None = None,
    fallback_description: str = '',
) -> dict[str, Any]:
    """Complete VideoObject for Google rich results (description + embed/content URL)."""
    video = item['video']
    seo = video_item_seo(item, site_url=site_url)
    player = item.get('player') or {}
    node: dict[str, Any] = {
        '@type': 'VideoObject',
        'name': video.title,
        'description': _video_description(item, fallback=fallback_description),
        'thumbnailUrl': seo['poster_url'],
        'uploadDate': seo['upload_date'],
        'datePublished': seo['upload_date'],
        'duration': seo['duration_iso'],
        'url': page_url,
        'embedUrl': page_url,
        'inLanguage': 'fa-IR',
        'isFamilyFriendly': True,
        'publisher': org,
        'potentialAction': {
            '@type': 'WatchAction',
            'target': page_url,
        },
    }
    if node_id:
        node['@id'] = node_id
    if item_list_id:
        node['isPartOf'] = {'@id': item_list_id}
    if player.get('available') and seo.get('embed_url'):
        content_url = seo['embed_url']
        if not content_url.startswith('http'):
            content_url = f'{site_url}{content_url}'
        node['contentUrl'] = content_url
    return node


def academy_playlist_meta(*, active_item, sections, stats) -> dict:
    if active_item:
        video = active_item['video']
        path_title = active_item['path'].title if active_item.get('path') else 'آکادمی'
        title = f'{video.title} — آموزش ویدیویی آکادمی فایلینگ دیوار'
        description = (
            (video.subtitle or '').strip()
            or f'ویدیوی آموزشی «{video.title}» در مسیر {path_title}. '
            f'پلی‌لیست رایگان آکادمی فایلینگ دیوار برای مشاوران املاک.'
        )
    else:
        title = 'پلی‌لیست آموزش ویدیویی — آکادمی فایلینگ دیوار'
        description = (
            f'{stats["video_count"]} ویدیوی آموزشی رایگان برای مشاوران املاک در '
            f'{stats["section_count"]} مسیر یادگیری — از آشنایی با پلتفرم تا شروع سریع. '
            'پلی‌لیست کامل آکادمی فایلینگ دیوار.'
        )
    keywords = (
        'آموزش فایلینگ دیوار, آکادمی مشاور املاک, ویدیو آموزشی CRM املاک, '
        'آموزش نرم افزار مشاور, پلی‌لیست آموزشی املاک, میزکار مشاور, آموزش رایگان املاک'
    )
    return {
        'meta_title': title[:70],
        'meta_description': description[:320],
        'meta_keywords': keywords,
        'og_type': 'video.other' if active_item else 'website',
    }


def academy_landing_meta(*, stats) -> dict:
    count = stats.get('video_count') or 0
    title = 'آکادمی فایلینگ دیوار — از اولین فایل تا اولین معامله'
    description = (
        f'آکادمی رایگان مشاوران املاک با {count} ویدیوی آموزشی — '
        'مسیر آشنایی، شروع سریع و یادگیری حرفه‌ای فایلینگ و CRM. '
        'بدون نیاز به لایسنس ربات برای تماشای پلی‌لیست.'
    )
    return {
        'meta_title': title,
        'meta_description': description[:320],
        'meta_keywords': (
            'آکادمی فایلینگ دیوار, آموزش مشاور املاک, ویدیو آموزشی CRM, '
            'نرم افزار مشاور املاک, میزکار مشاور, آموزش رایگان فایلینگ'
        ),
        'og_type': 'website',
    }


def academy_playlist_schema_json(request, *, active_item, sections, flat_items) -> str:
    site_url = get_site_url()
    site_name = get_site_name()
    playlist_path = reverse('public_academy_playlist')
    playlist_url = _abs(request, playlist_path, site_url)
    education_url = _abs(request, reverse('education'), site_url)
    academy_url = _abs(request, reverse('public_academy'), site_url)
    stats = playlist_stats(sections)
    org = _org_node(site_url, site_name)
    item_list_id = f'{playlist_url}#itemlist'
    course_id = f'{playlist_url}#course'

    if active_item:
        page_url = _abs(request, active_item['url'], site_url)
        page_name = active_item['video'].title
        page_desc = (
            (active_item['video'].subtitle or '').strip()
            or academy_playlist_meta(active_item=active_item, sections=sections, stats=stats)[
                'meta_description'
            ]
        )
    else:
        page_url = playlist_url
        page_name = 'پلی‌لیست آموزش ویدیویی آکادمی فایلینگ دیوار'
        page_desc = academy_playlist_meta(
            active_item=None, sections=sections, stats=stats
        )['meta_description']

    breadcrumb_items = [
        {'@type': 'ListItem', 'position': 1, 'name': 'خانه', 'item': site_url},
        {'@type': 'ListItem', 'position': 2, 'name': 'آموزش', 'item': education_url},
        {'@type': 'ListItem', 'position': 3, 'name': 'آکادمی', 'item': academy_url},
        {'@type': 'ListItem', 'position': 4, 'name': 'پلی‌لیست ویدیویی', 'item': playlist_url},
    ]
    if active_item:
        breadcrumb_items.append({
            '@type': 'ListItem',
            'position': 5,
            'name': active_item['video'].title,
            'item': page_url,
        })

    item_list_elements = []
    for pos, item in enumerate(flat_items, start=1):
        item_url = _abs(request, item['url'], site_url)
        video_obj = _build_video_object(
            item,
            site_url=site_url,
            page_url=item_url,
            org=org,
            item_list_id=item_list_id,
        )
        item_list_elements.append({
            '@type': 'ListItem',
            'position': pos,
            'name': item['video'].title,
            'url': item_url,
            'item': video_obj,
        })

    # One Course per learning path + umbrella course
    course_nodes: list[dict[str, Any]] = [
        {
            '@type': 'Course',
            '@id': course_id,
            'name': 'آکادمی فایلینگ دیوار — پلی‌لیست عمومی',
            'description': (
                f'{stats["video_count"]} ویدیوی آموزشی رایگان برای مشاوران املاک '
                f'در {stats["section_count"]} مسیر یادگیری.'
            ),
            'url': playlist_url,
            'provider': org,
            'inLanguage': 'fa-IR',
            'isAccessibleForFree': True,
            'offers': _free_offer(playlist_url),
            'hasCourseInstance': {
                '@type': 'CourseInstance',
                'courseMode': 'online',
                'courseWorkload': f'PT{stats["total_minutes"]}M',
                'inLanguage': 'fa-IR',
            },
            'about': ['فایلینگ املاک', 'CRM مشاور', 'آموزش دیوار'],
        }
    ]
    for section in sections:
        path = section['path']
        first = section['videos'][0] if section['videos'] else None
        path_url = _abs(request, first['url'], site_url) if first else playlist_url
        course_nodes.append({
            '@type': 'Course',
            '@id': f'{playlist_url}#course-{path.slug}',
            'name': path.title,
            'description': (path.description or path.title)[:280],
            'url': path_url,
            'provider': org,
            'inLanguage': 'fa-IR',
            'isAccessibleForFree': True,
            'offers': _free_offer(path_url),
            'isPartOf': {'@id': course_id},
            'hasCourseInstance': {
                '@type': 'CourseInstance',
                'courseMode': 'online',
                'courseWorkload': f'PT{section["total_minutes"]}M',
            },
        })

    webpage_type = 'CollectionPage' if not active_item else 'WebPage'
    graph: list[dict[str, Any]] = [
        {
            '@type': webpage_type,
            '@id': f'{page_url}#webpage',
            'url': page_url,
            'name': page_name,
            'description': page_desc,
            'inLanguage': 'fa-IR',
            'isPartOf': {'@type': 'WebSite', 'name': site_name, 'url': site_url},
            'publisher': org,
            'primaryImageOfPage': {
                '@type': 'ImageObject',
                'url': (
                    video_item_seo(active_item, site_url=site_url)['poster_url']
                    if active_item
                    else _first_poster_url(flat_items, site_url)
                ),
            },
            'mainEntity': {'@id': item_list_id if not active_item else f'{page_url}#video'},
        },
        {
            '@type': 'BreadcrumbList',
            '@id': f'{page_url}#breadcrumb',
            'itemListElement': breadcrumb_items,
        },
        {
            '@type': 'ItemList',
            '@id': item_list_id,
            'name': 'پلی‌لیست آموزش ویدیویی آکادمی فایلینگ دیوار',
            'description': (
                f'{stats["video_count"]} ویدیوی آموزشی برای مشاوران املاک '
                f'در {stats["section_count"]} مسیر یادگیری.'
            ),
            'numberOfItems': stats['video_count'],
            'itemListOrder': 'https://schema.org/ItemListOrderAscending',
            'url': playlist_url,
            'itemListElement': item_list_elements,
        },
        *course_nodes,
        {
            '@type': 'FAQPage',
            '@id': f'{page_url}#faq',
            'url': page_url,
            'inLanguage': 'fa-IR',
            'mainEntity': _faq_entities(),
        },
    ]

    if active_item:
        graph.append(
            _build_video_object(
                active_item,
                site_url=site_url,
                page_url=page_url,
                org=org,
                item_list_id=item_list_id,
                node_id=f'{page_url}#video',
                fallback_description=page_desc,
            )
        )

    payload = {'@context': 'https://schema.org', '@graph': graph}
    return json.dumps(payload, ensure_ascii=False)


def academy_landing_schema_json(request, *, sections, flat_items) -> str:
    site_url = get_site_url()
    site_name = get_site_name()
    page_url = _abs(request, reverse('public_academy'), site_url)
    playlist_url = _abs(request, reverse('public_academy_playlist'), site_url)
    education_url = _abs(request, reverse('education'), site_url)
    stats = playlist_stats(sections)
    meta = academy_landing_meta(stats=stats)
    org = _org_node(site_url, site_name)
    poster = _first_poster_url(flat_items, site_url)

    path_list = []
    for pos, section in enumerate(sections, start=1):
        first = section['videos'][0] if section['videos'] else None
        path_list.append({
            '@type': 'ListItem',
            'position': pos,
            'name': section['path'].title,
            'url': _abs(request, first['url'], site_url) if first else playlist_url,
            'description': f'{section["video_count"]} ویدیو · حدود {section["total_minutes"]} دقیقه',
        })

    graph = [
        {
            '@type': 'WebPage',
            '@id': f'{page_url}#webpage',
            'url': page_url,
            'name': meta['meta_title'],
            'description': meta['meta_description'],
            'inLanguage': 'fa-IR',
            'isPartOf': {'@type': 'WebSite', 'name': site_name, 'url': site_url},
            'publisher': org,
            'primaryImageOfPage': {'@type': 'ImageObject', 'url': poster},
            'mainEntity': {'@id': f'{page_url}#course'},
        },
        {
            '@type': 'BreadcrumbList',
            '@id': f'{page_url}#breadcrumb',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'خانه', 'item': site_url},
                {'@type': 'ListItem', 'position': 2, 'name': 'آموزش', 'item': education_url},
                {'@type': 'ListItem', 'position': 3, 'name': 'آکادمی فایلینگ دیوار', 'item': page_url},
            ],
        },
        {
            '@type': 'Course',
            '@id': f'{page_url}#course',
            'name': 'آکادمی فایلینگ دیوار',
            'description': meta['meta_description'],
            'url': page_url,
            'provider': org,
            'inLanguage': 'fa-IR',
            'isAccessibleForFree': True,
            'offers': _free_offer(page_url),
            'hasCourseInstance': {
                '@type': 'CourseInstance',
                'courseMode': 'online',
                'courseWorkload': f'PT{stats["total_minutes"]}M',
            },
            'about': ['فایلینگ املاک', 'CRM مشاور', 'آموزش مشاور املاک'],
        },
        {
            '@type': 'ItemList',
            '@id': f'{page_url}#paths',
            'name': 'مسیرهای آموزشی عمومی آکادمی',
            'numberOfItems': len(path_list),
            'itemListElement': path_list,
            'url': playlist_url,
        },
        {
            '@type': 'FAQPage',
            '@id': f'{page_url}#faq',
            'url': page_url,
            'inLanguage': 'fa-IR',
            'mainEntity': _faq_entities(),
        },
    ]
    return json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False)


def education_hub_schema_json(request, *, faq_pairs: Optional[list[dict[str, str]]] = None) -> str:
    """WebPage + Breadcrumb + FAQ برای /amoozesh/ با لینک به آکادمی."""
    site_url = get_site_url()
    site_name = get_site_name()
    page_url = _abs(request, reverse('education'), site_url)
    academy_url = _abs(request, reverse('public_academy'), site_url)
    playlist_url = _abs(request, reverse('public_academy_playlist'), site_url)
    org = _org_node(site_url, site_name)

    pairs = faq_pairs or []
    faq_main = _faq_entities(pairs) if pairs else _faq_entities()

    graph = [
        {
            '@type': 'WebPage',
            '@id': f'{page_url}#webpage',
            'url': page_url,
            'name': 'آموزش — مرکز یادگیری فایلینگ دیوار',
            'description': (
                'آکادمی ویدیویی رایگان، مسیرهای یادگیری CRM، ربات استخراج دیوار، '
                'فایلینگ و تحلیل بازار برای مشاوران املاک.'
            ),
            'inLanguage': 'fa-IR',
            'isPartOf': {'@type': 'WebSite', 'name': site_name, 'url': site_url},
            'publisher': org,
            'significantLink': [academy_url, playlist_url],
        },
        {
            '@type': 'BreadcrumbList',
            '@id': f'{page_url}#breadcrumb',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'خانه', 'item': site_url},
                {'@type': 'ListItem', 'position': 2, 'name': 'آموزش', 'item': page_url},
            ],
        },
        {
            '@type': 'ItemList',
            '@id': f'{page_url}#learning-hub',
            'name': 'مسیرهای یادگیری فایلینگ دیوار',
            'itemListElement': [
                {
                    '@type': 'ListItem',
                    'position': 1,
                    'name': 'آکادمی فایلینگ دیوار',
                    'url': academy_url,
                },
                {
                    '@type': 'ListItem',
                    'position': 2,
                    'name': 'پلی‌لیست ویدیویی آکادمی',
                    'url': playlist_url,
                },
            ],
        },
        {
            '@type': 'FAQPage',
            '@id': f'{page_url}#faq',
            'url': page_url,
            'inLanguage': 'fa-IR',
            'mainEntity': faq_main,
        },
    ]
    return json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False)
