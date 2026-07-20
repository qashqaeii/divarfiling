"""Tests for workspace academy."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.academy.models import AcademyMission, AcademyVideo, LearningPath
from workspace.academy.services.progress_service import (
    check_action_complete,
    get_mission_progress,
    sync_mission_auto_confirm,
    update_video_progress,
)
from workspace.models import Customer, ListingMeta

User = get_user_model()


class AcademySeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy')

    def test_paths_and_videos_seeded(self):
        self.assertGreaterEqual(LearningPath.objects.count(), 5)
        self.assertGreaterEqual(AcademyVideo.objects.count(), 25)
        self.assertTrue(AcademyMission.objects.filter(slug='day-one').exists())

    def test_launch_videos_flagged(self):
        self.assertEqual(AcademyVideo.objects.filter(is_launch=True).count(), 8)


class AcademyPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy')
        cls.user = User.objects.create_user(username='acduser', password='test-pass-123')

    def setUp(self):
        self.client = Client()
        self.client.login(username='acduser', password='test-pass-123')

    def test_academy_home_requires_login(self):
        anon = Client()
        resp = anon.get(reverse('workspace:academy_home'))
        self.assertEqual(resp.status_code, 302)

    def test_academy_home_ok(self):
        resp = self.client.get(reverse('workspace:academy_home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'آکادمی فایلینگ دیوار')

    def test_mission_page_ok(self):
        resp = self.client.get(reverse('workspace:academy_mission'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ماموریت روز اول')
        self.assertContains(resp, 'bot-install-video.js')
        self.assertContains(resp, 'data-mk-vid-player')

    def test_onboarding_complete_redirect_url(self):
        resp = self.client.post(reverse('workspace:onboarding_complete'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))
        self.assertIn('academy/mission', data.get('redirect_url', ''))


class AcademyProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy')
        cls.user = User.objects.create_user(username='proguser', password='test-pass-123')

    def test_first_contact_detection(self):
        self.assertFalse(check_action_complete(self.user, 'first_contact_created'))
        Customer.objects.create(user=self.user, name='Test', phone='09120000000')
        self.assertTrue(check_action_complete(self.user, 'first_contact_created'))

    def test_first_file_favorite(self):
        self.assertFalse(check_action_complete(self.user, 'first_file_found'))
        ListingMeta.objects.create(user=self.user, token='tok1', is_favorite=True)
        self.assertTrue(check_action_complete(self.user, 'first_file_found'))

    def test_video_progress_api(self):
        import json
        video = AcademyVideo.objects.get(slug='quick-start-first-value')
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

        resp = self.client.post(
            url,
            json.dumps({'watched_seconds': 55, 'completed': True}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('completed'))
        progress = get_mission_progress(self.user)
        sync_mission_auto_confirm(self.user)
        self.assertIsNotNone(progress)


class AcademyPosterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy')

    def test_poster_image_in_player_context(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        video = AcademyVideo.objects.get(slug='quick-start-first-value')
        video.poster_image = SimpleUploadedFile(
            'poster.jpg',
            b'\xff\xd8\xff\xd9',
            content_type='image/jpeg',
        )
        video.save()
        ctx = video.to_player_context()
        self.assertEqual(ctx['poster_kind'], 'media')
        self.assertIn('/media/academy/posters/', ctx['poster'])

    def test_legacy_static_poster_path(self):
        video = AcademyVideo.objects.get(slug='quick-start-first-value')
        video.poster_path = 'images/test-poster.jpg'
        video.save()
        ctx = video.to_player_context()
        self.assertEqual(ctx['poster_kind'], 'static')
        self.assertEqual(ctx['poster'], 'images/test-poster.jpg')


class PublicAcademyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy')

    def test_public_academy_page(self):
        resp = Client().get(reverse('public_academy'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'آکادمی فایلینگ دیوار')
