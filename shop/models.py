"""
مدل‌های فروشگاه
"""
import uuid
import json
import re
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()


def persian_to_slug(text):
    """
    تبدیل متن فارسی به اسلاگ معتبر
    """
    if not text:
        return ''
    
    # جدول تبدیل کاراکترهای فارسی به انگلیسی
    persian_to_english = {
        'ا': 'a', 'آ': 'a', 'أ': 'a', 'إ': 'a', 'ء': 'a',
        'ب': 'b', 'پ': 'p', 'ت': 't', 'ث': 's', 'ج': 'j',
        'چ': 'ch', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'z',
        'ر': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's', 'ش': 'sh',
        'ص': 's', 'ض': 'z', 'ط': 't', 'ظ': 'z', 'ع': 'a',
        'غ': 'gh', 'ف': 'f', 'ق': 'gh', 'ک': 'k', 'گ': 'g',
        'ل': 'l', 'م': 'm', 'ن': 'n', 'و': 'v', 'ه': 'h',
        'ی': 'y', 'ي': 'y', 'ئ': 'y', 'ة': 'h', 'ك': 'k',
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    }
    
    # تبدیل کاراکترهای فارسی
    result = ''
    for char in text:
        if char in persian_to_english:
            result += persian_to_english[char]
        elif char.isalnum() or char in ['-', '_', ' ']:
            result += char
        else:
            result += ' '
    
    # استفاده از slugify برای تبدیل به فرمت استاندارد
    result = slugify(result)
    
    # حذف خط فاصله‌های اضافی
    result = re.sub(r'-+', '-', result).strip('-')
    
    return result


class Product(models.Model):
    """مدل محصول"""
    title = models.CharField(max_length=200, verbose_name='عنوان')
    slug = models.SlugField(unique=True, verbose_name='نامک')
    description = models.TextField(verbose_name='توضیحات')
    short_description = models.CharField(max_length=300, blank=True, verbose_name='توضیح کوتاه')
    features = models.JSONField(default=list, verbose_name='امکانات')
    video_url = models.URLField(blank=True, null=True, verbose_name='لینک ویدئو')
    download_file = models.FileField(upload_to='products/', blank=True, null=True, verbose_name='فایل دانلود')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    repeat_purchase_discount = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        validators=[MinValueValidator(0)],
        verbose_name='تخفیف خریدهای بعدی (%)',
        help_text='درصد تخفیف برای خریدهای دوم به بعد این محصول'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    order = models.IntegerField(default=0, verbose_name='ترتیب نمایش')
    
    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """ذخیره محصول با تولید خودکار اسلاگ از عنوان"""
        # اگر اسلاگ خالی است یا title تغییر کرده، از عنوان تولید کن
        if not self.slug:
            # تولید اسلاگ از عنوان
            base_slug = persian_to_slug(self.title)
            if not base_slug:
                base_slug = 'product'
            
            # بررسی یکتایی اسلاگ
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk if self.pk else None).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            
            self.slug = slug
        elif self.pk:
            # اگر slug وجود دارد اما title تغییر کرده، بررسی کن که آیا slug از title قدیمی تولید شده یا نه
            try:
                old_product = Product.objects.get(pk=self.pk)
                if old_product.title != self.title:
                    # اگر title تغییر کرده، slug را از title جدید تولید کن
                    old_slug_from_title = persian_to_slug(old_product.title)
                    if old_slug_from_title and self.slug.startswith(old_slug_from_title):
                        # slug از title قدیمی تولید شده بود، پس آن را به‌روز کن
                        base_slug = persian_to_slug(self.title)
                        if not base_slug:
                            base_slug = 'product'
                        
                        # بررسی یکتایی اسلاگ
                        slug = base_slug
                        counter = 1
                        while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                            slug = f'{base_slug}-{counter}'
                            counter += 1
                        
                        self.slug = slug
            except Product.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        """دریافت URL محصول"""
        from django.urls import reverse
        return reverse('product_detail', kwargs={'slug': self.slug})


class ProductMedia(models.Model):
    """رسانه‌های محصول (تصویر/ویدئو)"""
    MEDIA_TYPES = [
        ('image', 'تصویر'),
        ('video', 'ویدئو'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='media', verbose_name='محصول')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image', verbose_name='نوع رسانه')
    file = models.FileField(upload_to='products/media/', verbose_name='فایل')
    alt_text = models.CharField(max_length=200, blank=True, verbose_name='متن جایگزین')
    order = models.IntegerField(default=0, verbose_name='ترتیب')
    
    class Meta:
        verbose_name = 'رسانه محصول'
        verbose_name_plural = 'رسانه‌های محصولات'
        ordering = ['order']


class LicensePlan(models.Model):
    """پلن‌های لایسنس"""
    PLAN_TYPES = [
        ('single', 'یک‌سیستمی'),
        ('multi', 'چندسیستمی'),
        ('lifetime', 'مادام‌العمر'),
        ('daily', 'یک‌روزه'),
        ('monthly', 'یک‌ماهه'),
        ('quarterly', 'سه‌ماهه'),
        ('yearly', 'یک‌ساله'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='plans', verbose_name='محصول')
    name = models.CharField(max_length=100, verbose_name='نام پلن')
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, verbose_name='نوع پلن')
    price = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(0)], verbose_name='قیمت (تومان)')
    duration_days = models.IntegerField(null=True, blank=True, verbose_name='مدت اعتبار (روز)')
    max_activations = models.IntegerField(default=1, verbose_name='حداکثر فعال‌سازی')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    order = models.IntegerField(default=0, verbose_name='ترتیب')
    
    class Meta:
        verbose_name = 'پلن لایسنس'
        verbose_name_plural = 'پلن‌های لایسنس'
        ordering = ['order', 'price']
    
    def __str__(self):
        return f'{self.product.title} - {self.name}'


class Order(models.Model):
    """سفارش"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('pending_verification', 'در انتظار تایید پرداخت'),
        ('paid', 'پرداخت شده'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('zibal', 'درگاه زیبال'),
        ('card_transfer', 'کارت به کارت'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name='کاربر')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='product_orders', verbose_name='محصول')
    plan = models.ForeignKey(LicensePlan, on_delete=models.PROTECT, related_name='plan_orders', verbose_name='پلن')
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='مبلغ نهایی (تومان)')
    original_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='قیمت اصلی (تومان)')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='مبلغ تخفیف (تومان)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='zibal',
        verbose_name='روش پرداخت',
    )
    zibal_track_id = models.CharField(max_length=50, blank=True, null=True, verbose_name='کد پیگیری زیبال')
    affiliate = models.ForeignKey('affiliates.Affiliate', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مشاور')
    discount_code = models.ForeignKey('DiscountCode', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='کد تخفیف')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پرداخت')
    
    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'سفارش {self.id} - {self.user.username}'


class PlanFunnelEvent(models.Model):
    """رویداد قیف خرید پلن — بازدید قیمت‌گذاری، شروع خرید و ارتقا."""

    EVENT_TYPES = [
        ('pricing_view', 'بازدید صفحه قیمت‌گذاری'),
        ('checkout_view', 'شروع خرید'),
        ('upgrade_view', 'بازدید صفحه ارتقا'),
        ('payment_success', 'پرداخت موفق'),
        ('payment_failed', 'پرداخت ناموفق'),
        ('checkout_abandon', 'رها کردن Checkout'),
    ]

    event_type = models.CharField(max_length=32, choices=EVENT_TYPES, verbose_name='نوع رویداد')
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_funnel_events',
        verbose_name='کاربر',
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True, verbose_name='نشست')
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_funnel_events',
        verbose_name='محصول',
    )
    plan = models.ForeignKey(
        LicensePlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_funnel_events',
        verbose_name='پلن',
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name='متادیتا')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='تاریخ')

    class Meta:
        verbose_name = 'رویداد قیف پلن'
        verbose_name_plural = 'رویدادهای قیف پلن'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['product', 'event_type', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} — {self.created_at:%Y-%m-%d %H:%M}'


class Transaction(models.Model):
    """تراکنش پرداخت"""
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='transaction', verbose_name='سفارش')
    zibal_track_id = models.CharField(max_length=50, unique=True, verbose_name='کد پیگیری زیبال')
    zibal_ref_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='شماره مرجع زیبال')
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='مبلغ')
    status = models.CharField(max_length=20, verbose_name='وضعیت')
    gateway_result_code = models.IntegerField(null=True, blank=True, verbose_name='کد نتیجه درگاه')
    gateway_message = models.CharField(max_length=255, blank=True, verbose_name='پیام درگاه')
    callback_payload = models.JSONField(default=dict, blank=True, verbose_name='داده callback')
    verify_payload = models.JSONField(default=dict, blank=True, verbose_name='پاسخ verify')
    paid_amount_rial = models.PositiveIntegerField(null=True, blank=True, verbose_name='مبلغ پرداخت‌شده (ریال)')
    card_number_masked = models.CharField(max_length=32, blank=True, verbose_name='شماره کارت (ماسک‌شده)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تایید')
    
    class Meta:
        verbose_name = 'تراکنش'
        verbose_name_plural = 'تراکنش‌ها'
        ordering = ['-created_at']


class PaymentWebhookLog(models.Model):
    """لاگ وب‌هوک پرداخت"""
    payload = models.JSONField(verbose_name='داده دریافتی')
    headers = models.JSONField(default=dict, verbose_name='هدرها')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='آدرس IP')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'لاگ وب‌هوک پرداخت'
        verbose_name_plural = 'لاگ‌های وب‌هوک پرداخت'
        ordering = ['-created_at']


class DownloadLog(models.Model):
    """لاگ دانلود فایل"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name='سفارش')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='آدرس IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ دانلود')
    
    class Meta:
        verbose_name = 'لاگ دانلود'
        verbose_name_plural = 'لاگ‌های دانلود'
        ordering = ['-created_at']


class DiscountCode(models.Model):
    """کد تخفیف"""
    DISCOUNT_TYPES = [
        ('percentage', 'درصدی'),
        ('fixed', 'مبلغ ثابت'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='کد تخفیف')
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='percentage', verbose_name='نوع تخفیف')
    discount_value = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(0)], verbose_name='مقدار تخفیف')
    max_uses = models.IntegerField(null=True, blank=True, verbose_name='حداکثر تعداد استفاده')
    used_count = models.IntegerField(default=0, verbose_name='تعداد استفاده شده')
    min_purchase_amount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(0)], verbose_name='حداقل مبلغ خرید')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name='اعتبار از تاریخ')
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name='اعتبار تا تاریخ')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    
    class Meta:
        verbose_name = 'کد تخفیف'
        verbose_name_plural = 'کدهای تخفیف'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.code} - {self.get_discount_type_display()}'
    
    def is_valid(self, user=None):
        """بررسی اعتبار کد تخفیف"""
        if not self.is_active:
            return False, 'کد تخفیف غیرفعال است.'
        
        if self.max_uses and self.used_count >= self.max_uses:
            return False, 'کد تخفیف به پایان رسیده است.'
        
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False, 'کد تخفیف هنوز فعال نشده است.'
        
        if self.valid_until and now > self.valid_until:
            return False, 'کد تخفیف منقضی شده است.'
        
        # بررسی اینکه آیا کاربر قبلاً از این کد استفاده کرده است (فقط سفارش‌های پرداخت شده)
        if user and user.is_authenticated:
            from .models import Order
            has_used = Order.objects.filter(
                user=user,
                discount_code=self,
                status='paid'
            ).exists()
            if has_used:
                return False, 'شما قبلاً از این کد تخفیف استفاده کرده‌اید.'
        
        return True, 'کد تخفیف معتبر است.'
    
    def calculate_discount(self, amount, user=None):
        """محاسبه مبلغ تخفیف"""
        is_valid, message = self.is_valid(user)
        if not is_valid:
            return 0, message
        
        if self.min_purchase_amount and amount < self.min_purchase_amount:
            return 0, f'برای استفاده از این کد تخفیف، حداقل مبلغ خرید باید {int(self.min_purchase_amount):,} تومان باشد.'
        
        if self.discount_type == 'percentage':
            discount = (amount * self.discount_value) // 100
        else:  # fixed
            discount = min(self.discount_value, amount)
        
        return discount, 'تخفیف با موفقیت محاسبه شد.'


class ProductRating(models.Model):
    """امتیاز محصول"""
    RATING_CHOICES = [
        (1, '1 ستاره'),
        (2, '2 ستاره'),
        (3, '3 ستاره'),
        (4, '4 ستاره'),
        (5, '5 ستاره'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings', verbose_name='محصول')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_ratings', verbose_name='کاربر')
    rating = models.IntegerField(choices=RATING_CHOICES, verbose_name='امتیاز')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    
    class Meta:
        verbose_name = 'امتیاز محصول'
        verbose_name_plural = 'امتیازهای محصولات'
        unique_together = ['product', 'user']  # هر کاربر فقط یک بار می‌تواند امتیاز بدهد
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.product.title} - {self.rating} ستاره'
    
    @classmethod
    def get_average_rating(cls, product):
        """محاسبه میانگین امتیاز محصول"""
        ratings = cls.objects.filter(product=product)
        if not ratings.exists():
            return 0
        return round(ratings.aggregate(models.Avg('rating'))['rating__avg'], 1)
    
    @classmethod
    def get_rating_count(cls, product):
        """تعداد امتیازهای محصول"""
        return cls.objects.filter(product=product).count()
    
    @classmethod
    def get_rating_distribution(cls, product):
        """توزیع امتیازها"""
        distribution = {}
        for rating_value in range(1, 6):
            count = cls.objects.filter(product=product, rating=rating_value).count()
            distribution[rating_value] = count
        return distribution


class ProductReview(models.Model):
    """نظر/دیدگاه محصول"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name='محصول')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews', verbose_name='کاربر')
    rating = models.ForeignKey(ProductRating, on_delete=models.SET_NULL, null=True, blank=True, related_name='review', verbose_name='امتیاز مرتبط')
    title = models.CharField(max_length=200, verbose_name='عنوان نظر')
    content = models.TextField(verbose_name='متن نظر')
    is_approved = models.BooleanField(default=False, verbose_name='تایید شده')
    is_verified_purchase = models.BooleanField(default=False, verbose_name='خرید تایید شده')
    helpful_count = models.IntegerField(default=0, verbose_name='تعداد مفید')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    
    class Meta:
        verbose_name = 'نظر محصول'
        verbose_name_plural = 'نظرات محصولات'
        ordering = ['-created_at', '-helpful_count']
        indexes = [
            models.Index(fields=['product', 'is_approved']),
            models.Index(fields=['product', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.product.title} - {self.title[:50]}'
    
    def save(self, *args, **kwargs):
        # اگر کاربر قبلاً خرید کرده باشد، خرید را تایید شده علامت بزن
        if not self.pk and self.user and self.product:
            has_purchase = Order.objects.filter(
                user=self.user,
                product=self.product,
                status='paid'
            ).exists()
            self.is_verified_purchase = has_purchase
        super().save(*args, **kwargs)


class ReviewHelpful(models.Model):
    """نظرات مفید - برای ثبت اینکه کدام نظر برای کاربر مفید بوده"""
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='helpful_votes', verbose_name='نظر')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='helpful_reviews', verbose_name='کاربر')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    
    class Meta:
        verbose_name = 'نظر مفید'
        verbose_name_plural = 'نظرات مفید'
        unique_together = ['review', 'user']  # هر کاربر فقط یک بار می‌تواند نظر را مفید علامت بزند
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.review.title[:50]}'


class Announcement(models.Model):
    """اطلاعیه"""
    title = models.CharField(max_length=200, verbose_name='عنوان')
    content = models.TextField(verbose_name='محتوا')
    link = models.URLField(blank=True, null=True, verbose_name='لینک (اختیاری)')
    link_text = models.CharField(max_length=100, blank=True, verbose_name='متن لینک')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    show_from = models.DateTimeField(null=True, blank=True, verbose_name='نمایش از تاریخ')
    show_until = models.DateTimeField(null=True, blank=True, verbose_name='نمایش تا تاریخ')
    order = models.IntegerField(default=0, verbose_name='ترتیب نمایش')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    
    class Meta:
        verbose_name = 'اطلاعیه'
        verbose_name_plural = 'اطلاعیه‌ها'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return self.title
    
    def is_visible(self):
        """بررسی اینکه اطلاعیه باید نمایش داده شود یا نه"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.show_from and now < self.show_from:
            return False
        if self.show_until and now > self.show_until:
            return False
        
        return True



class PaymentSettings(models.Model):
    """تنظیمات روش‌های پرداخت — فقط یک رکورد (singleton)."""
    zibal_enabled = models.BooleanField(default=True, verbose_name='فعال‌سازی درگاه زیبال')
    card_transfer_enabled = models.BooleanField(default=False, verbose_name='فعال‌سازی کارت به کارت')
    card_number = models.CharField(max_length=24, blank=True, verbose_name='شماره کارت')
    card_holder_name = models.CharField(max_length=120, blank=True, verbose_name='نام صاحب کارت')
    bank_name = models.CharField(max_length=80, blank=True, verbose_name='نام بانک')
    iban = models.CharField(max_length=34, blank=True, verbose_name='شماره شبا')
    instructions = models.TextField(
        blank=True,
        verbose_name='راهنمای پرداخت',
        help_text='متن نمایش‌داده‌شده به کاربر هنگام کارت به کارت',
    )
    support_contact = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='راه ارتباطی پشتیبانی',
        help_text='مثلاً شماره واتساپ یا تلگرام',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')

    class Meta:
        verbose_name = 'تنظیمات پرداخت'
        verbose_name_plural = 'تنظیمات پرداخت'

    def __str__(self):
        return 'تنظیمات پرداخت'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def available_methods(self):
        methods = []
        if self.zibal_enabled:
            methods.append('zibal')
        if self.card_transfer_enabled and self.card_number.strip():
            methods.append('card_transfer')
        return methods


class CardTransferSubmission(models.Model):
    """درخواست تایید پرداخت کارت به کارت."""
    STATUS_CHOICES = [
        ('pending', 'در انتظار بررسی'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='card_transfer',
        verbose_name='سفارش',
    )
    reference_number = models.CharField(max_length=80, verbose_name='شماره پیگیری / رسید')
    payer_name = models.CharField(max_length=120, blank=True, verbose_name='نام پرداخت‌کننده')
    transferred_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان واریز')
    receipt_image = models.ImageField(
        upload_to='payments/receipts/',
        blank=True,
        null=True,
        verbose_name='تصویر رسید',
    )
    user_note = models.TextField(blank=True, verbose_name='توضیح کاربر')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='وضعیت بررسی',
    )
    admin_note = models.TextField(blank=True, verbose_name='یادداشت مدیر')
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_card_transfers',
        verbose_name='بررسی‌کننده',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان بررسی')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')

    class Meta:
        verbose_name = 'درخواست کارت به کارت'
        verbose_name_plural = 'درخواست‌های کارت به کارت'
        ordering = ['-created_at']

    def __str__(self):
        return f'کارت به کارت {self.order_id} — {self.get_status_display()}'


class Banner(models.Model):
    """بنر"""
    BANNER_TYPES = [
        ('image', 'تصویر'),
        ('text', 'متن'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='عنوان')
    banner_type = models.CharField(max_length=10, choices=BANNER_TYPES, default='image', verbose_name='نوع بنر')
    image = models.ImageField(upload_to='banners/', blank=True, null=True, verbose_name='تصویر')
    text_content = models.TextField(blank=True, verbose_name='متن بنر')
    link = models.URLField(blank=True, null=True, verbose_name='لینک')
    link_text = models.CharField(max_length=100, blank=True, verbose_name='متن لینک')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    show_from = models.DateTimeField(null=True, blank=True, verbose_name='نمایش از تاریخ')
    show_until = models.DateTimeField(null=True, blank=True, verbose_name='نمایش تا تاریخ')
    order = models.IntegerField(default=0, verbose_name='ترتیب نمایش')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    
    class Meta:
        verbose_name = 'بنر'
        verbose_name_plural = 'بنرها'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return self.title
    
    def is_visible(self):
        """بررسی اینکه بنر باید نمایش داده شود یا نه"""
        if not self.is_active:
            return False
        
        if self.banner_type == 'image' and not self.image:
            return False
        
        if self.banner_type == 'text' and not self.text_content:
            return False
        
        now = timezone.now()
        if self.show_from and now < self.show_from:
            return False
        if self.show_until and now > self.show_until:
            return False
        
        return True