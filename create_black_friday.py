"""
اسکریپت ایجاد اطلاعیه و بنر بلک فرایدی
"""
import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# تنظیم Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'divar_shop.settings')
django.setup()

from shop.models import Announcement, Banner

def create_black_friday_items():
    """ایجاد اطلاعیه و بنر بلک فرایدی"""
    
    # حذف اطلاعیه‌ها و بنرهای قبلی بلک فرایدی (در صورت وجود)
    Announcement.objects.filter(title__icontains='بلک فرایدی').delete()
    Banner.objects.filter(title__icontains='بلک فرایدی').delete()
    
    # ایجاد اطلاعیه بلک فرایدی
    announcement = Announcement.objects.create(
        title='تخفیف ویژه بلک فرایدی',
        content='فرصت طلایی! تا ۷۰٪ تخفیف روی تمام محصولات. این پیشنهاد محدود است و فقط تا پایان هفته معتبر می‌باشد.',
        link='/products/',
        link_text='مشاهده محصولات',
        is_active=True,
        order=1,
        show_from=timezone.now(),
        show_until=timezone.now() + timedelta(days=7)  # 7 روز معتبر
    )
    print(f'✅ اطلاعیه بلک فرایدی ایجاد شد: {announcement.title}')
    
    # ایجاد بنر متنی بلک فرایدی
    banner = Banner.objects.create(
        title='بنر بلک فرایدی',
        banner_type='text',
        text_content='<strong>بلک فرایدی ۲۰۲۵</strong><br>تخفیف‌های شگفت‌انگیز تا <strong>۷۰٪</strong><br><span style="font-size: 0.9em; opacity: 0.85;">فرصت محدود - فقط تا پایان هفته</span>',
        link='/products/',
        link_text='خرید با تخفیف',
        is_active=True,
        order=1,
        show_from=timezone.now(),
        show_until=timezone.now() + timedelta(days=7)  # 7 روز معتبر
    )
    print(f'✅ بنر بلک فرایدی ایجاد شد: {banner.title}')
    
    print('\n🎊 اطلاعیه و بنر بلک فرایدی با موفقیت ایجاد شدند!')
    print(f'📅 معتبر تا: {announcement.show_until.strftime("%Y-%m-%d %H:%M")}')

if __name__ == '__main__':
    create_black_friday_items()

