"""Tests for district access scoring and article HTML (no live Overpass)."""
from django.test import SimpleTestCase

from blog.services.market_article_access import (
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

    def test_cafe_restaurant_categories_exist(self):
        keys = {c['key'] for c in POI_CATEGORIES}
        self.assertIn('cafe', keys)
        self.assertIn('restaurant', keys)
        self.assertIn('police', keys)
        self.assertIn('fire_station', keys)

    def test_section_renders_crm_style_when_ok(self):
        access = {
            'ok': True,
            'score': 76,
            'grade': 'B+',
            'grade_label': 'دسترسی خوب',
            'radius_label': '۳ کیلومتر',
            'summary': 'امتیاز نمونه',
            'total_pois': 42,
            'found_count': 18,
            'total_count': 24,
            'missing_count': 6,
            'highlights': [
                {
                    'label': 'سوپرمارکت',
                    'name': 'افق کوروش',
                    'distance_label': '۲۷ متر',
                    'walk_label': 'حدود ۱ دقیقه پیاده',
                    'icon': 'fa-cart-shopping',
                    'color': '#0891b2',
                    'count': 5,
                    'found': True,
                }
            ],
            'gaps': [{'label': 'آتش‌نشانی'}],
            'groups': [
                {
                    'key': 'daily',
                    'label': 'زندگی روزمره',
                    'found_count': 2,
                    'items': [
                        {
                            'key': 'supermarket',
                            'label': 'سوپرمارکت',
                            'name': 'افق کوروش',
                            'icon': 'fa-cart-shopping',
                            'color': '#0891b2',
                            'count': 5,
                            'found': True,
                            'distance_label': '۲۷ متر',
                            'walk_label': 'حدود ۱ دقیقه پیاده',
                        },
                        {
                            'key': 'cafe',
                            'label': 'کافه',
                            'name': 'کافه نادری',
                            'icon': 'fa-mug-saucer',
                            'color': '#a16207',
                            'count': 8,
                            'found': True,
                            'distance_label': '۱۲۰ متر',
                            'walk_label': 'حدود ۲ دقیقه پیاده',
                        },
                        {
                            'key': 'restaurant',
                            'label': 'رستوران',
                            'icon': 'fa-utensils',
                            'color': '#b45309',
                            'count': 0,
                            'found': False,
                            'empty_label': 'در شعاع ۳ کیلومتر یافت نشد',
                        },
                    ],
                },
                {
                    'key': 'safety',
                    'label': 'امنیت و خدمات',
                    'found_count': 2,
                    'items': [
                        {
                            'key': 'police',
                            'label': 'کلانتری',
                            'name': 'نیروی انتظامی',
                            'icon': 'fa-shield-halved',
                            'color': '#1d4ed8',
                            'count': 2,
                            'found': True,
                            'distance_label': '۵۸۰ متر',
                            'walk_label': 'حدود ۷ دقیقه پیاده',
                        },
                        {
                            'key': 'fire_station',
                            'label': 'آتش‌نشانی',
                            'name': 'ایستگاه ۸۴',
                            'icon': 'fa-fire-extinguisher',
                            'color': '#b45309',
                            'count': 1,
                            'found': True,
                            'distance_label': '۷۱۰ متر',
                            'walk_label': 'حدود ۹ دقیقه پیاده',
                        },
                    ],
                },
            ],
        }
        html = _section_district_access(access, city='تهران', district='جردن')
        self.assertIn('district-access', html)
        self.assertIn('امکانات و دسترسی‌های منطقه', html)
        self.assertIn('سوپرمارکت', html)
        self.assertIn('۵ مورد', html)
        self.assertIn('کافه', html)
        self.assertIn('کلانتری', html)
        self.assertIn('آتش‌نشانی', html)
        self.assertIn('mk-poi-item__count', html)
        self.assertIn('حدود ۱ دقیقه پیاده', html)

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
