"""تست اشتراک عمومی فایل شخصی CRM."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMProperty, CRMPropertyPublicShare
from workspace.services.nearby_pois import PAYLOAD_VERSION
from workspace.services.property_public_share import (
    build_public_property_context,
    get_or_create_property_share,
)

User = get_user_model()


class PropertyPublicShareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09129876543',
            phone='09129876543',
            password='testpass123',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ویلای ۲۰۰ متری',
            deal_mode='فروش',
            property_type='ویلا',
            city='تهران',
            neighborhood='نیاوران',
            sale_price=12_000_000_000,
            area=200,
            rooms='4',
            notes='یادداشت محرمانه',
            address='خیابان تست ۱۲',
        )
        self.client = Client()

    def test_get_or_create_share_is_idempotent(self):
        s1 = get_or_create_property_share(self.user, self.prop)
        s2 = get_or_create_property_share(self.user, self.prop)
        self.assertEqual(s1.pk, s2.pk)
        self.assertTrue(s1.share_token)

    def test_build_context_hides_notes_by_default(self):
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        self.assertEqual(ctx['dossier_badge'], 'فایل شخصی')
        self.assertNotIn('یادداشت محرمانه', ctx['description_text'])

    def test_highlights_do_not_duplicate_core_amenities(self):
        self.prop.has_parking = True
        self.prop.has_storage = True
        self.prop.has_elevator = True
        self.prop.property_type = 'آپارتمان'
        self.prop.save(update_fields=['has_parking', 'has_storage', 'has_elevator', 'property_type'])
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        core_labels = [
            item['label']
            for item in ctx['feature_profile']['core']
            if item.get('known') and item.get('state') == 'yes'
        ]
        self.assertEqual(set(core_labels), {'پارکینگ', 'انباری', 'آسانسور'})
        self.assertEqual(ctx['feature_highlights'], ['آپارتمان'])

    def test_amenities_text_overrides_false_core_flags(self):
        self.prop.amenities = 'آسانسور، پارکینگ، انباری، لابی'
        self.prop.has_parking = False
        self.prop.has_storage = False
        self.prop.has_elevator = False
        self.prop.save(update_fields=[
            'amenities', 'has_parking', 'has_storage', 'has_elevator',
        ])
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        core = {item['label']: item['state'] for item in ctx['feature_profile']['core']}
        self.assertEqual(core['آسانسور'], 'yes')
        self.assertEqual(core['پارکینگ'], 'yes')
        self.assertEqual(core['انباری'], 'yes')
        extra_labels = [
            item['label']
            for group in ctx['feature_profile']['groups']
            for item in group['items']
        ]
        self.assertEqual(extra_labels, ['لابی'])
        self.assertEqual(ctx['feature_profile']['source_label'], 'ثبت‌شده در فایل شخصی')

    def test_amenities_show_real_values_not_just_bool(self):
        self.prop.amenities = (
            'آسانسور، پارکینگ، '
            'تعداد واحد در طبقه: ۲، '
            'تعداد پارکینگ: ۱، '
            'جنس کف: سرامیک، '
            'بالکن ندارد، '
            'لابی'
        )
        self.prop.has_elevator = False
        self.prop.has_parking = False
        self.prop.has_storage = False
        self.prop.save(update_fields=[
            'amenities', 'has_elevator', 'has_parking', 'has_storage',
        ])
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        core = {item['label']: item['value'] for item in ctx['feature_profile']['core']}
        self.assertEqual(core['آسانسور'], 'دارد')
        self.assertEqual(core['پارکینگ'], 'دارد')
        by_label = {
            item['label']: item
            for group in ctx['feature_profile']['groups']
            for item in group['items']
        }
        self.assertEqual(by_label['تعداد واحد در طبقه']['value'], '۲')
        self.assertEqual(by_label['تعداد واحد در طبقه']['state'], 'neutral')
        self.assertEqual(by_label['تعداد پارکینگ']['value'], '۱')
        self.assertEqual(by_label['جنس کف']['value'], 'سرامیک')
        self.assertEqual(by_label['بالکن']['value'], 'ندارد')
        self.assertEqual(by_label['لابی']['value'], 'دارد')
        self.assertNotEqual(by_label['تعداد واحد در طبقه']['value'], 'دارد')

        from workspace.services.property_public_share import build_property_amenity_dossier_items
        dossier = build_property_amenity_dossier_items(self.prop)
        by_d = {i['label']: i for i in dossier}
        self.assertEqual(by_d['آسانسور']['emoji'], '⬆️')
        self.assertEqual(by_d['آسانسور']['icon'], 'fa-elevator')
        self.assertEqual(by_d['پارکینگ']['state'], 'yes')
        self.assertEqual(by_d['پارکینگ']['tip'], 'پارکینگ: دارد')
        self.assertEqual(by_d['پارکینگ']['icon'], 'fa-square-parking')
        self.assertEqual(by_d['تعداد واحد در طبقه']['value'], '۲')
        self.assertEqual(by_d['تعداد واحد در طبقه']['emoji'], '🚪')
        self.assertEqual(by_d['تعداد واحد در طبقه']['icon'], 'fa-door-closed')
        self.assertEqual(by_d['تعداد واحد در طبقه']['tip'], 'تعداد واحد در طبقه: ۲')
        self.assertEqual(by_d['جنس کف']['value'], 'سرامیک')
        self.assertEqual(by_d['بالکن']['state'], 'no')
        self.assertEqual(by_d['بالکن']['icon'], 'fa-fan')
        self.assertTrue(by_d['آسانسور']['is_core'])
        self.assertFalse(by_d['لابی']['is_core'])

        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'تعداد واحد در طبقه')
        self.assertContains(resp, '۲')
        self.assertContains(resp, 'سرامیک')

    def test_build_context_shows_notes_when_enabled(self):
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptoken123',
            property=self.prop,
            created_by=self.user,
            show_internal_notes=True,
        )
        ctx = build_public_property_context(share)
        self.assertIn('یادداشت محرمانه', ctx['description_text'])

    def test_public_page_renders(self):
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptoken456',
            property=self.prop,
            created_by=self.user,
        )
        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ویلای ۲۰۰ متری')
        self.assertContains(resp, 'فایل شخصی')
        self.assertContains(resp, '09129876543')

    def test_public_page_shows_navigation_when_coords_exist(self):
        self.prop.latitude = 35.781
        self.prop.longitude = 51.412
        self.prop.save(update_fields=['latitude', 'longitude'])
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptokenmap',
            property=self.prop,
            created_by=self.user,
        )
        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مسیریابی')
        self.assertContains(resp, 'google.com/maps/dir')
        self.assertContains(resp, 'neshan.org/maps/routing')

    def test_inactive_share_returns_410(self):
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptoken789',
            property=self.prop,
            created_by=self.user,
            is_active=False,
        )
        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 410)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_json(self, _mock_license):
        self.client.login(username='09129876543', password='testpass123')
        url = reverse('workspace:crm_property_public_share', kwargs={'property_id': self.prop.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('share_url', data)
        self.assertIn('/p/f/', data['share_url'])

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_can_deactivate(self, _mock_license):
        self.client.login(username='09129876543', password='testpass123')
        url = reverse('workspace:crm_property_public_share', kwargs={'property_id': self.prop.pk})
        resp = self.client.post(url, {
            'consultant_name': '',
            'consultant_phone': '',
            'welcome_message': '',
        })
        self.assertEqual(resp.status_code, 302)
        share = CRMPropertyPublicShare.objects.get(property=self.prop, created_by=self.user)
        self.assertFalse(share.is_active)


class PropertyAmenityCheckboxFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121112233',
            phone='09121112233',
            password='testpass123',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان تست امکانات',
            deal_mode='فروش',
            property_type='آپارتمان',
            has_parking=True,
            has_elevator=False,
            has_storage=True,
            amenities='بالکن، لابی، جنس کف: سرامیک، استخر ندارد',
        )

    def test_split_and_serialize_roundtrip(self):
        from workspace.services.property_public_share import (
            serialize_amenity_checkboxes,
            split_amenities_for_checkbox_form,
        )

        selected, leftover = split_amenities_for_checkbox_form(
            self.prop.amenities,
            has_parking=self.prop.has_parking,
            has_storage=self.prop.has_storage,
            has_elevator=self.prop.has_elevator,
        )
        self.assertIn('پارکینگ', selected)
        self.assertIn('انباری', selected)
        self.assertIn('بالکن', selected)
        self.assertIn('لابی', selected)
        self.assertNotIn('آسانسور', selected)
        self.assertNotIn('استخر', selected)
        self.assertIn('جنس کف: سرامیک', leftover)

        text = serialize_amenity_checkboxes(
            ['پارکینگ', 'انباری', 'بالکن', 'لابی', 'جکوزی'],
            leftover,
        )
        self.assertIn('بالکن', text)
        self.assertIn('لابی', text)
        self.assertIn('جکوزی', text)
        self.assertIn('جنس کف: سرامیک', text)
        self.assertNotIn('پارکینگ', text)

    def test_form_save_syncs_flags_and_amenities(self):
        from workspace.forms import CRMPropertyForm

        form = CRMPropertyForm(instance=self.prop)
        groups = form.amenity_checkbox_groups()
        flat = {item['label']: item['checked'] for g in groups for item in g['items']}
        self.assertTrue(flat['پارکینگ'])
        self.assertNotIn('بالکن', flat)  # در بخش ویژگی‌ها
        self.assertNotIn('استخر', flat)
        self.assertFalse(flat['آسانسور'])
        self.assertEqual(form.fields['amenities_extra'].initial, 'جنس کف: سرامیک')
        # seed از امکانات قدیمی
        feat_items = {
            item['key']: item
            for group in form.feature_form_context()['groups']
            for item in group['items']
        }
        self.assertTrue(feat_items['بالکن']['checked'])

        data = {
            'title': self.prop.title,
            'property_type': self.prop.property_type,
            'deal_mode': self.prop.deal_mode,
            'transaction_status': self.prop.transaction_status or 'فعال',
            'publish_status': self.prop.publish_status or 'خصوصی',
            'amenity_flags': ['پارکینگ', 'آسانسور', 'روف گاردن'],
            'amenities_extra': 'جنس کف: پارکت',
            'feat_profile': 'sale',
            'feat__استخر': 'دارد',
            'feat__بالکن': 'دارد',
        }
        form = CRMPropertyForm(data, instance=self.prop)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertTrue(saved.has_parking)
        self.assertTrue(saved.has_elevator)
        self.assertFalse(saved.has_storage)
        self.assertIn('استخر', saved.amenities)
        self.assertIn('بالکن', saved.amenities)
        self.assertIn('روف گاردن', saved.amenities)
        self.assertIn('جنس کف: پارکت', saved.amenities)
        self.assertNotIn('پارکینگ', saved.amenities)
        self.assertEqual(saved.feature_data.get('استخر'), 'دارد')


class PropertyDistrictAndPriceFormTests(TestCase):
    def setUp(self):
        from workspace.models import Dataset, Listing

        self.user = User.objects.create_user(
            username='09123334455',
            phone='09123334455',
            password='testpass123',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست منطقه',
            original_filename='فروش_آپارتمان.xlsx',
            file_format='xlsx',
            city='تهران',
            district='منطقه ۳',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='tokdistrict1',
            title='آپارتمان نیاوران',
            city='تهران',
            neighborhood='نیاوران',
            price=10_000_000_000,
            area=120,
            data={'منطقه': 'منطقه ۳'},
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان نیاوران',
            deal_mode='فروش',
            property_type='آپارتمان',
            city='تهران',
            neighborhood='نیاوران',
            district='',
            token='tokdistrict1',
            sale_price=10_000_000_000,
            area=120,
        )

    def test_district_from_listing_uses_data_and_dataset(self):
        from workspace.services.listing_edit import district_from_listing

        self.assertEqual(district_from_listing(self.listing), 'منطقه ۳')
        self.listing.data = {}
        self.listing.save(update_fields=['data'])
        self.assertEqual(district_from_listing(self.listing), 'منطقه ۳')

    def test_form_hydrates_district_from_source_listing(self):
        from workspace.forms import CRMPropertyForm

        form = CRMPropertyForm(instance=self.prop)
        self.assertEqual(form.initial.get('district'), 'منطقه ۳')
        self.assertIn('منطقه ۳', form['district'].value() or '')

    def test_property_from_listing_sets_district(self):
        from workspace.services.crm import property_from_listing

        created = property_from_listing(self.user, self.listing)
        self.assertEqual(created.district, 'منطقه ۳')
        self.assertEqual(created.neighborhood, 'نیاوران')
        self.assertEqual(created.deal_mode, 'فروش')
        self.assertEqual(created.sale_price, 10_000_000_000)

    def test_rent_listing_maps_deal_mode_and_prices(self):
        from workspace.services.crm import property_from_listing

        self.listing.price = None
        self.listing.deposit = 500_000_000
        self.listing.rent = 25_000_000
        self.listing.token = 'tokrent1'
        self.listing.save()
        created = property_from_listing(self.user, self.listing)
        self.assertEqual(created.deal_mode, 'رهن و اجاره')
        self.assertEqual(created.deposit, 500_000_000)
        self.assertEqual(created.monthly_rent, 25_000_000)


class AmenityCategoryCoverageTests(TestCase):
    """پوشش امکانات در همه دسته‌ها، چیپ ترکیبی، و ادغام آگهی→پرونده."""

    def setUp(self):
        from workspace.models import Dataset, Listing

        self.user = User.objects.create_user(
            username='09125556677',
            phone='09125556677',
            password='testpass123',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='پوشش امکانات',
            original_filename='فروش_آپارتمان.xlsx',
            file_format='xlsx',
            city='تهران',
            district='منطقه ۱',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='tokcover1',
            title='پوشش کامل امکانات',
            city='تهران',
            neighborhood='فرمانیه',
            price=20_000_000_000,
            area=150,
            data={
                'آسانسور': 'ندارد',
                'پارکینگ': 'ندارد',
                'انباری': 'ندارد',
                'ویژگی‌ها و امکانات': 'لابی دارد | استخر دارد | روف گاردن دارد | آیفون تصویری',
                'جنس کف': 'سرامیک',
                'سرمایش': 'اسپیلت',
                'گرمایش': 'پکیج',
                'بالکن': 'دارد',
                'جکوزی': 'دارد',
                'سونا': 'ندارد',
                'حیوان خانگی مجاز': 'خیر',
                'تعداد پارکینگ': '۲',
                'تعداد واحد در طبقه': '۴',
                'جهت ساختمان': 'شمالی',
                'امکانات': 'نگهبانی، سرایداری، آنتن مرکزی',
            },
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='پوشش کامل امکانات',
            deal_mode='فروش',
            property_type='آپارتمان',
            token='tokcover1',
            amenities='',
            has_parking=False,
            has_storage=False,
            has_elevator=False,
        )

    def test_combined_and_chip_amenities_in_extract_features(self):
        from workspace.services.features import extract_listing_features

        feat = extract_listing_features(self.listing)
        self.assertTrue(feat['lobby'])
        self.assertTrue(feat['pool'])
        self.assertTrue(feat['roof_garden'])
        self.assertTrue(feat['balcony'])
        self.assertTrue(feat['jacuzzi'])
        self.assertIn('لابی', feat['amenities'])
        self.assertIn('استخر', feat['amenities'])

    def test_listing_profile_covers_all_feature_groups(self):
        from workspace.services.features import extract_listing_features
        from workspace.services.listing_features import build_listing_feature_profile

        profile = build_listing_feature_profile(
            self.listing, extract_listing_features(self.listing),
        )
        group_ids = {g['id'] for g in profile['groups']}
        self.assertIn('comfort', group_ids)
        self.assertIn('luxury', group_ids)
        self.assertIn('lifestyle', group_ids)
        self.assertIn('counts', group_ids)
        self.assertIn('building', group_ids)
        by_label = {
            item['label']: item
            for group in profile['groups']
            for item in group['items']
        }
        self.assertEqual(by_label['جنس کف']['value'], 'سرامیک')
        self.assertEqual(by_label['سرمایش']['value'], 'اسپیلت')
        self.assertEqual(by_label['تعداد پارکینگ']['value'], '۲')
        self.assertEqual(by_label['لابی']['state'], 'yes')
        self.assertEqual(by_label['استخر']['state'], 'yes')
        self.assertEqual(by_label['نگهبانی']['state'], 'yes')
        self.assertEqual(by_label['آنتن مرکزی']['icon'], 'fa-satellite-dish')
        self.assertEqual(by_label['جکوزی']['icon'], 'fa-hot-tub-person')

    def test_dossier_merges_listing_when_amenities_empty(self):
        from workspace.services.property_public_share import build_property_amenity_dossier_items

        dossier = build_property_amenity_dossier_items(self.prop)
        by_d = {i['label']: i for i in dossier}
        self.assertIn('پارکینگ', by_d)
        self.assertEqual(by_d['پارکینگ']['state'], 'no')
        self.assertEqual(by_d['لابی']['state'], 'yes')
        self.assertEqual(by_d['استخر']['tip'], 'استخر: دارد')
        self.assertEqual(by_d['جنس کف']['value'], 'سرامیک')
        self.assertEqual(by_d['سرمایش']['value'], 'اسپیلت')
        self.assertEqual(by_d['تعداد پارکینگ']['value'], '۲')
        self.assertEqual(by_d['نگهبانی']['icon'], 'fa-user-shield')
        self.assertEqual(by_d['روف گاردن']['icon'], 'fa-seedling')

    def test_comma_chip_list_explodes(self):
        from workspace.services.listing_features import _collect_raw_features

        raw = _collect_raw_features({
            'امکانات': 'لابی، استخر، روف گاردن',
        })
        self.assertEqual(raw.get('لابی'), 'دارد')
        self.assertEqual(raw.get('استخر'), 'دارد')
        self.assertEqual(raw.get('روف گاردن'), 'دارد')


class PropertyPublicNearbyPoisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121112222', phone='09121112222', password='testpass123',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='دفتر کار',
            deal_mode='اجاره',
            property_type='اداری',
            city='اصفهان',
            neighborhood='تیران',
            latitude=32.654,
            longitude=51.668,
        )
        self.client = Client()
        self.client.login(username='09121112222', password='testpass123')
        self.share_url = reverse(
            'workspace:crm_property_public_share',
            kwargs={'property_id': self.prop.pk},
        )

    def _sample_nearby_payload(self):
        return {
            'version': PAYLOAD_VERSION,
            'coords': {'lat': 32.654, 'lng': 51.668},
            'radius_m': 3000,
            'fetched_at_label': '۱۴۰۴/۰۴/۲۹',
            'found_count': 2,
            'items': [
                {
                    'key': 'mosque', 'group': 'religion', 'label': 'مسجد',
                    'icon': 'fa-mosque', 'color': '#0d9488', 'found': True,
                    'name': 'مسجد تست', 'distance_m': 200, 'distance_label': '۲۰۰ متر',
                    'walk_label': 'حدود ۳ دقیقه پیاده',
                },
                {
                    'key': 'metro', 'group': 'transport', 'label': 'مترو',
                    'icon': 'fa-train-subway', 'color': '#7c3aed', 'found': False,
                    'empty_label': 'یافت نشد',
                },
            ],
            'groups': [],
            'highlights': [],
        }

    def test_public_context_shows_nearby_when_enabled(self):
        self.prop.nearby_pois = self._sample_nearby_payload()
        self.prop.save(update_fields=['nearby_pois'])
        share = CRMPropertyPublicShare.objects.create(
            share_token='nearbytok1',
            property=self.prop,
            created_by=self.user,
            show_nearby_pois=True,
        )
        ctx = build_public_property_context(share)
        self.assertIsNotNone(ctx['public_nearby_pois'])
        self.assertEqual(ctx['public_nearby_pois']['found_count'], 1)
        self.assertEqual(len(ctx['public_nearby_pois']['groups']), 1)

    def test_public_page_renders_access_section(self):
        self.prop.nearby_pois = self._sample_nearby_payload()
        self.prop.save(update_fields=['nearby_pois'])
        share = CRMPropertyPublicShare.objects.create(
            share_token='nearbytok2',
            property=self.prop,
            created_by=self.user,
            show_nearby_pois=True,
            approximate_location=True,
        )
        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ps-access')
        self.assertContains(resp, 'دسترسی‌های اطراف')
        self.assertContains(resp, 'مسجد تست')

    def test_share_save_rejects_without_coords(self):
        self.prop.latitude = None
        self.prop.longitude = None
        self.prop.save(update_fields=['latitude', 'longitude'])
        resp = self.client.post(self.share_url, {
            'show_nearby_pois': '1',
            'is_active': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('موقعیت', resp.json()['error'])

    def test_share_save_rejects_without_data(self):
        resp = self.client.post(self.share_url, {
            'show_nearby_pois': '1',
            'is_active': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('محاسبه', resp.json()['error'])

    def test_share_save_accepts_when_ready(self):
        self.prop.nearby_pois = self._sample_nearby_payload()
        self.prop.save(update_fields=['nearby_pois'])
        resp = self.client.post(self.share_url, {
            'show_nearby_pois': '1',
            'is_active': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        share = CRMPropertyPublicShare.objects.get(property=self.prop, created_by=self.user)
        self.assertTrue(share.show_nearby_pois)
