"""تست ردیابی بازدید روزانه."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import Post, PostViewDaily
from blog.services.view_tracking import record_post_view

User = get_user_model()


class ViewTrackingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='viewauth', password='pass1234')
        self.post = Post.objects.create(
            title='تست بازدید',
            slug='view-tracking-test',
            author=self.author,
            content='<p>تست</p>',
            excerpt='خلاصه',
            is_published=True,
        )
        self.client = Client()

    def test_record_post_view_creates_daily_row(self):
        record_post_view(self.post)
        today = timezone.localdate()
        row = PostViewDaily.objects.get(post=self.post, date=today)
        self.assertEqual(row.views, 1)

    def test_record_post_view_increments(self):
        record_post_view(self.post)
        record_post_view(self.post)
        today = timezone.localdate()
        row = PostViewDaily.objects.get(post=self.post, date=today)
        self.assertEqual(row.views, 2)

    def test_post_detail_increments_daily_view(self):
        resp = self.client.get(reverse('blog:post_detail', kwargs={'slug': self.post.slug}))
        self.assertEqual(resp.status_code, 200)
        today = timezone.localdate()
        row = PostViewDaily.objects.get(post=self.post, date=today)
        self.assertEqual(row.views, 1)
        self.assertEqual(Post.objects.get(pk=self.post.pk).views_count, 1)

    def test_draft_does_not_record_daily_view(self):
        self.post.is_published = False
        self.post.save(update_fields=['is_published'])
        self.client.get(reverse('blog:post_detail', kwargs={'slug': self.post.slug}))
        self.assertFalse(PostViewDaily.objects.exists())
