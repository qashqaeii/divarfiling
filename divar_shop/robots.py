"""
robots.txt داینامیک — مسیرهای خصوصی را از ایندکس خارج می‌کند.
"""
from django.conf import settings
from django.http import HttpResponse


def robots_txt(request):
    site_url = getattr(settings, 'SITE_URL', 'https://divarfiling.ir').rstrip('/')

    lines = [
        'User-agent: *',
        'Allow: /',
        '',
        'Disallow: /admin/',
        'Disallow: /accounts/',
        'Disallow: /workspace/',
        'Disallow: /api/',
        'Disallow: /payment/',
        'Disallow: /affiliate/',
        'Disallow: /products/*/buy/',
        'Disallow: /products/*/apply-discount/',
        'Disallow: /products/*/rating/',
        'Disallow: /products/*/review/',
        'Disallow: /reviews/',
        '',
        f'Sitemap: {site_url}/sitemap.xml',
    ]

    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
