"""Tests for education hub academy hero context."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(ROOT_URLCONF='divar_shop.urls')
class EducationAcademyHeroTests(SimpleTestCase):
    @patch('workspace.academy.services.public_playlist_service.get_public_playlist_sections')
    def test_prefers_intro_video_when_available(self, mock_sections):
        from shop.education_academy import get_education_academy_hero

        intro = self._item('intro-what-is-divar-filing', '۳ دقیقه تا فهمیدن', available=True)
        other = self._item('intro-consultant-pain-points', 'مشکل واقعی', available=True)
        mock_sections.return_value = [{
            'path': MagicMock(title='آشنایی'),
            'videos': [intro, other],
            'video_count': 2,
            'total_minutes': 8,
        }]

        hero = get_education_academy_hero()
        self.assertTrue(hero['has_videos'])
        self.assertTrue(hero['player']['available'])
        self.assertEqual(hero['player']['slug'], 'intro-what-is-divar-filing')
        self.assertEqual(hero['playlist_url'], reverse('public_academy_playlist'))
        self.assertEqual(hero['stats']['video_count'], 2)

    @patch('workspace.academy.services.public_playlist_service.get_public_playlist_sections')
    def test_falls_back_to_first_available(self, mock_sections):
        from shop.education_academy import get_education_academy_hero

        missing = self._item('intro-what-is-divar-filing', '۳ دقیقه', available=False)
        ready = self._item('quick-start-first-value', 'اولین ارزش', available=True)
        mock_sections.return_value = [{
            'path': MagicMock(title='شروع سریع'),
            'videos': [missing, ready],
            'video_count': 2,
            'total_minutes': 5,
        }]

        hero = get_education_academy_hero()
        self.assertEqual(hero['player']['slug'], 'quick-start-first-value')

    @patch('workspace.academy.services.public_playlist_service.get_public_playlist_sections')
    def test_empty_playlist(self, mock_sections):
        from shop.education_academy import get_education_academy_hero

        mock_sections.return_value = []
        hero = get_education_academy_hero()
        self.assertFalse(hero['has_videos'])
        self.assertFalse(hero['player']['available'])
        self.assertEqual(hero['playlist_url'], reverse('public_academy_playlist'))

    def _item(self, slug, title, *, available):
        video = MagicMock()
        video.slug = slug
        video.title = title
        video.duration_seconds = 180
        return {
            'video': video,
            'player': {
                'available': available,
                'mode': 'file' if available else 'none',
                'src': f'/media/{slug}.mp4' if available else '',
                'title': title,
                'subtitle': '',
                'duration': '۳ دقیقه',
                'poster': '',
                'poster_kind': '',
                'slug': slug,
            },
            'index': 1,
            'global_index': 1,
            'url': f'/academy/videos/{slug}/',
        }
