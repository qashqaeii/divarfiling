"""Tests for education page academy hero."""
from django.test import SimpleTestCase

from shop.education_academy import get_education_academy_hero


class EducationAcademyHeroTests(SimpleTestCase):
    def _item(self, slug, title, available=True):
        class V:
            pass
        v = V()
        v.slug = slug
        v.title = title
        return {
            'video': v,
            'player': {
                'available': available,
                'slug': slug,
                'title': title,
                'src': f'/media/Video/x.mp4' if available else '',
            },
            'url': f'/academy/videos/{slug}/',
        }

    def test_hero_prefers_first_curriculum_video(self):
        from unittest.mock import patch
        intro = self._item('academy-what-is-divar-filing', 'فایلینگ دیوار', available=True)
        sections = [{'path': None, 'videos': [intro]}]
        with patch('workspace.academy.services.public_playlist_service.get_public_playlist_sections', return_value=sections):
            with patch('workspace.academy.services.public_playlist_service.playlist_stats', return_value={'video_count': 1, 'section_count': 1, 'total_minutes': 2}):
                with patch('workspace.academy.services.public_playlist_service.flatten_public_videos', return_value=[intro]):
                    hero = get_education_academy_hero()
        self.assertEqual(hero['player']['slug'], 'academy-what-is-divar-filing')
