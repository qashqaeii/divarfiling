"""
Template tags برای SEO و Meta Tags
"""
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
from django.urls import reverse
import json

register = template.Library()


def get_site_url():
    """دریافت URL پایه سایت"""
    if hasattr(settings, 'SITE_URL'):
        return settings.SITE_URL.rstrip('/')
    return 'https://divarfiling.ir'  # پیش‌فرض


def get_site_name():
    """دریافت نام سایت"""
    return getattr(settings, 'SITE_NAME', 'فایلینگ دیوار')


@register.inclusion_tag('shop/seo_meta.html', takes_context=True)
def seo_meta(context, **kwargs):
    """
    تولید Meta Tags کامل برای SEO
    
    Usage:
        {% load seo_tags %}
        {% seo_meta title="عنوان صفحه" description="توضیحات" %}
    """
    request = context.get('request')
    site_url = get_site_url()
    site_name = get_site_name()
    
    # دریافت مقادیر از context یا kwargs
    title = kwargs.get('title') or context.get('meta_title') or context.get('title', '')
    if not title:
        title = context.get('page_title', get_site_name())
    
    description = kwargs.get('description') or context.get('meta_description') or context.get('description', '')
    if not description:
        description = 'فروشگاه رسمی ربات هوشمند تحلیل املاک دیوار. ابزاری قدرتمند برای استخراج و تحلیل داده‌های املاک.'
    
    keywords = kwargs.get('keywords') or context.get('meta_keywords') or 'ربات دیوار, تحلیل املاک, استخراج داده, نرم‌افزار املاک'
    
    # تصویر برای Open Graph
    image = kwargs.get('image') or context.get('meta_image') or context.get('og_image')
    if image:
        if not image.startswith('http'):
            image = f"{site_url}{image}"
    else:
        image = f"{site_url}/static/images/og-default.jpg"
    
    # URL صفحه فعلی
    if request:
        current_url = request.build_absolute_uri()
    else:
        current_url = site_url
    
    # نوع محتوا (og:type)
    og_type = kwargs.get('og_type') or context.get('og_type', 'website')
    
    # اطلاعات اضافی
    author = kwargs.get('author') or context.get('author', site_name)
    published_time = kwargs.get('published_time') or context.get('published_time')
    modified_time = kwargs.get('modified_time') or context.get('modified_time')
    
    # Schema.org data
    schema_data = kwargs.get('schema') or context.get('schema_data')
    
    return {
        'title': title,
        'description': description,
        'keywords': keywords,
        'image': image,
        'url': current_url,
        'site_name': site_name,
        'site_url': site_url,
        'og_type': og_type,
        'author': author,
        'published_time': published_time,
        'modified_time': modified_time,
        'schema_data': schema_data,
        'locale': 'fa_IR',
    }


@register.simple_tag
def schema_organization():
    """Schema.org برای Organization"""
    from divar_shop.brand import site_brand_context

    site_url = get_site_url()
    site_name = get_site_name()
    brand = site_brand_context()

    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": site_name,
        "url": site_url,
        "logo": f"{site_url}/static/logo.png",
        "founder": {
            "@type": "Person",
            "name": brand["creator_name"],
        },
        "sameAs": [
            brand["creator_telegram_url"],
        ],
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": brand["creator_phone_tel"],
            "email": brand["support_email"],
            "contactType": "پشتیبانی",
            "areaServed": "IR",
            "availableLanguage": "Persian",
        },
    }

    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')


@register.simple_tag
def schema_product(product):
    """Schema.org برای Product"""
    if not product:
        return ''
    
    site_url = get_site_url()
    
    # دریافت قیمت
    price = None
    price_currency = 'IRR'
    if hasattr(product, 'plans') and product.plans.exists():
        plan = product.plans.first()
        price = float(plan.price)
    
    # دریافت تصویر
    image_url = None
    if hasattr(product, 'media') and product.media.exists():
        media = product.media.first()
        if media:
            image_url = f"{site_url}{media.file.url}"
    
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.title,
        "description": getattr(product, 'short_description', '') or str(product.description)[:200],
        "image": image_url or f"{site_url}/static/images/product-default.jpg",
        "url": f"{site_url}{product.get_absolute_url()}" if hasattr(product, 'get_absolute_url') else f"{site_url}/products/{product.slug}/",
    }
    
    if price:
        schema["offers"] = {
            "@type": "Offer",
            "price": price,
            "priceCurrency": price_currency,
            "availability": "https://schema.org/InStock",
            "url": f"{site_url}{product.get_absolute_url()}" if hasattr(product, 'get_absolute_url') else f"{site_url}/products/{product.slug}/",
        }
    
    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')


@register.simple_tag
def schema_breadcrumb(items):
    """Schema.org برای BreadcrumbList"""
    if not items:
        return ''
    
    site_url = get_site_url()
    
    breadcrumb_items = []
    for idx, item in enumerate(items, 1):
        breadcrumb_items.append({
            "@type": "ListItem",
            "position": idx,
            "name": item.get('name', ''),
            "item": item.get('url', '') if item.get('url', '').startswith('http') else f"{site_url}{item.get('url', '')}"
        })
    
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumb_items
    }
    
    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')


@register.simple_tag(takes_context=True)
def schema_article(context, post, request=None):
    """Schema.org Article برای صفحه بلاگ."""
    if not post:
        return ''
    req = request or context.get('request')
    site_url = get_site_url()
    if req:
        page_url = req.build_absolute_uri()
    else:
        page_url = post.get_absolute_url()
        if not page_url.startswith('http'):
            page_url = f'{site_url}{page_url}'

    from django.utils.html import strip_tags

    description = (post.excerpt or strip_tags(post.content or ''))[:300]
    author_name = post.author.get_full_name() or post.author.username

    schema = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': post.title,
        'description': description,
        'author': {'@type': 'Person', 'name': author_name},
        'publisher': {
            '@type': 'Organization',
            'name': get_site_name(),
            'logo': {'@type': 'ImageObject', 'url': f'{site_url}/static/logo.png'},
        },
        'mainEntityOfPage': {'@type': 'WebPage', '@id': page_url},
        'inLanguage': 'fa-IR',
    }
    if post.published_at:
        schema['datePublished'] = post.published_at.isoformat()
    if post.updated_at:
        schema['dateModified'] = post.updated_at.isoformat()
    if post.featured_image:
        try:
            img_url = post.featured_image.url
            schema['image'] = req.build_absolute_uri(img_url) if req else f'{site_url}{img_url}'
        except Exception:
            pass

    return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')

