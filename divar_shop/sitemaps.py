"""
Sitemap داینامیک برای صفحات عمومی، محصولات و بلاگ.
"""
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import Post
from shop.models import Product
from shop.seo_landings import LANDING_SLUGS, landing_url_name


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
        'public_academy': {'changefreq': 'weekly', 'priority': 0.78},
        'public_academy_playlist': {'changefreq': 'weekly', 'priority': 0.8},
        'android_tutorial': {'changefreq': 'monthly', 'priority': 0.75},
        'blog:post_list': {'changefreq': 'daily', 'priority': 0.8},
        'author_hossein_qashqaeii': {'changefreq': 'monthly', 'priority': 0.65},
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


class SeoLandingSitemap(SiteAwareSitemap):
    """لندینگ‌های سئو — Wave 1 و بعدی."""

    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return list(LANDING_SLUGS)

    def location(self, item):
        return reverse(landing_url_name(item))


class PlatformPagesSitemap(SiteAwareSitemap):
    """صفحات پلتفرم — features و solutions فاز ۱."""

    def items(self):
        from shop.platform.registry import sitemap_entries
        return sitemap_entries()

    def location(self, item):
        return item.url_path

    def changefreq(self, item):
        return item.sitemap_changefreq

    def priority(self, item):
        return item.sitemap_priority


class AcademyVideoSitemap(SiteAwareSitemap):
    """ویدیوهای عمومی آکادمی — URL جدا برای SEO."""

    changefreq = 'weekly'
    priority = 0.75

    def items(self):
        from workspace.academy.services.public_playlist_service import public_playlist_videos
        return list(public_playlist_videos())

    def location(self, obj):
        return reverse('public_academy_video', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        from datetime import datetime, timezone as dt_timezone
        from pathlib import Path

        from django.conf import settings

        mtimes = []
        if not obj.video_url:
            local = Path(settings.MEDIA_ROOT) / str(obj.file_path).strip('/') / obj.file_name
            if local.is_file():
                mtimes.append(local.stat().st_mtime)
        if obj.poster_image:
            try:
                mtimes.append(Path(obj.poster_image.path).stat().st_mtime)
            except (ValueError, OSError):
                pass
        if not mtimes:
            return None
        return datetime.fromtimestamp(min(mtimes), tz=dt_timezone.utc)


sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'blog': BlogPostSitemap,
    'landings': SeoLandingSitemap,
    'platform': PlatformPagesSitemap,
    'academy_videos': AcademyVideoSitemap,
}
