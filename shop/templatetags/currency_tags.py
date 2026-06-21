"""
Template tags برای فرمت کردن قیمت و کارنسی
"""
import re

from django import template
from shop.models import ProductRating, ProductReview

register = template.Library()


@register.filter(name='currency')
def currency(value):
    """
    فرمت کردن قیمت با جداکننده هزارگان (کاما)
    مثال: 1000000 -> 1,000,000
    """
    if value is None:
        return '0'
    
    try:
        # تبدیل به عدد صحیح
        num = int(float(value))
        # فرمت کردن با جداکننده هزارگان
        return f"{num:,}"
    except (ValueError, TypeError):
        return str(value)


@register.filter(name='toman')
def toman(value):
    """
    فرمت کردن قیمت با جداکننده هزارگان و واحد تومان
    مثال: 1000000 -> 1,000,000 تومان
    """
    if value is None:
        return '0 تومان'
    
    try:
        # تبدیل به عدد صحیح
        num = int(float(value))
        # فرمت کردن با جداکننده هزارگان
        formatted = f"{num:,}"
        return f"{formatted} تومان"
    except (ValueError, TypeError):
        return f"{value} تومان"


@register.filter(name='card_format')
def card_format(value):
    """گروه‌بندی شماره کارت: 6037 9919 3596 2708"""
    if not value:
        return ''
    digits = re.sub(r'\D', '', str(value))
    return ' '.join(digits[i:i + 4] for i in range(0, len(digits), 4))


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    دریافت مقدار از دیکشنری با کلید
    مثال: {{ rating_percentages|get_item:5 }}
    """
    if dictionary is None:
        return 0
    try:
        return dictionary.get(key, 0)
    except (AttributeError, TypeError):
        return 0


@register.filter(name='get_average_rating')
def get_average_rating(product):
    """
    دریافت میانگین امتیاز محصول
    مثال: {{ product|get_average_rating }}
    """
    if product is None:
        return 0
    try:
        return ProductRating.get_average_rating(product)
    except Exception:
        return 0


@register.filter(name='get_rating_count')
def get_rating_count(product):
    """
    دریافت تعداد امتیازهای محصول
    مثال: {{ product|get_rating_count }}
    """
    if product is None:
        return 0
    try:
        return ProductRating.get_rating_count(product)
    except Exception:
        return 0


@register.filter(name='get_reviews_count')
def get_reviews_count(product):
    """
    دریافت تعداد نظرات تایید شده محصول
    مثال: {{ product|get_reviews_count }}
    """
    if product is None:
        return 0
    try:
        return ProductReview.objects.filter(product=product, is_approved=True).count()
    except Exception:
        return 0
