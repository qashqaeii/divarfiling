from django.test import SimpleTestCase

from workspace.services.listing_edit import _input_meta_for_feature, listing_edit_payload


class ListingFeatureEditChoicesTests(SimpleTestCase):
    def test_catalog_fields_use_select_not_text(self):
        direction = _input_meta_for_feature('جهت ساختمان', 'شمالی')
        self.assertEqual(direction['input'], 'select')
        self.assertIn('شمالی', direction['choices'])
        self.assertIn('جنوبی', direction['choices'])

        floor = _input_meta_for_feature('جنس کف', '')
        self.assertEqual(floor['input'], 'select')
        self.assertIn('سرامیک', floor['choices'])

        bathroom = _input_meta_for_feature('سرویس بهداشتی', '')
        self.assertEqual(bathroom['input'], 'select')
        self.assertIn('فرنگی', bathroom['choices'])

        suitable = _input_meta_for_feature('مناسب برای', '')
        self.assertEqual(suitable['input'], 'select')
        self.assertIn('خانواده', suitable['choices'])

        cabinet = _input_meta_for_feature('جنس کابینت', '')
        self.assertEqual(cabinet['input'], 'select')
        self.assertIn('های‌گلاس', cabinet['choices'])

        unit_status = _input_meta_for_feature('وضعیت واحد', 'تخلیه')
        self.assertEqual(unit_status['input'], 'select')
        self.assertIn('تخلیه', unit_status['choices'])

    def test_unknown_value_is_kept_in_choices(self):
        meta = _input_meta_for_feature('جهت ساختمان', 'شمال شرقی')
        self.assertEqual(meta['choices'][0], 'شمال شرقی')
        self.assertIn('شمالی', meta['choices'])

    def test_boolish_fields_stay_tri(self):
        meta = _input_meta_for_feature('بازسازی شده', 'دارد')
        self.assertEqual(meta['input'], 'tri')
        self.assertEqual(meta['choices'], [])

    def test_payload_includes_select_choices(self):
        class Listing:
            id = 1
            dataset_id = 9
            token = 'abc123'
            title = 'آپارتمان'
            price = None
            deposit = 2_000_000_000
            rent = 1_000
            area = 130.0
            rooms = '3'
            neighborhood = 'بریانک'
            city = 'تهران'
            latitude = 35.6
            longitude = 51.4
            business_type = 'مشاور'
            link = 'https://divar.ir/v/x'
            description = 'خط اول'
            images = []
            is_expired = False
            data = {
                'جهت ساختمان': 'شمالی',
                'جنس کف': 'پارکت',
            }

        payload = listing_edit_payload(Listing())
        direction = next(f for f in payload['feature_fields'] if f['key'] == 'جهت ساختمان')
        self.assertEqual(direction['input'], 'select')
        self.assertIn('شمالی', direction['choices'])
        floor = next(f for f in payload['feature_fields'] if f['key'] == 'جنس کف')
        self.assertEqual(floor['input'], 'select')
        self.assertIn('پارکت', floor['choices'])
