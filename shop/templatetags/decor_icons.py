from django import template
from django.templatetags.static import static

from shop.decor_icons import CRM_ILLUSTRATIONS, DECOR_ICONS, ICON_SIZES

register = template.Library()


@register.inclusion_tag('includes/decor_icon.html')
def decor_icon(name, size='md', alt='', boxed=False, accent='', class_name=''):
    filename = DECOR_ICONS.get(name)
    px = ICON_SIZES.get(size, ICON_SIZES['md'])
    return {
        'src': static(f'icons/{filename}') if filename else '',
        'missing': not filename,
        'width': px,
        'height': px,
        'alt': alt,
        'boxed': boxed,
        'accent': accent,
        'class_name': class_name,
        'size': size,
    }


@register.inclusion_tag('includes/decor_icon.html')
def decor_illustration(name, size='hero', alt='', class_name=''):
    filename = CRM_ILLUSTRATIONS.get(name)
    px = ICON_SIZES.get(size, ICON_SIZES['hero'])
    return {
        'src': static(f'icons/{filename}') if filename else '',
        'missing': not filename,
        'width': px,
        'height': px,
        'alt': alt,
        'boxed': False,
        'accent': '',
        'class_name': f'df-decor-illustration {class_name}'.strip(),
        'size': size,
    }
