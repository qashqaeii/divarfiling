"""Tests for district access scoring (no live Overpass)."""
from django.test import SimpleTestCase

from blog.services.market_article_access import (
    _adaptive_radius_m,
    _count_to_score,
    _geo_center,
    _score_access,
)
from blog.services.market_article_composer import _section_district_access


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

    def test_adaptive_radius_clamped(self):
        tight = [
            {'lat': 35.700, 'lng': 51.400},
            {'lat': 35.701, 'lng': 51.401},
            {'lat': 35.702, 'lng': 51.402},
        ]
        r = _adaptive_radius_m(tight)
        self.assertGreaterEqual(r, 900)
        self.assertLessEqual(r, 2000)

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

    def test_section_renders_when_ok(self):
        access = {
            'ok': True,
            'score': 76,
            'grade': 'B+',
            'grade_label': 'دسترسی خوب',
            'radius_label': '1200 متر',
            'summary': 'امتیاز نمونه',
            'total_pois': 42,
            'highlights': [{'label': 'سوپرمارکت', 'count': 5, 'nearest_m': 120}],
            'gaps': [{'label': 'آتش‌نشانی'}],
            'groups': [
                {
                    'key': 'daily',
                    'label': 'زندگی روزمره',
                    'score': 80,
                    'items': [
                        {
                            'key': 'supermarket',
                            'label': 'سوپرمارکت',
                            'icon': 'fa-cart-shopping',
                            'color': '#0891b2',
                            'count': 5,
                            'nearest_m': 120,
                        }
                    ],
                }
            ],
        }
        html = _section_district_access(access, city='تهران', district='جردن')
        self.assertIn('district-access', html)
        self.assertIn('mk-access-score', html)
        self.assertIn('سوپرمارکت', html)
        self.assertIn('76', html)

    def test_section_empty_when_not_ok(self):
        self.assertEqual(_section_district_access({'ok': False}, city='x', district='y'), '')
