"""Tests for public academy video playlist page and SEO."""
import json

from django.test import Client, TestCase
from django.urls import reverse


def _parse_graph(resp):
    raw = resp.content.decode('utf-8')
    start = raw.find('{"@context": "https://schema.org", "@graph"')
    assert start > -1, 'JSON-LD @graph not found'
    end = raw.find('</script>', start)
    return json.loads(raw[start:end])


class PublicAcademyPlaylistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_academy')

    def test_playlist_hub_is_indexable_200(self):
        resp = Client().get(reverse('public_academy_playlist'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'پلی‌لیست آموزش ویدیویی آکادمی')
        self.assertContains(resp, 'application/ld+json')
        self.assertContains(resp, 'canonical')
        data = _parse_graph(resp)
        types = {node['@type'] for node in data['@graph']}
        self.assertIn('CollectionPage', types)
        self.assertIn('ItemList', types)
        self.assertIn('Course', types)
        self.assertIn('FAQPage', types)
        self.assertNotIn('VideoObject', types)  # hub has nested items, not page VideoObject

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

    def test_schema_video_object_complete(self):
        resp = Client().get(reverse('public_academy_video', kwargs={'slug': 'intro-what-is-divar-filing'}))
        data = _parse_graph(resp)
        types = {node['@type'] for node in data['@graph']}
        self.assertIn('ItemList', types)
        self.assertIn('VideoObject', types)
        self.assertIn('BreadcrumbList', types)
        self.assertIn('Course', types)
        self.assertIn('FAQPage', types)
        video_nodes = [n for n in data['@graph'] if n.get('@type') == 'VideoObject']
        self.assertEqual(len(video_nodes), 1)
        video = video_nodes[0]
        for key in ('uploadDate', 'datePublished', 'duration', 'thumbnailUrl', 'url', 'name', 'description', 'embedUrl'):
            self.assertIn(key, video)
            self.assertTrue(video[key], msg=f'{key} should be non-empty')
        self.assertRegex(video['uploadDate'], r'^\d{4}-\d{2}-\d{2}T')
        self.assertTrue(video.get('isFamilyFriendly'))
        # Nested ItemList videos must also be complete (Google validates these)
        item_list = next(n for n in data['@graph'] if n.get('@type') == 'ItemList')
        nested = item_list['itemListElement'][0]['item']
        self.assertEqual(nested['@type'], 'VideoObject')
        self.assertTrue(nested.get('description'))
        self.assertTrue(nested.get('embedUrl'))
        courses = [n for n in data['@graph'] if n.get('@type') == 'Course']
        self.assertGreaterEqual(len(courses), 1)
        self.assertTrue(courses[0].get('isAccessibleForFree'))
        self.assertEqual(courses[0].get('offers', {}).get('price'), '0')

    def test_public_academy_landing_seo(self):
        resp = Client().get(reverse('public_academy'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('public_academy_playlist'))
        self.assertContains(resp, 'application/ld+json')
        self.assertContains(resp, 'سؤالات رایج')
        data = _parse_graph(resp)
        types = {node['@type'] for node in data['@graph']}
        self.assertIn('WebPage', types)
        self.assertIn('BreadcrumbList', types)
        self.assertIn('Course', types)
        self.assertIn('FAQPage', types)
        self.assertIn('ItemList', types)

    def test_education_hub_has_faq_schema(self):
        resp = Client().get(reverse('education'))
        self.assertEqual(resp.status_code, 200)
        data = _parse_graph(resp)
        types = {node['@type'] for node in data['@graph']}
        self.assertIn('FAQPage', types)
        self.assertIn('WebPage', types)
        self.assertIn('BreadcrumbList', types)

    def test_academy_videos_sitemap_lists_public_slug(self):
        resp = Client().get('/sitemap-academy_videos.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('intro-what-is-divar-filing', body)
        self.assertIn('/academy/videos/', body)

    def test_playlist_only_shows_public_videos(self):
        from workspace.academy.models import AcademyVideo
        from workspace.academy.services.public_playlist_service import get_public_playlist_sections, playlist_stats

        sections = get_public_playlist_sections()
        stats = playlist_stats(sections)
        expected = AcademyVideo.objects.filter(
            is_public=True,
            is_active=True,
            path__is_active=True,
            path__requires_role='',
        ).count()
        self.assertEqual(stats['video_count'], expected)
        slugs = {item['video'].slug for section in sections for item in section['videos']}
        self.assertIn('intro-what-is-divar-filing', slugs)
        self.assertIn('intro-replace-excel-notebook', slugs)
        self.assertNotIn('quick-start-workspace-tour', slugs)
        self.assertNotIn('agency-team-intro', slugs)

    def test_public_video_in_non_public_path_still_lists(self):
        from workspace.academy.models import AcademyVideo
        from workspace.academy.services.public_playlist_service import get_public_playlist_sections

        video = AcademyVideo.objects.get(slug='quick-start-workspace-tour')
        self.assertFalse(video.is_public)
        video.is_public = True
        video.save(update_fields=['is_public'])
        try:
            slugs = {
                item['video'].slug
                for section in get_public_playlist_sections()
                for item in section['videos']
            }
            self.assertIn('quick-start-workspace-tour', slugs)
        finally:
            video.is_public = False
            video.save(update_fields=['is_public'])
