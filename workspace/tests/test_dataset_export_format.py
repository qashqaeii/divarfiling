"""خروجی دیتاست — فرمت xlsx واقعی."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from workspace.models import Dataset, Listing

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver'])
@patch('workspace.mixins.has_active_bot_license', return_value=True)
class DatasetExportFormatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ds_exp', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='تست')
        Listing.objects.create(
            dataset=self.dataset,
            token='tok1',
            title='ملک الف',
            data={'extra_col': 'x'},
        )
        Listing.objects.create(
            dataset=self.dataset,
            token='tok2',
            title='ملک ب',
            data={'another': 'y'},
        )

    @patch('workspace.export_security.is_export_authorized', return_value=True)
    def test_xlsx_returns_real_excel_content_type(self, _mock_license, _mock_export):
        self.client.force_login(self.user)
        url = reverse('workspace:dataset_export', kwargs={'dataset_id': self.dataset.pk})
        resp = self.client.get(url, {'format': 'xlsx'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            resp['Content-Type'],
        )
        self.assertTrue(resp.content[:2] == b'PK')

    @patch('workspace.export_security.is_export_authorized', return_value=True)
    def test_invalid_format_redirects(self, _mock_license, _mock_export):
        self.client.force_login(self.user)
        url = reverse('workspace:dataset_export', kwargs={'dataset_id': self.dataset.pk})
        resp = self.client.get(url, {'format': 'doc'}, follow=False)
        self.assertEqual(resp.status_code, 302)
