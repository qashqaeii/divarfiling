"""
مدل‌های کاربری
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """مدل کاربر سفارشی"""
    phone = models.CharField(max_length=20, unique=True, verbose_name='شماره موبایل')
    national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت‌نام')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    is_affiliate = models.BooleanField(default=False, verbose_name='مشاور فروش')
    referred_by = models.ForeignKey(
        'affiliates.Affiliate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_users',
        verbose_name='معرف'
    )
    
    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.phone or self.username or self.email


class UserProfile(models.Model):
    """پروفایل تکمیلی کاربر"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='کاربر')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='تصویر پروفایل')
    bio = models.TextField(blank=True, verbose_name='درباره من')
    address = models.TextField(blank=True, verbose_name='آدرس')
    city = models.CharField(max_length=100, blank=True, verbose_name='شهر')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='کد پستی')
    
    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = 'پروفایل‌های کاربران'
    
    def __str__(self):
        return f'پروفایل {self.user.username}'

