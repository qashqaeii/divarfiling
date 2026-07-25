"""Tests for district access scoring and article HTML (no live Overpass)."""
from django.test import SimpleTestCase

from blog.services.market_article_access import (
    _SKIP_CATEGORY_KEYS,
    _count_to_score,
    _geo_center,
    _score_access,
)
from blog.services.market_article_access_html import render_district_access_section
from blog.services.market_article_composer import _section_district_access
from workspace.services.nearby_pois import POI_CATEGORIES


class DistrictAccessHelpersTests(SimpleTestCase):
    def test_geo_center_median(self):
        pts = [
            {'lat': 35.7, 'lng': 51.4},
            {'lat': 35.71, 'lng': 51.41},
            {'lat': 35.72, 'lng': 51.42},
            {'lat': 35.73, 'lng': 51.43},
            {'lat': 35.74, 'lng': 51.44},
        ]
        c = _geo_center(pts)
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c[0], 35.72, places=2)

    def test_count_score_monotonic(self):
        self.assertEqual(_count_to_score(0, cap=6), 0.0)
        self.assertGreater(_count_to_score(2, cap=6), _count_to_score(1, cap=6))
        self.assertGreaterEqual(_count_to_score(6, cap=6), 90)

    def test_score_access_grades(self):
        groups = [
            {'key': 'daily', 'score': 90},
            {'key': 'health', 'score': 85},
            {'key': 'transport', 'score': 80},
            {'key': 'education', 'score': 75},
            {'key': 'religion', 'score': 70},
            {'key': 'leisure', 'score': 70},
            {'key': 'safety', 'score': 80},
        ]
        score, grade, label = _score_access(groups)
        self.assertGreaterEqual(score, 70)
        self.assertIn(grade[0], 'AB')
        self.assertTrue(label)

    def test_road_categories_skipped_for_district(self):
        self.assertIn('main_road', _SKIP_CATEGORY_KEYS)
        self.assertIn('motorway', _SKIP_CATEGORY_KEYS)
        keys = {c['key'] for c in POI_CATEGORIES}
        self.assertIn('cafe', keys)
        self.assertIn('police', keys)

    def test_section_renders_professional_counts(self):
        access = {
            'ok': True,
            'score': 86,
            'grade': 'A',
            'grade_label': 'دسترسی عالی',
            'radius_label': '۳ کیلومتر',
            'summary': 'امتیاز نمونه',
            'total_pois': 200,
            'found_count': 18,
            'total_count': 21,
            'highlights': [
                {'label': 'پارک', 'icon': 'fa-tree', 'color': '#059669', 'count': 98},
                {'label': 'رستوران', 'icon': 'fa-utensils', 'color': '#b45309', 'count': 29},
            ],
            'gaps': [{'label': 'مترو', 'key': 'metro'}],
            'groups': [
                {
                    'key': 'daily',
                    'label': 'زندگی روزمره',
                    'items': [
                        {'key': 'restaurant', 'label': 'رستوران', 'icon': 'fa-utensils', 'color': '#b45309', 'count': 29},
                        {'key': 'cafe', 'label': 'کافه', 'icon': 'fa-mug-saucer', 'color': '#a16207', 'count': 21},
                        {'key': 'main_road', 'label': 'معبر اصلی', 'count': 217},
                    ],
                },
                {
                    'key': 'safety',
                    'label': 'امنیت و خدمات',
                    'items': [
                        {'key': 'police', 'label': 'کلانتری', 'icon': 'fa-shield-halved', 'color': '#1d4ed8', 'count': 1},
                        {'key': 'fire_station', 'label': 'آتش‌نشانی', 'icon': 'fa-fire-extinguisher', 'color': '#b45309', 'count': 3},
                    ],
                },
            ],
        }
        html = _section_district_access(access, city='قم', district='شهرک قدس')
        self.assertIn('mk-access-section', html)
        self.assertIn('mk-access-shell', html)
        self.assertIn('mk-access-cell-grid', html)
        self.assertIn('mk-access-tally-grid', html)
        self.assertIn('امکانات و دسترسی‌های منطقه', html)
        self.assertIn('رستوران', html)
        self.assertIn('کلانتری', html)
        self.assertIn('پارک', html)
        self.assertIn('mk-access-score__num', html)
        self.assertIn('از ۱۰۰', html)
        self.assertNotIn('معبر اصلی', html)
        self.assertNotIn('OpenStreetMap', html)
        self.assertNotIn('پیاده', html)
        self.assertIn('یافت‌نشده', html)
        # اعداد فارسی تعداد
        self.assertIn('۲۹', html)
        self.assertIn('۹۸', html)

    def test_section_soft_message_when_overpass_fails(self):
        html = render_district_access_section(
            {'ok': False, 'reason': 'overpass', 'message': 'سرویس نقشه در دسترس نیست.'},
            city='تهران',
            district='جردن',
        )
        self.assertIn('district-access', html)
        self.assertIn('سرویس نقشه', html)

    def test_section_empty_when_skipped(self):
        self.assertEqual(_section_district_access({'ok': False, 'reason': 'skipped'}, city='x', district='y'), '')

    def test_tally_from_categories_when_groups_empty(self):
        access = {
            'ok': True,
            'score': 70,
            'grade': 'B+',
            'grade_label': 'دسترسی خوب',
            'radius_label': '۳ کیلومتر',
            'summary': 'نمونه',
            'total_pois': 435,
            'found_count': 2,
            'total_count': 20,
            'groups': [],
            'categories': [
                {'key': 'clinic', 'label': 'کلینیک', 'icon': 'fa-stethoscope', 'color': '#e11d48', 'count': 224, 'nearest_m': 180},
                {'key': 'park', 'label': 'پارک', 'icon': 'fa-tree', 'color': '#059669', 'count': 211, 'nearest_m': 90},
            ],
            'gaps': [],
        }
        html = render_district_access_section(access, city='تهران', district='جردن')
        self.assertIn('mk-access-tally', html)
        self.assertIn('کلینیک', html)
        self.assertIn('پارک', html)
        self.assertIn('۲۲۴', html)
        self.assertIn('۲۱۱', html)
