"""Agency Space — Mobile API parity tests."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import CRMAgencyMember, CRMProperty, Customer
from workspace.services.agency_entitlement import provision_subscription_from_paid_order
from workspace.services.agency_onboarding import link_agency_to_subscription
from workspace.services.agency_seats import assign_seat_to_member
from workspace.services.agency_space_publish import publish_property
from workspace.services.crm_agency import create_agency
import uuid

User = get_user_model()


class AgencySpaceMobileApiTests(TestCase):
    def setUp(self):
        self.feature_patch = patch.dict(
            'workspace.constants.AGENCY_COMMAND_CENTER_FEATURES',
            {'agency_space': True},
            clear=False,
        )
        self.feature_patch.start()
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        phone = f'0915{base:07d}'
        self.advisor = User.objects.create_user(username=phone, phone=phone, password='x')
        self.agency = create_agency(self.advisor, 'آژانس موبایل Space')
        product = Product.objects.create(
            title='Agency Space Mobile',
            slug=f'ag-sp-m-{uuid.uuid4().hex[:8]}',
            description='t',
            is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product,
            name='Agency',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=1,
            max_quantity=10,
            is_active=True,
        )
        order = Order.objects.create(
            user=self.advisor,
            product=product,
            plan=plan,
            quantity=1,
            amount=990_000,
            status='paid',
            paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        sub = provision_subscription_from_paid_order(order)
        link_agency_to_subscription(self.agency, sub)
        self.sub = sub
        CRMAgencyMember.objects.filter(agency=self.agency, user=self.advisor).update(
            role='advisor',
            is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        lic = License.objects.filter(agency_subscription=sub).order_by('pk').first()
        if lic:
            assign_seat_to_member(self.advisor, lic.pk, self.advisor.pk)

        self.prop = CRMProperty.objects.create(
            user=self.advisor,
            agency=self.agency,
            title='ملک Space موبایل',
            city='تهران',
            deal_mode='فروش',
            sale_price=5_000_000_000,
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.advisor)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def tearDown(self):
        self.feature_patch.stop()

    def test_agency_home_capabilities(self):
        resp = self.client.get('/api/mobile/v1/agency/home')
        self.assertEqual(resp.status_code, 200)
        caps = resp.json()['data']['capabilities']
        self.assertTrue(caps['agency_space_enabled'])
        self.assertTrue(caps['can_access_agency_space'])
        self.assertTrue(caps['can_publish_agency_space'])

    def test_list_and_detail_and_copy_flow(self):
        item = publish_property(self.advisor, self.prop.pk, visibility='agency_public')
        listed = self.client.get('/api/mobile/v1/agency/space/items', {'tab': 'properties'})
        self.assertEqual(listed.status_code, 200)
        body = listed.json()['data']
        self.assertGreaterEqual(body['total'], 1)
        self.assertTrue(any(i['id'] == item.pk for i in body['items']))

        detail = self.client.get(f'/api/mobile/v1/agency/space/items/{item.pk}')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['data']['item']['id'], item.pk)

        other = User.objects.create_user(
            username='09159998877',
            phone='09159998877',
            password='x',
        )
        CRMAgencyMember.objects.create(
            agency=self.agency,
            user=other,
            role='manager',
            is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        other_client = APIClient()
        other_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(other).access_token}',
        )
        copied = other_client.post(f'/api/mobile/v1/agency/space/items/{item.pk}/copy')
        self.assertEqual(copied.status_code, 200)
        self.assertIn('target_id', copied.json()['data'])

    def test_publish_from_property_payload(self):
        resp = self.client.get(f'/api/mobile/v1/crm/properties/{self.prop.pk}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['agency_space']['can_publish'])
        pub = self.client.post(
            '/api/mobile/v1/agency/space/publish/property',
            {'property_id': self.prop.pk, 'visibility': 'agency_public'},
            format='json',
        )
        self.assertEqual(pub.status_code, 201)
        item_id = pub.json()['data']['item']['id']
        unp = self.client.post(f'/api/mobile/v1/agency/space/items/{item_id}/unpublish')
        self.assertEqual(unp.status_code, 200)

    def test_property_detail_includes_source_context(self):
        resp = self.client.get(f'/api/mobile/v1/crm/properties/{self.prop.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('agency_space', resp.json()['data'])

    def test_feature_disabled_returns_not_found(self):
        self.feature_patch.stop()
        with patch.dict(
            'workspace.constants.AGENCY_COMMAND_CENTER_FEATURES',
            {'agency_space': False},
            clear=False,
        ):
            resp = self.client.get('/api/mobile/v1/agency/space/items')
            self.assertEqual(resp.status_code, 404)
