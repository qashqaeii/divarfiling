"""Tests for workspace academy curriculum (12 videos)."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.academy.models import UserVideoProgress

from workspace.academy.curriculum import adjacent_videos, ordered_videos
from workspace.academy.models import AcademyMission, AcademyVideo, LearningPath
from workspace.academy.seed_data import CONTEXTUAL_BANNERS, CURRICULUM_VIDEO_SLUGS, VIDEOS
from workspace.academy.services.contextual_service import get_contextual_banner

User = get_user_model()


class AcademySeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy', '--reset', '--yes')

    def test_exact_curriculum_counts(self):
        self.assertEqual(LearningPath.objects.filter(is_active=True).count(), 3)
        self.assertEqual(AcademyVideo.objects.filter(is_active=True).count(), 12)
        self.assertFalse(AcademyMission.objects.exists())

    def test_path_video_counts(self):
        p1 = LearningPath.objects.get(slug='getting-started')
        p2 = LearningPath.objects.get(slug='extracting-and-managing-files')
        p3 = LearningPath.objects.get(slug='customer-and-crm')
        self.assertEqual(p1.videos.filter(is_active=True).count(), 3)
        self.assertEqual(p2.videos.filter(is_active=True).count(), 5)
        self.assertEqual(p3.videos.filter(is_active=True).count(), 4)

    def test_global_order_and_adjacency(self):
        items = ordered_videos()
        self.assertEqual(len(items), 12)
        self.assertEqual(items[0].slug, 'academy-what-is-divar-filing')
        self.assertEqual(items[7].slug, 'academy-file-cabinets-folders')
        self.assertEqual(items[8].slug, 'academy-what-is-crm')
        self.assertEqual(items[11].slug, 'academy-personal-files-and-sharing-with-customers')
        prev_v, next_v = adjacent_videos(items[7])
        self.assertEqual(prev_v.slug, 'academy-personal-files-map')
        self.assertEqual(next_v.slug, 'academy-what-is-crm')
        prev_v, next_v = adjacent_videos(items[11])
        self.assertEqual(prev_v.slug, 'academy-crm-reminders-and-follow-ups')
        self.assertIsNone(next_v)

    def test_all_public(self):
        self.assertEqual(AcademyVideo.objects.filter(is_public=False).count(), 0)

    def test_seed_idempotent(self):
        from django.core.management import call_command
        call_command('seed_academy')
        self.assertEqual(AcademyVideo.objects.count(), 12)

    def test_media_and_posters_exist(self):
        media = Path(settings.MEDIA_ROOT)
        for row in VIDEOS:
            video_file = media / row['file_path'] / row['file_name']
            poster_file = media / row['poster_path']
            self.assertTrue(video_file.is_file(), msg=str(video_file))
            self.assertTrue(poster_file.is_file(), msg=str(poster_file))

    def test_contextual_empty_state_banners(self):
        user = User.objects.create_user(username='ctx_banner', password='x', phone='09121110001')
        self.assertIn('contacts_empty', CONTEXTUAL_BANNERS)
        self.assertIn('properties_empty', CONTEXTUAL_BANNERS)
        contacts_banner = get_contextual_banner(user, 'contacts_empty')
        props_banner = get_contextual_banner(user, 'properties_empty')
        self.assertIsNotNone(contacts_banner)
        self.assertIsNotNone(props_banner)
        self.assertEqual(contacts_banner['video'].slug, 'academy-adding-a-new-contact-to-crm')
        self.assertEqual(
            contacts_banner['video'].file_name,
            'Adding-a-New-Contact-to-CRM.mp4',
        )
        self.assertEqual(
            props_banner['video'].slug,
            'academy-personal-files-and-sharing-with-customers',
        )
        self.assertEqual(
            props_banner['video'].file_name,
            'Personal-Files-and-Sharing-with-Customers-via-Link.mp4',
        )
        datasets_banner = get_contextual_banner(user, 'datasets_empty')
        self.assertIsNotNone(datasets_banner)
        self.assertTrue(datasets_banner['player']['available'])
        self.assertEqual(datasets_banner['modal_id'], 'modal-acd-contextual-datasets_empty')
        self.assertEqual(datasets_banner['video'].slug, 'academy-extract-divar-listings')
        self.assertEqual(
            datasets_banner['video'].file_name,
            'Extracting-Divar-Listings-in-Less-Than-Two-Minutes.mp4',
        )

    def test_contextual_banner_lazy_seeds_missing_video_row(self):
        user = User.objects.create_user(username='ctx_lazy', password='x', phone='09121110002')
        deleted, _ = AcademyVideo.objects.filter(slug='academy-extract-divar-listings').delete()
        self.assertGreater(deleted, 0)
        banner = get_contextual_banner(user, 'datasets_empty')
        self.assertIsNotNone(banner)
        self.assertTrue(
            AcademyVideo.objects.filter(slug='academy-extract-divar-listings', is_active=True).exists()
        )


class AcademyPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy', '--reset', '--yes')
        cls.user = User.objects.create_user(username='acduser', password='test-pass-123', phone='09120000001')

    def setUp(self):
        self.client = Client()
        self.client.login(username='acduser', password='test-pass-123')

    def test_academy_home_ok(self):
        resp = self.client.get(reverse('workspace:academy_home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'آکادمی فایلینگ دیوار')
        self.assertNotContains(resp, 'ماموریت روز اول')
        self.assertNotContains(resp, 'مشاور سنتی')

    def test_mission_redirects_home(self):
        resp = self.client.get(reverse('workspace:academy_mission'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('academy', resp.url)

    def test_traditional_redirects_home(self):
        resp = self.client.get(reverse('workspace:academy_traditional'))
        self.assertEqual(resp.status_code, 302)

    def test_onboarding_complete_redirect_url(self):
        resp = self.client.post(reverse('workspace:onboarding_complete'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('academy', data.get('redirect_url', ''))
        self.assertNotIn('mission', data.get('redirect_url', ''))

    def test_each_video_page_200(self):
        for slug in CURRICULUM_VIDEO_SLUGS:
            resp = self.client.get(reverse('workspace:academy_video', kwargs={'slug': slug}))
            self.assertEqual(resp.status_code, 200, slug)

    def test_extract_video_title_updated(self):
        video = AcademyVideo.objects.get(slug='academy-extract-divar-listings')
        self.assertEqual(video.title, 'استخراج سریع آگهی‌های دیوار')
        resp = self.client.get(reverse('workspace:academy_video', kwargs={'slug': video.slug}))
        self.assertContains(resp, 'استخراج سریع آگهی‌های دیوار')
        self.assertNotContains(resp, 'کمتر از یک دقیقه')

    def test_academy_home_has_search(self):
        resp = self.client.get(reverse('workspace:academy_home'))
        self.assertContains(resp, 'acdSearchInput')
        self.assertContains(resp, 'acdSearchData')

    def test_workspace_home_does_not_show_intro_video_block(self):
        resp = self.client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'mk-intro-vid')

    def test_public_home_shows_intro_video_below_stats(self):
        resp = Client().get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mk-intro-vid')
        self.assertContains(resp, reverse('public_academy_playlist'))

    def test_persian_search_keywords(self):
        from workspace.academy.search import find_videos_by_query

        cases = {
            'فایلینگ دیوار': 'academy-what-is-divar-filing',
            'داشبورد': 'academy-dashboard-overview',
            'لایسنس': 'academy-license-purchase-activation',
            'استخراج': 'academy-extract-divar-listings',
            'فیلتر': 'academy-filter-files',
            'تحلیل فایل': 'academy-review-analyze-file',
            'فایل شخصی': 'academy-personal-files-map',
            'نقشه': 'academy-personal-files-map',
            'زونکن': 'academy-file-cabinets-folders',
            'کمد': 'academy-file-cabinets-folders',
            'CRM': 'academy-what-is-crm',
            'ثبت مخاطب': 'academy-adding-a-new-contact-to-crm',
            'یادآوری': 'academy-crm-reminders-and-follow-ups',
            'اشتراک فایل': 'academy-personal-files-and-sharing-with-customers',
        }
        for query, expected_slug in cases.items():
            hits = find_videos_by_query(query)
            self.assertTrue(hits, msg=query)
            self.assertEqual(hits[0].slug, expected_slug, msg=query)


class AcademyProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy', '--reset', '--yes')
        cls.user = User.objects.create_user(username='proguser', password='test-pass-123')

    def test_video_progress_api(self):
        import json
        video = AcademyVideo.objects.get(slug='academy-what-is-divar-filing')
        self.client = Client()
        self.client.login(username='proguser', password='test-pass-123')
        url = reverse('workspace:api_academy_video_progress', kwargs={'slug': video.slug})
        resp = self.client.post(
            url,
            json.dumps({'watched_seconds': 10, 'completed': True}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json().get('completed'))
        min_watch = max(int(video.duration_seconds * 0.85), 5)
        resp = self.client.post(
            url,
            json.dumps({'watched_seconds': min_watch, 'completed': True}),
            content_type='application/json',
        )
        self.assertTrue(resp.json().get('completed'))


class AcademyCtaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        from shop.models import Product

        call_command('seed_academy', '--reset', '--yes')
        Product.objects.get_or_create(
            slug='divar-extraction-bot',
            defaults={
                'title': 'ربات استخراج دیوار',
                'description': 'تست',
                'is_active': True,
            },
        )
        cls.user = User.objects.create_user(username='ctauser', password='test-pass-123')

    def setUp(self):
        self.client = Client()
        self.client.login(username='ctauser', password='test-pass-123')

    def test_license_video_cta_points_to_product(self):
        video = AcademyVideo.objects.get(slug='academy-license-purchase-activation')
        video.action_url = '/shop/'
        video.save(update_fields=['action_url'])
        expected = reverse('product_detail', kwargs={'slug': 'divar-extraction-bot'})
        self.assertEqual(video.resolved_action_url(), expected)
        resp = self.client.get(reverse('workspace:academy_video', kwargs={'slug': video.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, expected)

    def test_all_active_video_ctas_resolve(self):
        for video in AcademyVideo.objects.filter(is_active=True).exclude(action_url=''):
            url = video.resolved_action_url()
            self.assertTrue(url, msg=video.slug)
            if url.startswith('/'):
                resp = self.client.get(url)
                self.assertIn(
                    resp.status_code,
                    (200, 302),
                    msg=f'{video.slug} -> {url} status {resp.status_code}',
                )


class AcademyResumeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy', '--reset', '--yes')
        cls.user = User.objects.create_user(username='resumeuser', password='test-pass-123')

    def setUp(self):
        self.client = Client()
        self.client.login(username='resumeuser', password='test-pass-123')

    def test_resume_position_on_video_page(self):
        import json
        video = AcademyVideo.objects.get(slug='academy-dashboard-overview')
        url = reverse('workspace:api_academy_video_progress', kwargs={'slug': video.slug})
        self.client.post(
            url,
            json.dumps({'watched_seconds': 37}),
            content_type='application/json',
        )
        page = self.client.get(reverse('workspace:academy_video', kwargs={'slug': video.slug}))
        self.assertContains(page, 'data-acd-resume-seconds="37"')

    def test_inactive_video_not_in_continue_watching(self):
        from workspace.academy.services.progress_service import get_continue_watching

        video = AcademyVideo.objects.get(slug='academy-filter-files')
        UserVideoProgress.objects.update_or_create(
            user=self.user,
            video=video,
            defaults={'last_position': 40, 'watched_seconds': 40, 'completed': False},
        )
        video.is_active = False
        video.save(update_fields=['is_active'])
        self.assertIsNone(get_continue_watching(self.user))

    def test_progress_api_rejects_invalid_watched_seconds(self):
        import json
        video = AcademyVideo.objects.get(slug='academy-what-is-divar-filing')
        url = reverse('workspace:api_academy_video_progress', kwargs={'slug': video.slug})
        resp = self.client.post(
            url,
            json.dumps({'watched_seconds': 'not-a-number'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


class PublicAcademyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy', '--reset', '--yes')

    def test_public_academy_page(self):
        resp = Client().get(reverse('public_academy'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'آکادمی فایلینگ دیوار')
        self.assertContains(resp, '12 آموزش')

    def test_public_playlist_count(self):
        resp = Client().get(reverse('public_academy_playlist'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['playlist_stats']['video_count'], 12)
        self.assertEqual(resp.context['playlist_stats']['section_count'], 3)
