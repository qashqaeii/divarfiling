"""
Template tags برای Breadcrumbs
"""
from django import template
from django.urls import reverse, NoReverseMatch
from django.utils.safestring import mark_safe

register = template.Library()


@register.inclusion_tag('shop/breadcrumbs.html', takes_context=True)
def breadcrumbs(context, **kwargs):
    """
    تولید Breadcrumbs برای SEO و Navigation
    
    Usage:
        {% load breadcrumbs %}
        {% breadcrumbs %}
    """
    request = context.get('request')
    items = kwargs.get('items', [])
    
    # اگر items داده نشده، از context استفاده کن
    if not items:
        items = context.get('breadcrumbs', [])
    
    # اگر هنوز خالی است، از URL فعلی بساز
    if not items and request:
        path_parts = request.path.strip('/').split('/')
        items = []
        
        # صفحه اصلی
        items.append({
            'name': 'خانه',
            'url': '/'
        })
        
        # بخش‌های URL
        current_path = ''
        for part in path_parts:
            if part:
                current_path += '/' + part
                # نام فارسی برای بخش‌های مختلف
                name_map = {
                    'products': 'محصولات',
                    'about': 'درباره ما',
                    'contact': 'تماس با ما',
                    'terms': 'قوانین و مقررات',
                    'privacy': 'حریم خصوصی',
                    'license-guide': 'راهنمای فعال‌سازی',
                    'dashboard': 'داشبورد',
                    'profile': 'پروفایل',
                    'login': 'ورود',
                    'register': 'ثبت‌نام',
                }
                
                name = name_map.get(part, part.replace('-', ' ').title())
                
                # اگر آخرین بخش است، active نکن
                is_last = part == path_parts[-1]
                items.append({
                    'name': name,
                    'url': current_path if not is_last else None,
                    'active': is_last
                })
    
    return {
        'items': items,
    }

