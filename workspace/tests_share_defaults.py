"""تست پیش‌فرض اشتراک، پیام خوش‌آمد و شبکه‌های اجتماعی."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.mixins import get_or_create_settings
from workspace.models import Dataset, Listing, ListingPublicShare
from workspace.services.listing_public_share import (
    build_public_listing_context,
    get_or_create_listing_share,
)
from workspace.services.public_share_common import (
    normalize_social_links,
    render_share_message,
    resolve_welcome_message,
    sanitize_welcome_html,
    save_share_profile_defaults,
)

User = get_user_model()


class ShareDefaultsAndSocialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09129876543',
            phone='09129876543',
            password='testpass123',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='test.xlsx',
            file_format='xlsx',
            transaction_type='فروش',
            subcategory='آپارتمان',
            city='تهران',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='sharedef1',
            title='ویلای شمال',
            price=10_000_000_000,
            area=200,
            city='تهران',
            description='توضیح',
            data={},
        )
        self.client = Client()

    def test_sanitize_welcome_strips_script(self):
        html = sanitize_welcome_html('<b>سلام</b><script>alert(1)</script><a href="javascript:alert(1)">x</a>')
        self.assertIn('<b>سلام</b>', html)
        self.assertNotIn('script', html.lower())
        self.assertNotIn('javascript:', html.lower())

    def test_default_welcome_used_when_share_empty(self):
        save_share_profile_defaults(
            self.user,
            default_welcome_message='<p>برای بازدید هماهنگ کنید</p>',
            save_welcome=True,
        )
        share = get_or_create_listing_share(self.user, self.listing)
        self.assertEqual(share.welcome_message, '')
        resolved = resolve_welcome_message(self.user, share)
        self.assertTrue(resolved['from_default'])
        self.assertIn('بازدید', resolved['welcome_plain'])
        ctx = build_public_listing_context(share)
        self.assertTrue(ctx['consultant']['has_welcome'])
        self.assertIn('بازدید', ctx['consultant']['welcome_message'])

    def test_social_links_on_public_page(self):
        save_share_profile_defaults(
            self.user,
            social_links={'telegram': 'https://t.me/testagent', 'bale': 'ble.ir/agent'},
            save_socials=True,
        )
        share = ListingPublicShare.objects.create(
            share_token='socialtok12',
            listing=self.listing,
            created_by=self.user,
        )
        ctx = build_public_listing_context(share)
        self.assertTrue(ctx['consultant']['has_socials'])
        keys = {n['key'] for n in ctx['consultant']['social_networks']}
        self.assertIn('telegram', keys)
        self.assertIn('bale', keys)
        url = reverse('listing_public:view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 't.me/testagent')
        self.assertContains(resp, 'بله')

    def test_normalize_social_adds_https(self):
        out = normalize_social_links({'telegram': 't.me/foo', 'instagram': ''})
        self.assertEqual(out['telegram'], 'https://t.me/foo')
        self.assertNotIn('instagram', out)

    def test_render_share_message_placeholders(self):
        text = render_share_message(
            'ملک {title}\n{url}',
            title='آپارتمان',
            url='https://example.com/p/x/',
        )
        self.assertEqual(text, 'ملک آپارتمان\nhttps://example.com/p/x/')

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_saves_defaults_and_socials(self, _mock):
        self.client.login(username='09129876543', password='testpass123')
        url = reverse(
            'workspace:listing_share',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.post(url, {
            'consultant_name': '',
            'consultant_phone': '',
            'welcome_message': '<b>پیام پیش‌فرض من</b>',
            'save_as_default_welcome': '1',
            'share_message_template': 'سلام {title}\n{url}',
            'save_as_default_share_message': '1',
            'social_telegram': 'https://t.me/agency',
            'social_rubika': 'https://rubika.ir/agency',
            'is_active': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        ws = get_or_create_settings(self.user)
        self.assertIn('پیام پیش‌فرض', ws.default_welcome_message)
        self.assertIn('{title}', ws.default_share_message)
        self.assertEqual(ws.social_links.get('telegram'), 'https://t.me/agency')
        self.assertEqual(ws.social_links.get('rubika'), 'https://rubika.ir/agency')
        share = ListingPublicShare.objects.get(listing=self.listing, created_by=self.user, is_active=True)
        self.assertEqual(share.welcome_message, '')

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_listing_detail_has_pro_share_modal(self, _mock):
        self.client.login(username='09129876543', password='testpass123')
        url = reverse(
            'workspace:listing_detail',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-share-tabs')
        self.assertContains(resp, 'data-welcome-rte')
        self.assertContains(resp, 'social_telegram')
        self.assertContains(resp, 'save_as_default_share_message')
