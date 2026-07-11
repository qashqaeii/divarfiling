"""تست ذخیره پروفایل عمومی مشاور از داشبورد حساب."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.mixins import get_or_create_settings
from workspace.services.public_share_common import share_profile_context
from workspace.models import Dataset, Listing
from workspace.services.listing_public_share import get_or_create_listing_share

User = get_user_model()


class ConsultantProfileDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09123334455',
            phone='09123334455',
            password='testpass123',
        )
        self.client = Client()
        self.client.login(username='09123334455', password='testpass123')

    def test_dashboard_shows_consultant_social_form(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'consultantProfileForm')
        self.assertContains(resp, 'social_telegram')
        self.assertContains(resp, 'پروفایل عمومی مشاور')

    def test_update_consultant_profile_saves_socials_for_share(self):
        url = reverse('update_consultant_profile')
        resp = self.client.post(url, {
            'agency_name': 'آژانس تست',
            'default_welcome_message': 'برای بازدید تماس بگیرید',
            'social_telegram': '@dashagent',
            'social_bale': '09121112233',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        ws = get_or_create_settings(self.user)
        self.assertEqual(ws.agency_name, 'آژانس تست')
        self.assertEqual(ws.social_links.get('telegram'), 'dashagent')
        self.assertEqual(ws.social_links.get('bale'), '09121112233')
        self.assertIn('بازدید', ws.default_welcome_message)

        dataset = Dataset.objects.create(
            user=self.user,
            name='d',
            original_filename='d.xlsx',
            file_format='xlsx',
            transaction_type='فروش',
            subcategory='آپارتمان',
            city='تهران',
        )
        listing = Listing.objects.create(
            dataset=dataset,
            token='dashsoc1',
            title='ملک تست',
            price=1,
            area=80,
            city='تهران',
        )
        share = get_or_create_listing_share(self.user, listing)
        profile = share_profile_context(self.user, share, title=listing.title, share_url='https://ex.com/p/1/')
        keys = [c['key'] for c in profile['share_send_channels']]
        self.assertIn('telegram', keys)
        self.assertIn('bale', keys)
        active_keys = [n['key'] for n in profile['social_networks_active']]
        self.assertIn('telegram', active_keys)
        self.assertIn('bale', active_keys)

    def test_update_consultant_profile_saves_agency_fields(self):
        url = reverse('update_consultant_profile')
        resp = self.client.post(url, {
            'agency_name': 'دفتر آسمان',
            'default_welcome_message': 'سلام',
            'agency_address': 'ونک',
            'agency_city': 'تهران',
            'agency_landline': '02122223333',
            'agency_website': 'https://aseman.example',
            'agency_latitude': '35.76',
            'agency_longitude': '51.41',
            'social_telegram': '@me',
            'agency_social_bale': '09120001122',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        ws = get_or_create_settings(self.user)
        self.assertEqual(ws.agency_address, 'ونک')
        self.assertEqual(ws.agency_landline, '02122223333')
        self.assertEqual(ws.agency_website, 'https://aseman.example')
        self.assertAlmostEqual(ws.agency_latitude, 35.76)
        self.assertEqual(ws.social_links.get('telegram'), 'me')
        self.assertEqual(ws.agency_social_links.get('bale'), '09120001122')

    def test_dashboard_shows_agency_profile_fields(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'agency_address')
        self.assertContains(resp, 'agency_social_telegram')
        self.assertContains(resp, 'consultant_photo')
        self.assertContains(resp, 'business_card_image')
        self.assertContains(resp, 'دفتر املاک')
