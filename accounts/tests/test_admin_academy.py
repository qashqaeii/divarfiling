"""تست پنل مدیریت آکادمی و ثبت بازدید ویدیو."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_academy import (
    build_academy_stats_json,
    get_academy_analytics_chart,
    get_academy_dashboard_stats,
)
from workspace.academy.models import AcademyVideo, AcademyVideoViewDaily, LearningPath
from workspace.academy.services.view_tracking import record_video_view

User = get_user_model()


class AcademyViewTrackingTests(TestCase):
    def setUp(self):
        self.path = LearningPath.objects.create(
            slug='test-path', title='مسیر تست', order=1, is_active=True, is_public=True,
        )
        self.video = AcademyVideo.objects.create(
            path=self.path,
            slug='test-video',
            title='ویدیو تست',
            file_name='t.mp4',
            file_path='academy',
            duration_seconds=120,
            is_public=True,
            is_active=True,
        )

    def test_record_video_view_increments(self):
        self.assertEqual(record_video_view(self.video), 1)
        self.assertEqual(record_video_view(self.video), 2)
        self.video.refresh_from_db()
        self.assertEqual(self.video.views_count, 2)
        self.assertEqual(AcademyVideoViewDaily.objects.filter(video=self.video).count(), 1)

    def test_public_view_api(self):
        client = Client(enforce_csrf_checks=False)
        url = reverse('public_academy_video_view', kwargs={'slug': self.video.slug})
        resp = client.post(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['views_count'], 1)
        self.video.refresh_from_db()
        self.assertEqual(self.video.views_count, 1)


class AdminAcademyPanelTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffacd', password='pass1234', phone='09123333333', is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)
        path = LearningPath.objects.create(
            slug='admin-path', title='مسیر ادمین', order=1, is_active=True,
        )
        video = AcademyVideo.objects.create(
            path=path,
            slug='admin-video',
            title='ویدیو ادمین',
            file_name='a.mp4',
            file_path='academy',
            duration_seconds=60,
            is_public=True,
            is_active=True,
        )
        record_video_view(video)

    def test_academy_panel_requires_staff(self):
        guest = Client()
        resp = guest.get(reverse('admin_panel_academy'))
        self.assertEqual(resp.status_code, 302)

    def test_academy_panel_loads(self):
        resp = self.client.get(reverse('admin_panel_academy'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'استودیو آمار')

    def test_academy_stats_json(self):
        resp = self.client.get(reverse('admin_panel_academy_stats_json'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('summary', data)
        self.assertGreaterEqual(data['summary']['views_total'], 1)

    def test_academy_analytics_json(self):
        resp = self.client.get(reverse('admin_panel_academy_analytics_json'), {'days': 7})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['days'], 7)
        self.assertIn('traffic', data)

    def test_dashboard_includes_academy_section(self):
        resp = self.client.get(reverse('admin_panel'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ecc-academy')
        self.assertContains(resp, 'پنل آکادمی')

    def test_build_academy_stats_json_structure(self):
        payload = build_academy_stats_json(days=30, status='public', videos_limit=50)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['meta']['source'], 'admin_panel_academy')
        stats = get_academy_dashboard_stats()
        self.assertGreaterEqual(stats['videos_active'], 1)
        chart = get_academy_analytics_chart(days=7)
        self.assertIn('pulse', chart)

    def test_backfill_from_progress(self):
        from workspace.academy.models import AcademyVideo, UserVideoProgress
        from workspace.academy.services.backfill_views import backfill_academy_views

        video = AcademyVideo.objects.get(slug='admin-video')
        AcademyVideo.objects.filter(pk=video.pk).update(views_count=0)
        UserVideoProgress.objects.create(
            user=self.staff, video=video, watched_seconds=40, completed=False,
        )
        result = backfill_academy_views(replace_daily=True)
        self.assertGreaterEqual(result['views_total'], 1)
        video.refresh_from_db()
        self.assertGreaterEqual(video.views_count, 1)
