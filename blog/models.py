"""
مدل‌های بلاگ
"""
import uuid

from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class Category(models.Model):
    """دسته‌بندی مقالات"""
    name = models.CharField(max_length=100, verbose_name='نام')
    slug = models.SlugField(max_length=120, unique=True, verbose_name='نامک')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    order = models.IntegerField(default=0, verbose_name='ترتیب')
    
    class Meta:
        verbose_name = 'دسته‌بندی'
        verbose_name_plural = 'دسته‌بندی‌ها'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class Tag(models.Model):
    """برچسب مقالات"""
    name = models.CharField(max_length=100, unique=True, verbose_name='نام')
    slug = models.SlugField(max_length=120, unique=True, verbose_name='نامک')
    
    class Meta:
        verbose_name = 'برچسب'
        verbose_name_plural = 'برچسب‌ها'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Post(models.Model):
    """مقاله"""
    title = models.CharField(max_length=200, verbose_name='عنوان')
    slug = models.SlugField(max_length=220, unique=True, verbose_name='نامک')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='نویسنده')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='دسته‌بندی')
    tags = models.ManyToManyField(Tag, blank=True, verbose_name='برچسب‌ها')
    content = models.TextField(verbose_name='محتوا')
    excerpt = models.TextField(max_length=300, blank=True, verbose_name='خلاصه')
    featured_image = models.ImageField(upload_to='blog/', blank=True, null=True, verbose_name='تصویر شاخص')
    is_published = models.BooleanField(default=False, verbose_name='منتشر شده')
    views_count = models.IntegerField(default=0, verbose_name='تعداد بازدید')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ انتشار')
    
    class Meta:
        verbose_name = 'مقاله'
        verbose_name_plural = 'مقالات'
        ordering = ['-published_at', '-created_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.slug})


class PostViewDaily(models.Model):
    """بازدید روزانه هر مقاله — پایه Analytics پنل مدیریت."""

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='daily_views',
        verbose_name='مقاله',
    )
    date = models.DateField(verbose_name='تاریخ', db_index=True)
    views = models.PositiveIntegerField(default=0, verbose_name='بازدید')

    class Meta:
        verbose_name = 'بازدید روزانه'
        verbose_name_plural = 'بازدیدهای روزانه'
        ordering = ['-date', '-views']
        constraints = [
            models.UniqueConstraint(fields=['post', 'date'], name='blog_postviewdaily_post_date_uniq'),
        ]
        indexes = [
            models.Index(fields=['date', 'views']),
        ]

    def __str__(self):
        return f'{self.post_id} · {self.date} · {self.views}'


class MarketArticleRun(models.Model):
    """پیش‌نمایش / اجرای تولید مقاله سیستماتیک از دیتاست."""

    class Status(models.TextChoices):
        BUILDING = 'building', 'در حال ساخت'
        PREVIEW = 'preview', 'پیش‌نمایش'
        DRAFT_LINKED = 'draft_linked', 'متصل به پیش‌نویس'
        FAILED = 'failed', 'ناموفق'
        DISCARDED = 'discarded', 'لغو شده'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        'workspace.Dataset',
        on_delete=models.CASCADE,
        related_name='market_article_runs',
        verbose_name='دیتاست',
    )
    market_key = models.CharField(max_length=220, db_index=True, verbose_name='کلید بازار')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PREVIEW,
        db_index=True,
        verbose_name='وضعیت',
    )
    report_json = models.JSONField(default=dict, blank=True, verbose_name='گزارش anonymized')
    seo_json = models.JSONField(default=dict, blank=True, verbose_name='SEO')
    content_html = models.TextField(blank=True, verbose_name='محتوای HTML')
    faq_json = models.JSONField(default=list, blank=True, verbose_name='FAQ')
    featured_image = models.ImageField(
        upload_to='blog/market-maps/',
        blank=True,
        null=True,
        verbose_name='تصویر شاخص',
    )
    chart_assets = models.JSONField(default=dict, blank=True, verbose_name='دارایی‌های نمودار/نقشه')
    quality_score = models.FloatField(null=True, blank=True, verbose_name='امتیاز کیفیت')
    confidence_score = models.FloatField(null=True, blank=True, verbose_name='امتیاز اعتماد')
    valid_count = models.PositiveIntegerField(default=0, verbose_name='رکورد معتبر')
    raw_count = models.PositiveIntegerField(default=0, verbose_name='رکورد خام')
    quality_pct = models.FloatField(null=True, blank=True, verbose_name='درصد کیفیت')
    data_from = models.DateField(null=True, blank=True, verbose_name='از تاریخ داده')
    data_to = models.DateField(null=True, blank=True, verbose_name='تا تاریخ داده')
    source_dataset_updated_at = models.DateTimeField(
        null=True, blank=True, verbose_name='updated_at دیتاست منبع',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='market_article_runs',
        verbose_name='ایجادکننده',
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='market_article_runs',
        verbose_name='مقاله',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')

    class Meta:
        verbose_name = 'اجرای مقاله سیستماتیک'
        verbose_name_plural = 'اجراهای مقاله سیستماتیک'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['dataset', '-created_at']),
            models.Index(fields=['market_key', '-created_at']),
        ]

    def __str__(self):
        return f'{self.market_key} · {self.status} · {self.pk}'


class MarketArticleLink(models.Model):
    """یک مقاله اصلی به ازای هر ترکیب بازار."""

    market_key = models.CharField(max_length=220, unique=True, verbose_name='کلید بازار')
    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name='market_article_link',
        verbose_name='مقاله',
    )
    primary_dataset = models.ForeignKey(
        'workspace.Dataset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='market_article_links',
        verbose_name='دیتاست منبع',
    )
    last_run = models.ForeignKey(
        MarketArticleRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_as_last',
        verbose_name='آخرین اجرا',
    )
    last_generated_at = models.DateTimeField(null=True, blank=True, verbose_name='آخرین تولید')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'پیوند مقاله بازار'
        verbose_name_plural = 'پیوندهای مقاله بازار'

    def __str__(self):
        return self.market_key

