"""تست API خلاصه فایل شخصی."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from workspace.models import CRMProperty, Dataset, Listing


@override_settings(AI_ENABLED=True)
class PropertySummaryViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='propsum', password='pass', phone='09125556666',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ویلا ۲۰۰ متری',
            deal_mode='فروش',
            city='تهران',
            area=200,
            sale_price=20_000_000_000,
        )
        self.url = reverse(
            'workspace:ai_workspace:property_summary',
            kwargs={'property_id': self.prop.id},
        )

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_requires_post(self, _license):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_not_found_for_other_user(self, _license):
        other = get_user_model().objects.create_user(
            username='other', password='pass', phone='09127778888',
        )
        self.client.force_login(other)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 404)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_uses_listing_path_when_source_still_in_filing(self, _license):
        dataset = Dataset.objects.create(
            user=self.user,
            name='فایل تست',
            original_filename='t.xlsx',
            file_format='xlsx',
            city='تهران',
            transaction_type='sale',
        )
        listing = Listing.objects.create(
            dataset=dataset,
            token='tok-personal',
            title='ویلا ۲۰۰ متری',
            city='تهران',
            area=200,
            price=20_000_000_000,
        )
        self.prop.token = listing.token
        self.prop.save(update_fields=['token'])

        self.client.force_login(self.user)
        with patch('ai_workspace.services.property_summary.generate_summary') as mocked:
            from ai_workspace.services.gateway import GatewayResult

            mocked.return_value = GatewayResult(
                feature='listing_summary',
                provider='test',
                model='test',
                text='{}',
                data={'summary': 'ok', 'highlights': [], 'negotiation_tip': ''},
                is_fallback=True,
                from_cache=False,
                latency_ms=1,
                input_tokens=0,
                output_tokens=0,
                status='ok',
            )
            resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        mocked.assert_called_once()
        args = mocked.call_args[0]
        self.assertEqual(args[1], dataset)
        self.assertEqual(args[2].pk, listing.pk)
