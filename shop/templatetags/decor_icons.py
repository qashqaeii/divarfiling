from django import template
from django.templatetags.static import static

from shop.decor_icons import CRM_ILLUSTRATIONS, DECOR_ICONS, ICON_SIZES
from shop.lucide_icons import icon_pixel_size, render_lucide_svg, resolve_lucide_name

register = template.Library()


@register.inclusion_tag('includes/decor_icon.html')
def decor_icon(name, size='md', alt='', boxed=False, accent='', class_name=''):
    lucide_name = resolve_lucide_name(name)
    return {
        'svg_html': render_lucide_svg(name, size=size, class_name=class_name),
        'missing': not lucide_name,
        'width': icon_pixel_size(size),
        'height': icon_pixel_size(size),
        'alt': alt,
        'boxed': boxed,
        'accent': accent,
        'class_name': class_name,
        'size': size,
        'legacy_png': DECOR_ICONS.get(name, ''),
    }


@register.inclusion_tag('includes/decor_icon.html')
def decor_illustration(name, size='hero', alt='', class_name=''):
    """CRM hero illustrations remain legacy PNG assets."""
    filename = CRM_ILLUSTRATIONS.get(name)
    px = ICON_SIZES.get(size, ICON_SIZES['hero'])
    return {
        'svg_html': '',
        'src': static(f'icons/{filename}') if filename else '',
        'use_legacy_img': True,
        'missing': not filename,
        'width': px,
        'height': px,
        'alt': alt,
        'boxed': False,
        'accent': '',
        'class_name': f'df-decor-illustration {class_name}'.strip(),
        'size': size,
        'legacy_png': filename or '',
    }
