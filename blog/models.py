"""
مدل‌های بلاگ
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class Category(models.Model):
    """دسته‌بندی مقالات"""
    name = models.CharField(max_length=100, verbose_name='نام')
    slug = models.SlugField(unique=True, verbose_name='نامک')
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
    name = models.CharField(max_length=50, unique=True, verbose_name='نام')
    slug = models.SlugField(unique=True, verbose_name='نامک')
    
    class Meta:
        verbose_name = 'برچسب'
        verbose_name_plural = 'برچسب‌ها'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Post(models.Model):
    """مقاله"""
    title = models.CharField(max_length=200, verbose_name='عنوان')
    slug = models.SlugField(unique=True, verbose_name='نامک')
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

