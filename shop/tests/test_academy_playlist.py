"""Tests for public academy video playlist page."""
import json

from django.test import Client, TestCase
from django.urls import reverse


class PublicAcademyPlaylistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy')

    def test_playlist_redirects_to_first_video(self):
        resp = Client().get(reverse('public_academy_playlist'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/academy/videos/', resp['Location'])

    def test_video_page_renders(self):
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': 'intro-what-is-divar-filing'}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'acd-pl-layout')
        self.assertContains(resp, 'فهرست پلی‌لیست')
        self.assertContains(resp, 'intro-what-is-divar-filing')
        self.assertContains(resp, 'application/ld+json')

    def test_video_page_seo_meta(self):
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': 'intro-what-is-divar-filing'}))
        self.assertContains(resp, 'og:title')
        self.assertContains(resp, 'canonical')
        self.assertContains(resp, 'آموزش ویدیویی آکادمی')

    def test_invalid_video_slug_404(self):
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': 'not-a-real-video'}))
        self.assertEqual(resp.status_code, 404)

    def test_schema_has_item_list(self):
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': 'intro-what-is-divar-filing'}))
        raw = resp.content.decode('utf-8')
        start = raw.find('{"@context": "https://schema.org", "@graph"')
        self.assertGreater(start, -1)
        end = raw.find('</script>', start)
        data = json.loads(raw[start:end])
        types = {node['@type'] for node in data['@graph']}
        self.assertIn('ItemList', types)
        self.assertIn('VideoObject', types)
        self.assertIn('BreadcrumbList', types)

    def test_public_academy_landing_links_playlist(self):
        resp = Client().get(reverse('public_academy'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('public_academy_playlist'))

    def test_playlist_includes_all_non_agency_paths(self):
        from workspace.academy.models import AcademyVideo
        from workspace.academy.services.public_playlist_service import get_public_playlist_sections, playlist_stats

        sections = get_public_playlist_sections()
        stats = playlist_stats(sections)
        expected = AcademyVideo.objects.filter(
            is_active=True,
            path__is_active=True,
            path__requires_role='',
        ).count()
        self.assertEqual(stats['video_count'], expected)
        self.assertGreater(stats['video_count'], 3)
        self.assertGreater(stats['section_count'], 1)
        slugs = {item['video'].slug for section in sections for item in section['videos']}
        self.assertIn('intro-what-is-divar-filing', slugs)
        self.assertIn('quick-start-workspace-tour', slugs)
        self.assertIn('crm-create-contact', slugs)
        self.assertNotIn('agency-team-intro', slugs)
