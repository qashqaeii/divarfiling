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
    build_share_send_channels,
    normalize_social_links,
    render_share_message,
    resolve_welcome_message,
    sanitize_welcome_html,
    save_share_profile_defaults,
    share_profile_context,
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
            social_links={'telegram': '@testagent', 'bale': '09120001122'},
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
        self.assertEqual(out['telegram'], 'foo')
        self.assertNotIn('instagram', out)

    def test_normalize_social_accepts_username_and_phone(self):
        from workspace.services.public_share_common import resolve_social_href
        out = normalize_social_links({
            'telegram': '@MyAgent',
            'bale': '09121234567',
            'rubika': '۰۹۳۵۱۱۱۲۲۳۳',
            'eitaa': 'agent_id',
        })
        self.assertEqual(out['telegram'], 'MyAgent')
        self.assertEqual(out['bale'], '09121234567')
        self.assertEqual(out['rubika'], '09351112233')
        self.assertEqual(out['eitaa'], 'agent_id')
        self.assertEqual(resolve_social_href('telegram', out['telegram']), 'https://t.me/MyAgent')
        self.assertEqual(resolve_social_href('bale', out['bale']), 'https://ble.ir/9121234567')
        self.assertEqual(
            resolve_social_href('telegram', '09121234567'),
            'tg://resolve?phone=989121234567',
        )

    def test_render_share_message_placeholders(self):
        text = render_share_message(
            'ملک {title}\n{url}',
            title='آپارتمان',
            url='https://example.com/p/x/',
        )
        self.assertEqual(text, 'ملک آپارتمان\nhttps://example.com/p/x/')

    def test_share_send_channels_include_saved_socials(self):
        channels = build_share_send_channels({})
        self.assertEqual([c['key'] for c in channels], ['whatsapp'])

        channels = build_share_send_channels({
            'telegram': 'agent_tg',
            'bale': '09121112233',
            'instagram': '',
        })
        keys = [c['key'] for c in channels]
        self.assertEqual(keys[0], 'whatsapp')
        self.assertIn('telegram', keys)
        self.assertIn('bale', keys)
        self.assertNotIn('instagram', keys)
        tg = next(c for c in channels if c['key'] == 'telegram')
        self.assertEqual(tg['mode'], 'telegram')
        bale = next(c for c in channels if c['key'] == 'bale')
        self.assertEqual(bale['mode'], 'copy_open')
        self.assertIn('ble.ir', bale['href'])

        share = get_or_create_listing_share(self.user, self.listing)
        save_share_profile_defaults(
            self.user,
            social_links={'telegram': '@desk', 'rubika': 'myrubika'},
            save_socials=True,
        )
        profile = share_profile_context(self.user, share, title='x', share_url='https://ex.com/p/1/')
        send_keys = [c['key'] for c in profile['share_send_channels']]
        self.assertEqual(send_keys[0], 'whatsapp')
        self.assertIn('telegram', send_keys)
        self.assertIn('rubika', send_keys)

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
            'social_telegram': '@agency',
            'social_rubika': '09123334455',
            'is_active': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        ws = get_or_create_settings(self.user)
        self.assertIn('پیام پیش‌فرض', ws.default_welcome_message)
        self.assertIn('{title}', ws.default_share_message)
        self.assertEqual(ws.social_links.get('telegram'), 'agency')
        self.assertEqual(ws.social_links.get('rubika'), '09123334455')
        share = ListingPublicShare.objects.get(listing=self.listing, created_by=self.user, is_active=True)
        self.assertEqual(share.welcome_message, '')

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_listing_detail_has_pro_share_modal(self, _mock):
        save_share_profile_defaults(
            self.user,
            social_links={'telegram': '@agency', 'bale': '09120001122'},
            save_socials=True,
        )
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
        self.assertContains(resp, 'data-share-msg-send')
        self.assertContains(resp, 'data-send-mode="telegram"')
        self.assertContains(resp, 'data-send-mode="copy_open"')
        self.assertContains(resp, 'data-send-key="bale"')

    def test_build_map_navigation_includes_balad(self):
        from workspace.services.public_share_common import build_map_navigation
        nav = build_map_navigation(35.7, 51.4)
        self.assertIsNotNone(nav)
        self.assertIn('balad.ir/directions', nav['balad_url'])
        self.assertIn('35.7,51.4', nav['balad_url'])
        self.assertIn('google.com/maps', nav['google_url'])
        self.assertIn('neshan.org', nav['neshan_url'])
        self.assertIn('waze.com', nav['waze_url'])
        self.assertIsNone(build_map_navigation(None, 51.4))
        self.assertIsNone(build_map_navigation(0, 0))

    def test_consultant_block_agency_profile_conditional(self):
        from workspace.services.public_share_common import build_consultant_block
        ws = get_or_create_settings(self.user)
        ws.agency_name = 'آژانس نگین'
        ws.agency_address = 'ولیعصر، پلاک ۱'
        ws.agency_city = 'تهران'
        ws.agency_landline = '02188776655'
        ws.agency_website = 'https://negin.example'
        ws.agency_latitude = 35.7
        ws.agency_longitude = 51.4
        ws.social_links = {'telegram': 'person_tg'}
        ws.agency_social_links = {'instagram': 'office_ig'}
        ws.save()
        share = get_or_create_listing_share(self.user, self.listing)
        block = build_consultant_block(self.user, share, title=self.listing.title)
        self.assertTrue(block['has_agency_address'])
        self.assertTrue(block['has_agency_landlines'])
        self.assertTrue(block['has_agency_website'])
        self.assertTrue(block['has_office_navigation'])
        self.assertIn('balad.ir', block['agency']['map_navigation']['balad_url'])
        self.assertTrue(block['has_consultant_socials'])
        self.assertTrue(block['has_agency_socials'])
        self.assertEqual(block['consultant_social_networks'][0]['key'], 'telegram')
        self.assertEqual(block['agency_social_networks'][0]['key'], 'instagram')
        # بدون مختصات، مسیریابی دفتر نباشد
        ws.agency_latitude = None
        ws.agency_longitude = None
        ws.agency_address = ''
        ws.agency_city = ''
        ws.agency_landline = ''
        ws.agency_website = ''
        ws.agency_social_links = {}
        ws.save()
        block2 = build_consultant_block(self.user, share, title=self.listing.title)
        self.assertFalse(block2['has_agency_address'])
        self.assertFalse(block2['has_agency_landlines'])
        self.assertFalse(block2['has_agency_website'])
        self.assertFalse(block2['has_office_navigation'])
        self.assertFalse(block2['has_agency_socials'])
        self.assertTrue(block2['has_consultant_socials'])

    def test_share_profile_context_has_agency_fields(self):
        ws = get_or_create_settings(self.user)
        ws.agency_address = 'سعادت‌آباد'
        ws.agency_landline = '02111112222'
        ws.agency_social_links = {'telegram': 'office_tg'}
        ws.save()
        share = get_or_create_listing_share(self.user, self.listing)
        profile = share_profile_context(self.user, share, title='x', share_url='https://ex.com/p/1/')
        self.assertEqual(profile['agency_address'], 'سعادت‌آباد')
        self.assertEqual(profile['agency_landline'], '02111112222')
        self.assertTrue(any(n['key'] == 'telegram' for n in profile['agency_social_networks']))
        self.assertIn('agency_social_networks', profile)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_saves_agency_profile(self, _mock):
        self.client.login(username='09129876543', password='testpass123')
        url = reverse(
            'workspace:listing_share',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.post(url, {
            'consultant_name': '',
            'consultant_phone': '',
            'agency_address': 'جردن، پلاک ۱۰',
            'agency_city': 'تهران',
            'agency_landline': '02199887766',
            'agency_website': 'negin.ir',
            'agency_latitude': '35.75',
            'agency_longitude': '51.42',
            'social_telegram': '@person',
            'agency_social_instagram': '@officebrand',
            'is_active': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        ws = get_or_create_settings(self.user)
        self.assertEqual(ws.agency_address, 'جردن، پلاک ۱۰')
        self.assertEqual(ws.agency_city, 'تهران')
        self.assertEqual(ws.agency_landline, '02199887766')
        self.assertEqual(ws.agency_website, 'https://negin.ir')
        self.assertAlmostEqual(ws.agency_latitude, 35.75)
        self.assertAlmostEqual(ws.agency_longitude, 51.42)
        self.assertEqual(ws.social_links.get('telegram'), 'person')
        self.assertEqual(ws.agency_social_links.get('instagram'), 'officebrand')
        share = ListingPublicShare.objects.get(listing=self.listing, created_by=self.user, is_active=True)
        ctx = build_public_listing_context(share)
        self.assertContains(
            self.client.get(reverse('listing_public:view', kwargs={'share_token': share.share_token})),
            'مسیریابی به دفتر',
        )
        self.assertTrue(ctx['consultant']['has_office_navigation'])
        self.assertContains(
            self.client.get(reverse('listing_public:view', kwargs={'share_token': share.share_token})),
            'balad.ir/directions',
        )