"""تست fallback اتاق/طبقه در سریالایزر API موبایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from mobile_api.serializers import listing_detail_to_dict, listing_to_dict
from workspace.models import Dataset, Listing

User = get_user_model()


class ListingSerializerFallbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121112233', password='test')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='test.xlsx',
            file_format='xlsx',
        )

    def test_rooms_from_data_column_when_model_empty(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-data-rooms',
            title='آپارتمان ۴۹ متری',
            price=6_400_000_000,
            area=49,
            rooms='',
            data={'اتاق': '۲', 'طبقه': '۳', 'ساخت': '۱۳۹۵'},
        )
        row = listing_to_dict(listing)
        self.assertEqual(row['rooms'], 2)
        self.assertEqual(row['floor'], '3')
        self.assertEqual(row['year_built'], '1395')

    def test_rooms_from_description_when_columns_missing(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-desc-rooms',
            title='واحد نوساز',
            price=5_000_000_000,
            area=85,
            description='۱۰۵متر دو خواب\nطبقه ۴ از ۶',
            data={},
        )
        detail = listing_detail_to_dict(listing)
        self.assertEqual(detail['rooms'], 2)
        self.assertEqual(detail['floor'], '4')
        self.assertEqual(detail['total_floors'], '6')

    def test_ignores_dash_placeholders_in_data(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-dash',
            title='۳ خواب طبقه ۲',
            price=1_000_000_000,
            area=100,
            data={'اتاق': '-', 'طبقه': '—'},
        )
        row = listing_to_dict(listing)
        self.assertEqual(row['rooms'], 3)
        self.assertEqual(row['floor'], '2')

    def test_zero_rooms_for_studio_label(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-studio',
            title='سوئیت',
            price=2_000_000_000,
            area=35,
            data={'اتاق': 'بدون اتاق'},
        )
        row = listing_to_dict(listing)
        self.assertEqual(row['rooms'], 0)

    def test_detail_includes_amenity_fields(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-amenities',
            title='آپارتمان با امکانات',
            price=5_000_000_000,
            area=90,
            data={
                'پارکینگ': 'دارد',
                'انباری': 'ندارد',
                'آسانسور': 'دارد',
                'وضعیت واحد': 'تخلیه',
            },
        )
        detail = listing_detail_to_dict(listing)
        self.assertTrue(detail['has_parking'])
        self.assertFalse(detail['has_storage'])
        self.assertTrue(detail['has_elevator'])
        self.assertEqual(detail['unit_status'], 'تخلیه')
