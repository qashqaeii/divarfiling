"""تست fallback و context پیام CRM."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.context_builders.contact_context import (
    _format_match_line,
    _top_matches_text,
)
from ai_workspace.fallbacks.crm_message import build as build_crm_message

User = get_user_model()


class CrmMessageFallbackTests(TestCase):
    def test_matches_message_includes_public_urls(self):
        text = build_crm_message({
            'name': 'پریسا جعفری',
            'tone': 'رسمی',
            'channel': 'واتساپ',
            'customer_type': 'متقاضی اجاره',
            'areas': 'یوسف‌آباد، پونک',
            'top_matches': [
                {
                    'title': 'آپارتمان ۷۵ متری',
                    'deal_mode': 'رهن و اجاره',
                    'price_label': 'رهن ۲۵۰M / اجاره ۱۶M',
                    'neighborhood': 'یوسف‌آباد',
                    'city': 'تهران',
                    'score': 88,
                    'public_url': 'https://divarfiling.ir/p/abc123/',
                },
                {
                    'title': 'واحد ۵۰ متری',
                    'deal_mode': 'رهن و اجاره',
                    'price_label': 'رهن ۲۰۰M / اجاره ۱۸M',
                    'neighborhood': 'بریانک',
                    'city': 'تهران',
                    'score': 84,
                    'public_url': 'https://divarfiling.ir/p/def456/',
                },
            ],
        })
        self.assertIn('https://divarfiling.ir/p/abc123/', text)
        self.assertIn('https://divarfiling.ir/p/def456/', text)
        self.assertIn('امتیاز تطابق سیستم: 88٪', text)
        self.assertIn('یوسف‌آباد', text)

    def test_followup_without_matches(self):
        text = build_crm_message({
            'name': 'علی',
            'areas': 'سعادت‌آباد',
            'customer_type': 'خریدار',
            'status': 'در حال پیگیری',
            'tone': 'رسمی',
            'channel': 'واتساپ',
            'recent_activities': '—',
        })
        self.assertIn('سعادت‌آباد', text)
        self.assertNotIn('مشاهده جزئیات', text)


class ContactContextFormatTests(TestCase):
    def test_top_matches_text_includes_public_link(self):
        matches = [{
            'title': 'آپارتمان ۸۰ متری',
            'price_label': 'اجاره ۴۰M',
            'neighborhood': 'شهرک غرب',
            'score': 91,
            'public_url': 'https://divarfiling.ir/p/test/',
        }]
        text = _top_matches_text(matches)
        self.assertIn('لینک صفحه عمومی: https://divarfiling.ir/p/test/', text)
        self.assertIn('[امتیاز سیستم: 91%]', _format_match_line(1, matches[0]))


@override_settings(SITE_URL='https://divarfiling.ir')
class ContactContextPublicUrlTests(TestCase):
    @patch('ai_workspace.context_builders.contact_context.get_or_create_listing_share')
    @patch('ai_workspace.context_builders.contact_context.Listing')
    def test_resolve_listing_public_url(self, listing_model, get_share):
        user = User.objects.create_user(username='u1', password='x', phone='09120000001')
        listing = MagicMock()
        listing_model.objects.filter.return_value.first.return_value = listing
        share = MagicMock(share_token='toklisting1')
        get_share.return_value = share

        from ai_workspace.context_builders.contact_context import _resolve_match_public_url

        url = _resolve_match_public_url(user, {
            'source': 'divar',
            'listing_id': 10,
        })
        self.assertIn('https://divarfiling.ir', url)
        self.assertIn('toklisting1', url)
