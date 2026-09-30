"""Agency Space — property detail page UI shell."""
from django.urls import reverse

from workspace.models import AgencySpaceItem
from workspace.services.agency_space_publish import publish_property
from workspace.tests.test_agency_space_phase1 import AgencySpaceTestBase


class AgencySpacePropertyDetailTests(AgencySpaceTestBase):
    def test_property_detail_page_renders_new_layout(self):
        prop = self._prop()
        item = publish_property(
            self.advisor,
            prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )
        self.client.force_login(self.advisor2)
        url = reverse('workspace:agency_hub_space_item', kwargs={'item_id': item.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'جزئیات فایل')
        self.assertContains(resp, 'مشخصات اصلی')
        self.assertContains(resp, 'agency-space-property-detail')
        self.assertContains(resp, 'کپی به CRM من')
