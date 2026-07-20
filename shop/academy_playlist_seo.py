"""SEO و Schema.org برای پلی‌لیست عمومی آکادمی."""
from __future__ import annotations

import json

from django.urls import reverse

from shop.templatetags.seo_tags import get_site_name, get_site_url
from workspace.academy.services.public_playlist_service import (
    playlist_stats,
    video_item_seo,
)


def academy_playlist_meta(*, active_item, sections, stats) -> dict:
    if active_item:
        video = active_item['video']
        title = f'{video.title} — آموزش ویدیویی آکادمی فایلینگ دیوار'
        description = (
            video.subtitle
            or f'ویدیوی آموزشی {video.title} در مسیر {active_item["path"].title}. '
            f'آکادمی رایگان مشاوران املاک — فایلینگ دیوار.'
        )
    else:
        title = 'پلی‌لیست آموزش ویدیویی — آکادمی فایلینگ دیوار'
        description = (
            f'{stats["video_count"]} ویدیوی آموزشی رایگان برای مشاوران املاک — '
            'از آشنایی با پلتفرم تا شروع سریع. پلی‌لیست کامل آکادمی فایلینگ دیوار.'
        )
    keywords = (
        'آموزش فایلینگ دیوار, آکادمی مشاور املاک, ویدیو آموزشی CRM املاک, '
        'آموزش نرم افزار مشاور, پلی‌لیست آموزشی املاک, میزکار مشاور'
    )
    return {
        'meta_title': title,
        'meta_description': description[:320],
        'meta_keywords': keywords,
        'og_type': 'video.other' if active_item else 'website',
    }


def academy_playlist_schema_json(request, *, active_item, sections, flat_items) -> str:
    site_url = get_site_url()
    site_name = get_site_name()
    playlist_url = f'{site_url}{reverse("public_academy_playlist")}'
    if request:
        playlist_url = request.build_absolute_uri(reverse('public_academy_playlist'))

    stats = playlist_stats(sections)

    if active_item:
        page_url = f'{site_url}{active_item["url"]}'
        if request:
            page_url = request.build_absolute_uri(active_item['url'])
        page_name = active_item['video'].title
        page_desc = active_item['video'].subtitle or stats['paths'][0] if stats['paths'] else ''
    else:
        page_url = playlist_url
        page_name = 'پلی‌لیست آموزش ویدیویی آکادمی'
        page_desc = academy_playlist_meta(active_item=None, sections=sections, stats=stats)['meta_description']

    breadcrumb_items = [
        {'@type': 'ListItem', 'position': 1, 'name': 'خانه', 'item': site_url},
        {'@type': 'ListItem', 'position': 2, 'name': 'آموزش', 'item': f'{site_url}{reverse("education")}'},
        {'@type': 'ListItem', 'position': 3, 'name': 'آکادمی ویدیویی', 'item': playlist_url},
    ]
    if active_item:
        breadcrumb_items.append({
            '@type': 'ListItem',
            'position': 4,
            'name': active_item['video'].title,
            'item': page_url,
        })

    item_list_elements = []
    for pos, item in enumerate(flat_items, start=1):
        item_url = f'{site_url}{item["url"]}'
        item_list_elements.append({
            '@type': 'ListItem',
            'position': pos,
            'name': item['video'].title,
            'url': item_url,
        })

    graph = [
        {
            '@type': 'WebPage',
            '@id': f'{page_url}#webpage',
            'url': page_url,
            'name': page_name,
            'description': page_desc,
            'inLanguage': 'fa-IR',
            'isPartOf': {'@type': 'WebSite', 'name': site_name, 'url': site_url},
        },
        {
            '@type': 'BreadcrumbList',
            'itemListElement': breadcrumb_items,
        },
        {
            '@type': 'ItemList',
            'name': 'پلی‌لیست آموزش ویدیویی آکادمی فایلینگ دیوار',
            'description': (
                f'{stats["video_count"]} ویدیوی آموزشی برای مشاوران املاک '
                f'در {stats["section_count"]} مسیر یادگیری.'
            ),
            'numberOfItems': stats['video_count'],
            'itemListElement': item_list_elements,
        },
        {
            '@type': 'Course',
            'name': 'آکادمی فایلینگ دیوار — مسیر آشنایی',
            'description': 'ویدیوهای آموزشی رایگان برای مشاوران املاک',
            'provider': {'@type': 'Organization', 'name': site_name, 'url': site_url},
            'inLanguage': 'fa-IR',
            'hasCourseInstance': {
                '@type': 'CourseInstance',
                'courseMode': 'online',
                'courseWorkload': f'PT{stats["total_minutes"]}M',
            },
        },
    ]

    if active_item:
        seo = video_item_seo(active_item, site_url=site_url)
        video = active_item['video']
        video_node = {
            '@type': 'VideoObject',
            '@id': f'{page_url}#video',
            'name': video.title,
            'description': video.subtitle or page_desc,
            'thumbnailUrl': seo['poster_url'],
            'duration': seo['duration_iso'],
            'embedUrl': page_url,
            'inLanguage': 'fa-IR',
            'isPartOf': {'@type': 'ItemList', 'name': 'پلی‌لیست آکادمی'},
            'publisher': {
                '@type': 'Organization',
                'name': site_name,
                'logo': {'@type': 'ImageObject', 'url': f'{site_url}/static/logo.png'},
            },
        }
        if active_item['player'].get('available') and seo['embed_url']:
            content_url = seo['embed_url']
            if not content_url.startswith('http'):
                content_url = f'{site_url}{content_url}'
            video_node['contentUrl'] = content_url
        graph.append(video_node)

    payload = {'@context': 'https://schema.org', '@graph': graph}
    return json.dumps(payload, ensure_ascii=False)
