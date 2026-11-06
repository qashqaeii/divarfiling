"""تست KPI پریمیوم مرکز توسعه."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from product_hub.models import BugReport, FeatureRequest, ProductFeature
from product_hub.services.stats import build_hub_kpi_stats, get_hub_stats

User = get_user_model()


class HubKpiStatsTests(TestCase):
    def test_empty_enrichment_keys(self):
        kpi = build_hub_kpi_stats()
        base = get_hub_stats()
        for key in (
            'features_total', 'features_active', 'features_in_progress',
            'requests_open', 'bugs_open', 'bugs_resolved', 'latest_version',
        ):
            self.assertEqual(kpi[key], base[key])
        self.assertIn('hero_meta', kpi)
        self.assertIn('mix_segments', kpi)
        self.assertIn('progress_meta', kpi)
        self.assertIn('requests_meta', kpi)
        self.assertIn('bugs_meta', kpi)

    def test_mix_and_metas(self):
        ProductFeature.objects.create(
            title='فعال', slug='kpi-active', summary='s', category='crm',
            status='active', is_published=True,
        )
        ProductFeature.objects.create(
            title='ساخت', slug='kpi-build', summary='s', category='crm',
            status='in_progress', is_published=True,
        )
        ProductFeature.objects.create(
            title='برنامه', slug='kpi-plan', summary='s', category='tools',
            status='planned', is_published=True,
        )
        user = User.objects.create_user(
            username='phkpi', password='pass1234', phone='09123334455',
        )
        FeatureRequest.objects.create(
            user=user, title='پیشنهاد باز', category='crm',
            problem='p', why_important='w', priority='medium',
            status='submitted', is_public=True,
        )
        BugReport.objects.create(
            user=user, title='باگ باز', description='d',
            severity='medium', status='reported',
        )
        BugReport.objects.create(
            user=user, title='باگ رفع', description='d',
            severity='low', status='resolved',
        )

        kpi = build_hub_kpi_stats()
        self.assertEqual(kpi['features_total'], 3)
        self.assertEqual(kpi['features_active'], 1)
        self.assertEqual(kpi['features_in_progress'], 1)
        self.assertEqual(kpi['features_planned'], 1)
        self.assertEqual(kpi['requests_open'], 1)
        self.assertEqual(kpi['bugs_open'], 1)
        self.assertEqual(kpi['bugs_resolved'], 1)
        self.assertTrue(kpi['mix_segments'])
        self.assertIn('فعال', kpi['hero_meta'])
        self.assertIn('در صف', kpi['requests_meta'])
        self.assertIn('مشکل باز', kpi['bugs_meta'])


class HubPageKpiRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='phkpipage', password='pass1234', phone='09123334466',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_hub_renders_premium_kpi(self):
        resp = self.client.get(reverse('workspace:product_hub:hub'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'fl-kpi-pro--product')
        self.assertContains(resp, 'قابلیت‌ها')
        self.assertContains(resp, 'پیشنهاد باز')
        self.assertContains(resp, 'باگ باز')
        self.assertIn('hero_meta', resp.context['hub_stats'])
        self.assertNotContains(resp, 'ph-metrics')
