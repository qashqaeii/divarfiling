from django.test import SimpleTestCase

from accounts.services.divar_places import (
    list_cities_for_province_slug,
    list_provinces_for_select,
    places_config_available,
    province_label,
    resolve_province_slug,
)


class DivarPlacesTests(SimpleTestCase):
    def test_places_file_loads(self):
        if not places_config_available():
            self.skipTest('places-web.json not on disk')
        provinces = list_provinces_for_select()
        self.assertGreater(len(provinces), 25)
        self.assertEqual(resolve_province_slug('tehran'), 'tehran-province')
        self.assertEqual(province_label('tehran'), 'تهران')
        cities = list_cities_for_province_slug('tehran-province')
        names = [c[0] for c in cities]
        self.assertIn('تهران', names)
