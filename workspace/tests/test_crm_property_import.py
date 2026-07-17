"""Tests for CRM personal property Excel/CSV import."""
import io

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from workspace.models import CRMProperty
from workspace.services.crm_property_import import (
    _parse_money,
    import_properties_from_file,
)


User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver'])
class CRMPropertyImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='prop_imp', phone='09121112233', password='x')

    def _xlsx(self, rows):
        buf = io.BytesIO()
        pd.DataFrame(rows).to_excel(buf, index=False)
        buf.seek(0)
        return SimpleUploadedFile(
            'props.xlsx',
            buf.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_invalid_money_does_not_raise(self):
        self.assertIsNone(_parse_money('قیمت فروش (تومان)'))
        self.assertEqual(_parse_money('1,200,000'), 1200000)

    def test_header_row_and_bad_money_do_not_500(self):
        f = self._xlsx([
            {'عنوان': 'عنوان', 'قیمت فروش (تومان)': 'قیمت فروش (تومان)'},
            {'عنوان': 'آپارتمان الف', 'قیمت فروش (تومان)': 'abc'},
            {'عنوان': 'ویلا ب', 'قیمت فروش (تومان)': 900000000},
        ])
        created, skipped, errors = import_properties_from_file(self.user, f)
        self.assertEqual(created, 2)
        self.assertGreaterEqual(skipped, 1)
        self.assertEqual(errors, [])
        titles = set(CRMProperty.objects.filter(user=self.user).values_list('title', flat=True))
        self.assertIn('آپارتمان الف', titles)
        self.assertIn('ویلا ب', titles)
        villa = CRMProperty.objects.get(user=self.user, title='ویلا ب')
        self.assertEqual(villa.sale_price, 900000000)
