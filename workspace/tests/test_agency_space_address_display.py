from types import SimpleNamespace

from django.test import SimpleTestCase

from workspace.services.agency_space_serialize import (
    _property_address_for_display,
    _property_address_redundant_with_fields,
)


class PropertyAddressDisplayTests(SimpleTestCase):
    def _prop(self, **kwargs):
        defaults = {
            'city': '',
            'district': '',
            'neighborhood': '',
            'address': '',
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_hides_address_when_equals_neighborhood(self):
        prop = self._prop(
            city='تهران',
            district='سعادت آباد',
            neighborhood='سعادت آباد',
            address='سعادت آباد',
        )
        self.assertTrue(_property_address_redundant_with_fields(prop))
        self.assertEqual(_property_address_for_display(prop), '')

    def test_shows_address_when_has_extra_detail(self):
        prop = self._prop(
            city='تهران',
            district='سعادت آباد',
            neighborhood='سعادت آباد',
            address='خیابان پاک، پلاک ۱۲',
        )
        self.assertFalse(_property_address_redundant_with_fields(prop))
        self.assertEqual(_property_address_for_display(prop), 'خیابان پاک، پلاک ۱۲')

    def test_hides_combined_city_neighborhood_only(self):
        prop = self._prop(
            city='تهران',
            district='سعادت آباد',
            neighborhood='سعادت آباد',
            address='سعادت آباد، تهران',
        )
        self.assertTrue(_property_address_redundant_with_fields(prop))
