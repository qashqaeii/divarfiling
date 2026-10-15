"""خلاصه هوشمند فایل — نمایش برای کاربر بدون لایسنس (سطح رایگان AI)."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from workspace.models import CRMProperty

User = get_user_model()


@override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True)
class CrmPropertyAiSummaryUiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='free_ai_prop', password='x', phone='09128887766',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان تست',
            deal_mode='فروش',
            city='تهران',
        )
        self.url = reverse('workspace:crm_property_detail', kwargs={'property_id': self.prop.pk})

    @patch('workspace.services.access.has_active_bot_license', return_value=False)
    def test_summary_card_visible_without_license(self, _lic):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'خلاصه هوشمند فایل')
        self.assertContains(resp, 'ws-ai-card--listing')
