"""تست fallback اتاق/طبقه در سریالایزر API موبایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from mobile_api.serializers import listing_detail_to_dict, listing_to_dict
from workspace.models import Customer, CustomerListing, Dataset, Listing

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

    def test_list_row_includes_amenity_fields(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-list-amenities',
            title='آپارتمان',
            price=5_000_000_000,
            area=90,
            data={
                'پارکینگ': 'دارد',
                'انباری': 'دارد',
                'آسانسور': 'دارد',
            },
        )
        row = listing_to_dict(listing)
        self.assertTrue(row['has_parking'])
        self.assertTrue(row['has_storage'])
        self.assertTrue(row['has_elevator'])

    def test_detail_includes_feature_profile(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-feature-profile',
            title='آپارتمان کامل',
            price=8_000_000_000,
            area=120,
            data={
                'پارکینگ': 'دارد',
                'انباری': 'دارد',
                'آسانسور': 'دارد',
                'نوع سند': 'تک‌برگ',
                'گرمایش': 'شوفاژ',
                'سرمایش': 'اسپلیت',
                'جنس کف': 'سرامیک',
            },
        )
        detail = listing_detail_to_dict(listing)
        self.assertIn('feature_profile', detail)
        profile = detail['feature_profile']
        self.assertTrue(profile.get('has_details') or profile.get('groups'))
        self.assertIn('listing_highlights', detail)
        self.assertIsInstance(detail['listing_highlights'], list)

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
        self.assertTrue(detail['is_vacant'])
        self.assertIn('feature_fields', detail)
        floor = next(f for f in detail['feature_fields'] if f['key'] == 'جنس کف')
        self.assertEqual(floor['input'], 'select')
        self.assertIn('سرامیک', floor['choices'])
        self.assertIn('address', detail)
        self.assertIn('tenant_name', detail)
        self.assertIn('has_balcony', detail)
        self.assertIn('meta', detail)
        self.assertIn('linked_contacts', detail)
        self.assertIsInstance(detail['linked_contacts'], list)
        self.assertFalse(detail['meta']['is_favorite'])

    def test_detail_includes_market_benchmark(self):
        cheap = Listing.objects.create(
            dataset=self.dataset,
            token='tok-mkt-cheap',
            title='ارزان',
            price=10_000_000_000,
            area=100,
            neighborhood='جردن',
        )
        Listing.objects.create(
            dataset=self.dataset,
            token='tok-mkt-mid',
            title='میانه',
            price=20_000_000_000,
            area=100,
            neighborhood='جردن',
        )
        expensive = Listing.objects.create(
            dataset=self.dataset,
            token='tok-mkt-high',
            title='گران',
            price=40_000_000_000,
            area=100,
            neighborhood='جردن',
        )
        detail = listing_detail_to_dict(expensive)
        self.assertIn('market', detail)
        market = detail['market']
        self.assertEqual(market['market_tier'], 'over')
        self.assertEqual(market['short_verdict'], 'بالای بازار')
        self.assertGreater(market['diff_pct'], 12)
        self.assertTrue(market['market_median_fmt'])
        self.assertTrue(market['listing_metric_fmt'])
        self.assertTrue(market['diff_amount_fmt'])
        self.assertGreaterEqual(market['sample_count'], 3)
        cheap_detail = listing_detail_to_dict(cheap)
        self.assertIn('market', cheap_detail)
        self.assertEqual(cheap_detail['market']['market_tier'], 'under')
        self.assertEqual(cheap_detail['market']['short_verdict'], 'زیر بازار')
        self.assertIsNotNone(cheap_detail['market']['diff_pct'])
        self.assertLess(cheap_detail['market']['diff_pct'], -12)

    def test_linked_contacts_matching_owner_and_tenant_phones_get_roles(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-occupancy-roles',
            title='آپارتمان',
            price=8_000_000_000,
            area=90,
            data={
                'شماره تماس': '09121112233',
                'نام مالک': 'علی رضایی',
                'شماره مستاجر': '09123334455',
                'نام مستاجر': 'سارا محمدی',
            },
        )
        owner = Customer.objects.create(user=self.user, name='علی رضایی', phone='09121112233')
        tenant = Customer.objects.create(user=self.user, name='سارا محمدی', phone='09123334455')
        CustomerListing.objects.create(customer=owner, token=listing.token, role='پیشنهادی')
        CustomerListing.objects.create(customer=tenant, token=listing.token, role='پیشنهادی')
        detail = listing_detail_to_dict(listing, user=self.user)
        roles = {row['phone']: row['role'] for row in detail['linked_contacts']}
        self.assertEqual(roles['09121112233'], 'مالک')
        self.assertEqual(roles['09123334455'], 'مستاجر')
