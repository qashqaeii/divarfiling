"""Agency Space — contact detail page & serialize privacy."""
from django.urls import reverse

from licenses.models import License
from workspace.models import AgencySpaceItem
from workspace.services.agency_seats import assign_seat_to_member
from workspace.services.agency_space_publish import publish_customer
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.tests.test_agency_space_phase1 import AgencySpaceTestBase


class AgencySpaceContactDetailTests(AgencySpaceTestBase):
    def _seat_advisor2(self):
        lic = (
            License.objects.filter(agency_subscription=self.sub)
            .order_by('pk')
            .exclude(assigned_user_id=self.advisor.pk)
            .first()
        )
        if lic is None:
            lic = License.objects.filter(agency_subscription=self.sub).order_by('-pk').first()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)

    def test_summary_detail_no_phone_or_notes_in_payload(self):
        c = self._customer(phone='09121112233', notes='secret note')
        item = publish_customer(
            self.advisor,
            c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        data = serialize_space_item(item, self.advisor2, detail=True)
        self.assertEqual(data['customer']['phone'], '')
        self.assertEqual(data['customer'].get('notes', ''), '')
        self.assertFalse(data['customer']['has_phone'])

    def test_full_detail_shows_phone_when_authorized(self):
        c = self._customer(
            phone='09127776655',
            budget_min=1_000_000_000,
            budget_max=5_000_000_000,
        )
        item = publish_customer(
            self.advisor,
            c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_FULL,
        )
        data = serialize_space_item(item, self.advisor2, detail=True)
        self.assertEqual(data['customer']['phone'], '09127776655')
        self.assertTrue(data['customer']['has_phone'])
        self.assertTrue(data['customer']['budget_rows'])

    def test_contact_detail_page_renders_hero_and_privacy(self):
        c = self._customer(phone='09120001111', notes='private')
        item = publish_customer(
            self.advisor,
            c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        self.client.force_login(self.advisor2)
        url = reverse('workspace:agency_hub_space_item', kwargs={'item_id': item.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'جزئیات مخاطب')
        self.assertContains(resp, 'نیاز مخاطب')
        self.assertContains(resp, 'اطلاعات تماس در این سطح اشتراک نمایش داده نمی‌شود')
        self.assertNotContains(resp, '09120001111')
        self.assertNotContains(resp, 'private')

    def test_contact_detail_shows_copy_cta(self):
        self._seat_advisor2()
        c = self._customer()
        item = publish_customer(
            self.advisor,
            c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        self.client.force_login(self.advisor2)
        url = reverse('workspace:agency_hub_space_item', kwargs={'item_id': item.pk})
        resp = self.client.get(url)
        self.assertContains(resp, 'ذخیره در مخاطبین من')
        self.assertContains(resp, 'مخاطب منتشرشدهٔ تیم عوض نمی‌شود')
