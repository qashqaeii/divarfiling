"""Public academy playlist tests."""
from django.test import Client, TestCase
from django.urls import reverse

from workspace.academy.models import AcademyVideo
from workspace.academy.seed_data import CURRICULUM_VIDEO_SLUGS


class PublicAcademyPlaylistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy', '--reset', '--yes')

    def test_hub_lists_twelve_videos(self):
        resp = Client().get(reverse('public_academy_playlist'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['playlist_stats']['video_count'], 12)
        self.assertEqual(resp.context['playlist_stats']['section_count'], 3)

    def test_video_detail_200(self):
        slug = CURRICULUM_VIDEO_SLUGS[0]
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, slug)

    def test_bad_slug_404(self):
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': 'intro-what-is-divar-filing'}))
        self.assertEqual(resp.status_code, 404)

    def test_global_nav_across_paths(self):
        v3 = AcademyVideo.objects.get(slug='academy-license-purchase-activation')
        v4 = AcademyVideo.objects.get(slug='academy-extract-divar-listings')
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': v3.slug}))
        self.assertEqual(resp.status_code, 200)
        next_item = resp.context.get('next_item')
        self.assertIsNotNone(next_item)
        self.assertEqual(next_item['video'].slug, v4.slug)
