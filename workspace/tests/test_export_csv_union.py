"""ستون‌های CSV خروجی دیتاست — union کلیدها."""
from django.test import SimpleTestCase

from workspace.services.export import export_csv_response


class ExportCsvUnionTests(SimpleTestCase):
    def test_extra_keys_in_later_rows_included(self):
        class Listing:
            def __init__(self, data, token='t', title='x'):
                self.data = data
                self.token = token
                self.title = title
                self.price = ''
                self.deposit = ''
                self.rent = ''
                self.area = ''
                self.neighborhood = ''
                self.city = ''
                self.link = ''

        listings = [
            Listing({'a': '1'}),
            Listing({'b': '2'}),
        ]
        resp = export_csv_response(listings, 'out.csv')
        body = resp.content.decode('utf-8-sig')
        self.assertIn('a', body.splitlines()[0])
        self.assertIn('b', body.splitlines()[0])
