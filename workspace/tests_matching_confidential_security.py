"""Regression امنیت اشتراک محرمانه در Matching و لینک عمومی."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from workspace.models import (
    CRMAgency,
    CRMAgencyMember,
    CRMProperty,
    CRMPropertyPublicShare,
    CRMResourceShare,
    Customer,
)
from workspace.services.crm_matching import get_customer_matches
from workspace.services.crm_match_notifications import record_match_alerts
from workspace.services.crm_sharing import share_property
from workspace.services.property_public_share import get_or_create_property_share
from workspace.services.property_suggestion_share import (
    enrich_match_with_links,
    public_share_url_for_property,
)

User = get_user_model()


class ConfidentialMatchingSecurityRegressionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='09121110001', phone='09121110001', password='x')
        self.advisor = User.objects.create_user(username='09121110002', phone='09121110002', password='x')
        self.agency = CRMAgency.objects.create(name='آژانس امنیت', owner=self.owner)
        CRMAgencyMember.objects.create(agency=self.agency, user=self.owner, role='owner', is_active=True)
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
        )
        self.buyer = Customer.objects.create(
            user=self.advisor,
            agency=self.agency,
            name='خریدار',
            phone='09123330000',
            customer_type='خریدار',
            budget_min=8_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='ملک مخفی',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=12_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
            token='secret-crm-token',
            link='https://divar.ir/v/secret',
        )
        share_property(
            self.owner,
            self.prop,
            self.advisor_member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
        )
        self.factory = RequestFactory()

    def test_match_reasons_do_not_leak_price_or_neighborhood(self):
        data = get_customer_matches(self.buyer, self.advisor, divar_enabled=False)
        match = next(m for m in data['crm_matches'] if m['property_id'] == self.prop.pk)
        reasons_text = ' '.join(match.get('reasons') or [])
        self.assertNotIn('ونک', reasons_text)
        self.assertNotIn('۱۲', reasons_text)
        self.assertNotIn('میلیارد', reasons_text)
        self.assertEqual(match.get('token'), '')

    def test_enrich_strips_forged_urls_after_mask(self):
        forged = {
            'source': 'crm',
            'property_id': self.prop.pk,
            'public_share_url': 'https://evil.example/p/leak',
            'internal_url': 'https://evil.example/workspace/1',
            'link': 'https://divar.ir/v/leak',
            'reasons': ['محله ونک — ۱۲ میلیارد'],
            'token': 'leak-token',
        }
        out = enrich_match_with_links(self.advisor, self.factory.get('/'), forged)
        self.assertEqual(out.get('public_share_url'), '')
        self.assertEqual(out.get('internal_url'), '')
        self.assertEqual(out.get('link'), '')
        self.assertEqual(out.get('token'), '')
        self.assertNotIn('ونک', ' '.join(out.get('reasons') or []))

    def test_advisor_cannot_create_public_share(self):
        self.assertEqual(public_share_url_for_property(self.advisor, self.factory.get('/'), self.prop), '')
        with self.assertRaises(PermissionDenied):
            get_or_create_property_share(self.advisor, self.prop)
        self.assertFalse(
            CRMPropertyPublicShare.objects.filter(property=self.prop, created_by=self.advisor).exists()
        )

    def test_owner_can_create_public_share(self):
        share = get_or_create_property_share(self.owner, self.prop)
        self.assertTrue(share.share_token)
        url = public_share_url_for_property(self.owner, self.factory.get('/'), self.prop)
        self.assertIn('/p/', url)

    def test_alert_snapshot_masked_for_confidential(self):
        alerts = record_match_alerts(
            self.advisor,
            self.buyer,
            [{
                'source': 'crm',
                'property_id': self.prop.pk,
                'title': 'عنوان حساس',
                'price_label': '۱۲ میلیارد',
                'neighborhood': 'ونک',
                'reasons': ['محله ونک', '۱۲ میلیارد تومان'],
                'score': 88,
                'match_key': f'crm:{self.prop.pk}',
            }],
        )
        self.assertEqual(len(alerts), 1)
        snap = alerts[0].match_snapshot
        self.assertNotIn('ونک', snap.get('neighborhood', ''))
        self.assertNotIn('۱۲', snap.get('price_label', ''))
        self.assertNotIn('میلیارد', ' '.join(snap.get('reasons') or []))
