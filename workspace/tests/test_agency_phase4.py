"""تست‌های فاز ۴ — Activity, Export UI, Documents, Renewal."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import AgencyActivityEvent, AgencySubscription, CRMAgencyMember, Customer, CustomerDocument
from workspace.services.agency_entitlement import get_active_subscription_for_owner, provision_subscription_from_paid_order
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_seats import assign_seat_to_member

User = get_user_model()


class AgencyPhase4Base(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-p4-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.phones = [f'0915{base + i:07d}' for i in range(4)]
        self.owner = User.objects.create_user(username=self.phones[0], phone=self.phones[0], password='x')
        self.advisor = User.objects.create_user(username=self.phones[1], phone=self.phones[1], password='x')

    def _order(self, qty=2):
        order = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=qty, amount=qty * 990_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        return order


class ActivityInstrumentationTests(AgencyPhase4Base):
    def test_contact_created_emits_event(self):
        order = self._order()
        agency = create_or_link_agency(self.owner, 'Act Agency')
        member = CRMAgencyMember.objects.create(
            agency=agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        Customer.objects.create(user=self.advisor, agency=agency, name='X', phone='09120001111')
        self.assertTrue(
            AgencyActivityEvent.objects.filter(
                agency=agency, event_type='contact_created',
            ).exists()
        )


class RenewalTests(AgencyPhase4Base):
    def test_active_renewal_extends_subscription(self):
        order1 = self._order(qty=2)
        sub1 = provision_subscription_from_paid_order(order1)
        agency = create_or_link_agency(self.owner, 'Renew Agency')
        sub1.agency = agency
        sub1.save()
        old_exp = sub1.expires_at
        order2 = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=2, amount=1_980_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order2)
        sub2 = provision_subscription_from_paid_order(order2)
        self.assertNotEqual(sub1.pk, sub2.pk)
        self.assertGreater(sub2.expires_at, old_exp)
        self.assertEqual(sub2.agency_id, agency.id)

    def test_expired_renewal_reactivates(self):
        order1 = self._order()
        sub1 = provision_subscription_from_paid_order(order1)
        agency = create_or_link_agency(self.owner, 'Exp Renew')
        sub1.agency = agency
        sub1.save(update_fields=['agency'])
        member = CRMAgencyMember.objects.create(
            agency=agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        lic = License.objects.filter(agency_subscription=sub1).first()
        assign_seat_to_member(self.owner, lic.pk, self.advisor.pk)
        sub1.expires_at = timezone.now() - timedelta(days=1)
        sub1.status = AgencySubscription.STATUS_EXPIRED
        sub1.save(update_fields=['expires_at', 'status'])
        order2 = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=2, amount=1_980_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order2)
        sub2 = provision_subscription_from_paid_order(order2)
        self.assertEqual(sub2.agency_id, agency.id)
        self.assertTrue(get_active_subscription_for_owner(self.owner))
        self.assertTrue(CRMAgencyMember.objects.filter(pk=member.pk, is_active=True).exists())
        lic.refresh_from_db()
        self.assertEqual(lic.agency_subscription_id, sub2.pk)
        self.assertEqual(lic.assigned_user_id, self.advisor.pk)


class TeamExportUITests(AgencyPhase4Base):
    def test_hub_advisors_page_has_export_form(self):
        self._order()
        create_or_link_agency(self.owner, 'Export UI')
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('workspace:agency_hub_advisors'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'خروجی تیمی')

    def test_team_export_post(self):
        self._order()
        agency = create_or_link_agency(self.owner, 'Export Post')
        CRMAgencyMember.objects.create(
            agency=agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        Customer.objects.create(user=self.advisor, agency=agency, name='C', phone='09123334444')
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('workspace:agency_team_export'), {
            'type': 'contacts', 'format': 'csv', 'all_members': '1',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])


class DocumentDownloadTests(AgencyPhase4Base):
    def test_cross_agency_document_denied(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self._order()
        agency = create_or_link_agency(self.owner, 'Doc A')
        member = CRMAgencyMember.objects.create(
            agency=agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        doc = CustomerDocument.objects.create(
            user=self.advisor, title='f', file=SimpleUploadedFile('t.txt', b'x'),
        )
        other = User.objects.create_user(username=self.phones[2], phone=self.phones[2], password='x')
        self.client.force_login(other)
        url = reverse('workspace:agency_advisor_document', kwargs={
            'member_id': member.pk, 'document_id': doc.pk,
        })
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403, 404))
