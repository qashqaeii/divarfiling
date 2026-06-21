"""
Context processors برای قالب‌ها
"""
from django.conf import settings
from .models import Product, Announcement, Banner
from django.utils import timezone


from divar_shop.brand import site_brand_context


def _is_public_site_request(request) -> bool:
    """صفحات عمومی سایت — بدون میزکار و ادمین."""
    path = (request.path or '/').lower()
    blocked = ('/workspace/', '/admin/', '/api/')
    return not any(path.startswith(prefix) for prefix in blocked)


def shop_context(request):
    """افزودن متغیرهای فروشگاه به context"""
    now = timezone.now()
    
    # اطلاعیه‌های فعال
    announcements = Announcement.objects.filter(is_active=True)
    visible_announcements = []
    for ann in announcements:
        if ann.is_visible():
            visible_announcements.append(ann)
    
    # بنرهای فعال
    banners = Banner.objects.filter(is_active=True)
    visible_banners = []
    for banner in banners:
        if banner.is_visible():
            visible_banners.append(banner)
    
    from shop.bot_catalog import footer_content, get_bot_product

    bot = get_bot_product()
    goftino_id = getattr(settings, 'GOFTINO_WIDGET_ID', '') or ''
    return {
        'products': [bot] if bot else [],
        'bot_product': bot,
        'footer_content': footer_content(),
        'site_brand': site_brand_context(),
        'announcements': visible_announcements,
        'banners': visible_banners,
        'goftino_widget_id': goftino_id,
        'show_goftino': bool(goftino_id) and _is_public_site_request(request),
    }

