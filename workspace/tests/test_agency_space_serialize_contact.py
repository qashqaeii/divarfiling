"""Regression: جزئیات مخاطب فضای آژانس نباید ۵۰۰ بدهد."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
import uuid

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import CRMAgencyMember, Customer
from workspace.services.agency_onboarding import link_agency_to_subscription
from workspace.services.agency_seats import assign_seat_to_member
from workspace.services.agency_space_publish import publish_customer
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.services.crm_agency import create_agency
from workspace.services.agency_entitlement import provision_subscription_from_paid_order

User = get_user_model()


class AgencySpaceContactDetailSerializeTests(TestCase):
    def setUp(self):
        self.feature_patch = patch.dict(
            'workspace.constants.AGENCY_COMMAND_CENTER_FEATURES',
            {'agency_space': True},
            clear=False,
        )
        self.feature_patch.start()
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        phone = f'0915{base:07d}'
        self.user = User.objects.create_user(username=phone, phone=phone, password='x')
        self.agency = create_agency(self.user, 'آژانس تست مخاطب')
        product = Product.objects.create(
            title='Agency',
            slug=f'ag-c-{uuid.uuid4().hex[:8]}',
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
            user=self.user,
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
        CRMAgencyMember.objects.filter(agency=self.agency, user=self.user).update(
            role='advisor',
            is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        lic = License.objects.filter(agency_subscription=sub).order_by('pk').first()
        if lic:
            assign_seat_to_member(self.user, lic.pk, self.user.pk)
        self.customer = Customer.objects.create(
            user=self.user,
            agency=self.agency,
            name='مخاطب تست',
            customer_type='خریدار',
            phone='09121112233',
        )

    def tearDown(self):
        self.feature_patch.stop()

    def test_contact_detail_serialize_for_publisher(self):
        item = publish_customer(self.user, self.customer.pk, visibility='agency_public')
        payload = serialize_space_item(item, self.user, detail=True)
        self.assertIsNotNone(payload)
        self.assertIn('contact_share_level_label', payload)
        self.assertIsNotNone(payload.get('customer'))
