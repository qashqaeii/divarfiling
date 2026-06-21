"""
Sitemap داینامیک برای صفحات عمومی، محصولات و بلاگ.
"""
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import Post
from shop.models import Product


def _site_protocol() -> str:
    site_url = getattr(settings, 'SITE_URL', 'https://divarfiling.ir')
    return urlparse(site_url).scheme or 'https'


class SiteAwareSitemap(Sitemap):
    """پروتکل و دامنه از SITE_URL و django.contrib.sites."""

    protocol = None

    def get_protocol(self, protocol=None):
        if protocol is not None:
            return protocol
        return _site_protocol()


class StaticViewSitemap(SiteAwareSitemap):

    STATIC_PAGES = {
        'home': {'changefreq': 'daily', 'priority': 1.0},
        'product_list': {'changefreq': 'weekly', 'priority': 0.9},
        'about': {'changefreq': 'monthly', 'priority': 0.7},
        'contact': {'changefreq': 'monthly', 'priority': 0.6},
        'terms': {'changefreq': 'yearly', 'priority': 0.4},
        'license_guide': {'changefreq': 'monthly', 'priority': 0.7},
        'education': {'changefreq': 'monthly', 'priority': 0.7},
        'blog:post_list': {'changefreq': 'daily', 'priority': 0.8},
    }

    def items(self):
        return list(self.STATIC_PAGES.keys())

    def location(self, item):
        return reverse(item)

    def changefreq(self, item):
        return self.STATIC_PAGES[item]['changefreq']

    def priority(self, item):
        return self.STATIC_PAGES[item]['priority']

    def lastmod(self, item):
        if item == 'blog:post_list':
            latest = Post.objects.filter(is_published=True).order_by('-updated_at').first()
            return latest.updated_at if latest else None
        if item == 'product_list':
            latest = Product.objects.filter(is_active=True).order_by('-updated_at').first()
            return latest.updated_at if latest else None
        return None


class ProductSitemap(SiteAwareSitemap):
    """صفحات جزئیات محصولات فعال."""

    changefreq = 'weekly'
    priority = 0.85

    def items(self):
        return Product.objects.filter(is_active=True).order_by('order', '-updated_at')

    def lastmod(self, obj):
        return obj.updated_at


class BlogPostSitemap(SiteAwareSitemap):
    """مقالات منتشرشده."""

    changefreq = 'monthly'
    priority = 0.75

    def items(self):
        return Post.objects.filter(is_published=True).order_by('-published_at', '-updated_at')

    def lastmod(self, obj):
        return obj.published_at or obj.updated_at


sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'blog': BlogPostSitemap,
}
