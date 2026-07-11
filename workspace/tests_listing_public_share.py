"""تست اشتراک عمومی آگهی."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import Dataset, Listing, ListingPublicShare
from workspace.services.listing_public_share import (
    build_public_listing_context,
    format_sections_public,
    get_or_create_listing_share,
)
from workspace.services.display import build_listing_display_data, transaction_profile
from workspace.services.features import extract_listing_features

User = get_user_model()


class ListingPublicShareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121234567',
            phone='09121234567',
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
            token='abc123',
            title='آپارتمان ۱۰۰ متری',
            price=5_000_000_000,
            area=100,
            rooms='2',
            neighborhood='ونک',
            city='تهران',
            description='توضیحات تست',
            data={
                'شماره تماس': '09111111111',
                'طبقه': '3',
                'پارکینگ': 'دارد',
            },
        )
        self.client = Client()

    def test_get_or_create_share_is_idempotent(self):
        s1 = get_or_create_listing_share(self.user, self.listing)
        s2 = get_or_create_listing_share(self.user, self.listing)
        self.assertEqual(s1.pk, s2.pk)
        self.assertTrue(s1.share_token)

    def test_public_sections_hide_contact(self):
        feat = extract_listing_features(self.listing)
        data = build_listing_display_data(self.listing, feat)
        tx = transaction_profile(self.dataset.transaction_type)
        sections = format_sections_public(data, tx)
        self.assertNotIn('تماس', sections)
        for fields in sections.values():
            for key in fields:
                self.assertNotIn('شماره تماس', key)

    def test_build_context_consultant_phone_fallback(self):
        share = get_or_create_listing_share(self.user, self.listing)
        ctx = build_public_listing_context(share)
        self.assertEqual(ctx['consultant']['phone'], '09121234567')
        self.assertTrue(ctx['consultant']['has_phone'])

    def test_public_page_renders(self):
        share = ListingPublicShare.objects.create(
            share_token='testtoken123',
            listing=self.listing,
            created_by=self.user,
        )
        url = reverse('listing_public:view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'آپارتمان ۱۰۰ متری')
        self.assertContains(resp, '09121234567')
        self.assertNotContains(resp, '09111111111')

    def test_inactive_share_returns_410(self):
        share = ListingPublicShare.objects.create(
            share_token='inactivetoken1',
            listing=self.listing,
            created_by=self.user,
            is_active=False,
        )
        url = reverse('listing_public:view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 410)

    def test_share_manage_requires_login(self):
        url = reverse(
            'workspace:listing_share',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_json(self, _mock_license):
        self.client.login(username='09121234567', password='testpass123')
        url = reverse(
            'workspace:listing_share',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('share_url', data)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_listing_detail_share_form_has_csrf(self, _mock_license):
        self.client.login(username='09121234567', password='testpass123')
        url = reverse(
            'workspace:listing_detail',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="form-listing-share"')
        self.assertContains(resp, 'name="csrfmiddlewaretoken"')
        self.assertRegex(resp.content.decode(), r'name="csrfmiddlewaretoken"\s+value="[^"]+"')

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_can_deactivate(self, _mock_license):
        self.client.login(username='09121234567', password='testpass123')
        url = reverse(
            'workspace:listing_share',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.post(url, {
            'consultant_name': '',
            'consultant_phone': '',
            'welcome_message': '',
        })
        self.assertEqual(resp.status_code, 302)
        share = ListingPublicShare.objects.get(listing=self.listing, created_by=self.user)
        self.assertFalse(share.is_active)

    def test_public_page_shows_description_once(self):
        long_desc = 'این واحد نورگیر است و دسترسی عالی به مترو دارد. مناسب خانواده.'
        self.listing.description = long_desc
        self.listing.data = {
            **(self.listing.data or {}),
            'توضیحات': long_desc,
            'متن آگهی': long_desc,
        }
        self.listing.save(update_fields=['description', 'data'])
        share = ListingPublicShare.objects.create(
            share_token='desctoken001',
            listing=self.listing,
            created_by=self.user,
            welcome_message=long_desc,
        )
        ctx = build_public_listing_context(share)
        self.assertEqual(ctx['description_text'], long_desc)
        self.assertFalse(ctx['consultant']['has_welcome'])
        for fields in (ctx['sections'] or {}).values():
            for key, val in fields.items():
                self.assertNotIn('توضیح', key)
                self.assertNotEqual(val.strip(), long_desc)

        url = reverse('listing_public:view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertEqual(body.count(long_desc), 1)
        self.assertContains(resp, 'توضیحات آگهی')
        self.assertNotContains(resp, 'پیام مشاور')
        self.assertNotContains(resp, 'متن آگهی')

    def test_public_context_prunes_hero_and_description_sections(self):
        share = get_or_create_listing_share(self.user, self.listing)
        ctx = build_public_listing_context(share)
        self.assertNotIn('توضیحات', ctx['sections'])
        self.assertNotIn('شرایط مالی', ctx['sections'])
        self.assertNotIn('مشخصات اصلی', ctx['sections'])
        self.assertEqual(ctx['description_text'], 'توضیحات تست')

    def test_public_hides_consultant_active_ads_and_agency_name(self):
        self.listing.data = {
            **(self.listing.data or {}),
            'آگهی‌های فعال مشاور': '۲۴۷ آگهی فعال',
            'مشاور_آگهی_فعال': '۲۴۷ آگهی فعال',
            'نام مشاور / آژانس': 'املاک آتی زعفرانیه',
            'بالکن': 'دارد',
        }
        self.listing.save(update_fields=['data'])
        share = get_or_create_listing_share(self.user, self.listing)
        ctx = build_public_listing_context(share)

        blob_parts = []
        for fields in (ctx['sections'] or {}).values():
            blob_parts.extend(fields.keys())
            blob_parts.extend(str(v) for v in fields.values())
        for group in ctx.get('supplementary_groups') or []:
            for f in group.get('fields') or []:
                blob_parts.append(str(f.get('key') or ''))
                blob_parts.append(str(f.get('display') or f.get('raw') or ''))
        for h in ctx.get('feature_highlights') or []:
            blob_parts.append(str(h))
        for group in (ctx.get('feature_profile') or {}).get('groups') or []:
            for item in group.get('items') or []:
                blob_parts.append(str(item.get('key') or item.get('label') or ''))
                blob_parts.append(str(item.get('value') or ''))
        blob = '\n'.join(blob_parts)

        self.assertNotIn('آگهی‌های فعال مشاور', blob)
        self.assertNotIn('۲۴۷ آگهی فعال', blob)
        self.assertNotIn('نام مشاور / آژانس', blob)
        self.assertNotIn('املاک آتی زعفرانیه', blob)

        url = reverse('listing_public:view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'آگهی‌های فعال مشاور')
        self.assertNotContains(resp, '۲۴۷ آگهی فعال')
        self.assertNotContains(resp, 'نام مشاور / آژانس')
