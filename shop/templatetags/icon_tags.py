from django import template

from shop.lucide_icons import render_lucide_svg, resolve_lucide_name

register = template.Library()


@register.simple_tag
def icon(name, size='md', class_name=''):
    """Render a Lucide SVG icon: {% icon "upload" size="nav" %}."""
    if not resolve_lucide_name(name):
        return ''
    return render_lucide_svg(name, size=size, class_name=class_name)
