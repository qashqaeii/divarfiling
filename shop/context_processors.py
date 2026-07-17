"""
Context processors برای قالب‌ها
"""
from django.conf import settings

from divar_shop.brand import site_brand_context

from .models import Announcement, Banner


def _is_public_site_request(request) -> bool:
    """صفحات عمومی سایت — بدون میزکار و ادمین."""
    path = (request.path or '/').lower()
    blocked = ('/workspace/', '/admin/', '/api/')
    return not any(path.startswith(prefix) for prefix in blocked)


def shop_context(request):
    """افزودن متغیرهای فروشگاه به context"""
    from shop.services.notice_dismiss import filter_dismissed

    # اطلاعیه‌های فعال (بدون موارد بسته‌شده در این نشست)
    announcements = Announcement.objects.filter(is_active=True)
    visible_announcements = []
    for ann in announcements:
        if ann.is_visible():
            visible_announcements.append(ann)
    visible_announcements = filter_dismissed(
        request, visible_announcements, kind='announcement',
    )

    # بنرهای فعال
    banners = Banner.objects.filter(is_active=True)
    visible_banners = []
    for banner in banners:
        if banner.is_visible():
            visible_banners.append(banner)
    visible_banners = filter_dismissed(request, visible_banners, kind='banner')

    from shop.bot_catalog import footer_content, get_bot_product, app_download_hub_content
    from shop.services.app_downloads import build_app_download_context

    bot = get_bot_product()
    goftino_id = getattr(settings, 'GOFTINO_WIDGET_ID', '') or ''
    ctx = {
        'products': [bot] if bot else [],
        'bot_product': bot,
        'footer_content': footer_content(),
        'site_brand': site_brand_context(),
        'announcements': visible_announcements,
        'banners': visible_banners,
        'goftino_widget_id': goftino_id,
        'show_goftino': bool(goftino_id) and _is_public_site_request(request),
        'app_downloads': build_app_download_context(request),
        'app_download_hub': app_download_hub_content(),
    }
    if _is_public_site_request(request):
        from shop.platform.nav import mark_menu_active
        from shop.platform.registry.menu import platform_mega_menu
        ctx['platform_menu'] = mark_menu_active(
            platform_mega_menu(),
            getattr(request, 'path', '') or '',
        )
    return ctx

