"""تست‌های Hardening داشبورد TV آژانس."""
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from workspace.models import (
    CRMAgencyAnnouncement,
    CRMAgencyMember,
    CRMAgencyTeamGoal,
    CRMDeal,
    Customer,
)
from workspace.services.crm_agency import create_agency
from workspace.services.crm_agency_announcements import create_announcement
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_agency_tv import (
    TV_ROLE_ADVISOR,
    TV_ROLE_MANAGER,
    TV_ROLE_SECRETARY,
    get_tv_cache_key,
    get_tv_dashboard_payload,
    invalidate_tv_cache,
    scan_payload_for_pii,
)

User = get_user_model()

PII_SAMPLES = (
    '09120000000',
    'مشتری محرمانه',
    'معامله تست',
    'آدرس دقیق',
)


class CRMAgencyTVHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username='owner_tv2', password='pass12345')
        self.manager = User.objects.create_user(username='mgr_tv2', phone='09126666666', password='pass12345')
        self.secretary = User.objects.create_user(username='sec_tv2', phone='09127777777', password='pass12345')
        self.advisor = User.objects.create_user(username='advisor_tv2', phone='09128888888', password='pass12345')
        self.agency = create_agency(self.owner, 'آژانس TV Hardening')
        CRMAgencyMember.objects.create(agency=self.agency, user=self.manager, role='manager')
        CRMAgencyMember.objects.create(agency=self.agency, user=self.secretary, role='secretary')
        CRMAgencyMember.objects.create(agency=self.agency, user=self.advisor, role='advisor')

        self.other_owner = User.objects.create_user(username='other_owner', phone='09129999999', password='pass12345')
        self.other_agency = create_agency(self.other_owner, 'آژانس دیگر')

    def _assert_no_pii(self, payload):
        raw = json.dumps(payload, ensure_ascii=False)
        for sample in PII_SAMPLES:
            self.assertNotIn(sample, raw)
        self.assertEqual(scan_payload_for_pii(payload), [])

    def test_active_member_can_access_page_and_api(self):
        for user in (self.owner, self.manager, self.secretary, self.advisor):
            client = Client()
            client.force_login(user)
            page = client.get(reverse('workspace:crm_team_tv'))
            self.assertEqual(page.status_code, 200, msg=user.username)
            api = client.get(reverse('workspace:api_crm_team_tv'))
            self.assertEqual(api.status_code, 200, msg=user.username)
            self.assertTrue(api.json()['ok'])

    def test_outsider_denied(self):
        outsider = User.objects.create_user(username='outsider_tv2', phone='09121112222', password='pass12345')
        client = Client()
        client.force_login(outsider)
        self.assertEqual(client.get(reverse('workspace:crm_team_tv')).status_code, 302)
        self.assertEqual(client.get(reverse('workspace:api_crm_team_tv')).status_code, 404)

    def test_cross_agency_isolation(self):
        client = Client()
        client.force_login(self.other_owner)
        data = client.get(reverse('workspace:api_crm_team_tv')).json()
        self.assertEqual(data['agency']['name'], 'آژانس دیگر')
        self.assertNotEqual(data['agency']['name'], 'آژانس TV Hardening')

    def test_role_payload_manager_includes_commission(self):
        payload = get_tv_dashboard_payload(self.owner, use_cache=False)
        self.assertEqual(payload['role'], TV_ROLE_MANAGER)
        self.assertIn('commission_month', payload['kpis'])
        self.assertIn('chart', payload)
        self.assertIn('activity', payload)
        self.assertIn('schedule', payload)

    def test_chart_doughnut_status_distribution(self):
        Customer.objects.create(
            agency=self.agency, user=self.owner, name='A', phone='09121111111', status='جدید',
        )
        Customer.objects.create(
            agency=self.agency, user=self.owner, name='B', phone='09122222222', status='در حال پیگیری',
        )
        payload = get_tv_dashboard_payload(self.owner, use_cache=False)
        chart = payload['chart']
        self.assertIn('doughnut', chart)
        self.assertIn('series', chart)
        donut = chart['doughnut']
        self.assertEqual(donut['center_value'], 2)
        labels = {s['label'] for s in donut['slices']}
        self.assertIn('جدید', labels)
        self.assertIn('در حال پیگیری', labels)
        self.assertEqual(sum(s['pct'] for s in donut['slices'] if s['value']), 100)
        self.assertEqual(len(chart['series']), 4)
        self.assertIn('share_pct', chart['series'][0])

    def test_role_payload_secretary_no_commission(self):
        payload = get_tv_dashboard_payload(self.secretary, use_cache=False)
        self.assertEqual(payload['role'], TV_ROLE_SECRETARY)
        self.assertNotIn('commission_month', payload['kpis'])
        self.assertIn('schedule', payload)

    def test_role_payload_advisor_reduced(self):
        payload = get_tv_dashboard_payload(self.advisor, use_cache=False)
        self.assertEqual(payload['role'], TV_ROLE_ADVISOR)
        self.assertNotIn('commission_month', payload['kpis'])
        self.assertNotIn('schedule', payload['allowed_widgets'])
        self.assertIn('leaderboard', payload)

    def test_pii_sanitization(self):
        customer = Customer.objects.create(
            agency=self.agency,
            user=self.owner,
            name='مشتری محرمانه',
            phone='09120000000',
            source='دیوار',
            notes='آدرس دقیق',
        )
        CRMDeal.objects.create(
            agency=self.agency,
            user=self.owner,
            customer=customer,
            title='معامله تست',
            stage='مذاکره',
        )
        payload = get_tv_dashboard_payload(self.owner, use_cache=False)
        self._assert_no_pii(payload)
        self.assertNotIn('09128888888', json.dumps(payload, ensure_ascii=False))
        for deal in payload.get('recent_deals', {}).get('active', []):
            self.assertIn('summary', deal)
            self.assertNotIn('title', deal)
            self.assertNotIn('معامله تست', deal.get('summary', ''))

    def test_forbidden_keys_not_in_payload(self):
        payload = get_tv_dashboard_payload(self.owner, use_cache=False)
        self.assertEqual(scan_payload_for_pii(payload), [])

    def test_expired_announcement_excluded(self):
        create_announcement(
            self.owner,
            title='منقضی',
            body='متن',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        create_announcement(self.owner, title='فعال', body='متن')
        payload = get_tv_dashboard_payload(self.advisor, use_cache=False)
        titles = [a['title'] for a in payload['announcements']]
        self.assertIn('فعال', titles)
        self.assertNotIn('منقضی', titles)

    def test_empty_state_payload(self):
        payload = get_tv_dashboard_payload(self.advisor, use_cache=False)
        self.assertTrue(payload['ok'])
        self.assertIsInstance(payload['leaderboard'], list)
        self.assertIsInstance(payload['goals'], list)
        self.assertIsInstance(payload['announcements'], list)

    def test_cache_isolation_by_role(self):
        get_tv_dashboard_payload(self.owner, use_cache=True)
        get_tv_dashboard_payload(self.advisor, use_cache=True)
        self.assertNotEqual(
            get_tv_cache_key(self.agency.pk, TV_ROLE_MANAGER),
            get_tv_cache_key(self.agency.pk, TV_ROLE_ADVISOR),
        )
        cached_mgr = cache.get(get_tv_cache_key(self.agency.pk, TV_ROLE_MANAGER))
        cached_adv = cache.get(get_tv_cache_key(self.agency.pk, TV_ROLE_ADVISOR))
        self.assertIsNotNone(cached_mgr)
        self.assertIsNotNone(cached_adv)
        self.assertNotEqual(cached_mgr['role'], cached_adv['role'])

    def test_cache_hit_updates_clock_only(self):
        first = get_tv_dashboard_payload(self.owner, use_cache=False)
        cache.set(get_tv_cache_key(self.agency.pk, TV_ROLE_MANAGER), first, 60)
        second = get_tv_dashboard_payload(self.owner, use_cache=True)
        self.assertEqual(second['payload_version'], first['payload_version'])
        self.assertNotEqual(second['generated_at'], first['generated_at'])

    def test_invalidate_tv_cache(self):
        get_tv_dashboard_payload(self.owner, use_cache=True)
        self.assertIsNotNone(cache.get(get_tv_cache_key(self.agency.pk, TV_ROLE_MANAGER)))
        invalidate_tv_cache(self.agency.pk)
        self.assertIsNone(cache.get(get_tv_cache_key(self.agency.pk, TV_ROLE_MANAGER)))

    @override_settings(USE_TZ=True, TIME_ZONE='Asia/Tehran')
    def test_timezone_in_generated_at(self):
        payload = get_tv_dashboard_payload(self.owner, use_cache=False)
        self.assertIn('+', payload['generated_at'])

    def test_feature_flag_disabled(self):
        with mock.patch('workspace.crm_views.is_agency_feature_enabled', return_value=False):
            with mock.patch('workspace.team_api_views.is_agency_feature_enabled', return_value=False):
                client = Client()
                client.force_login(self.owner)
                self.assertEqual(client.get(reverse('workspace:crm_team_tv')).status_code, 302)
                self.assertEqual(client.get(reverse('workspace:api_crm_team_tv')).status_code, 403)

    def test_query_count_bounded(self):
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            get_tv_dashboard_payload(self.owner, use_cache=False)
        small_team_queries = len(ctx)
        self.assertLessEqual(small_team_queries, 110, msg=f'{small_team_queries} queries for small team')

        for i in range(3):
            CRMAgencyMember.objects.create(
                agency=self.agency,
                user=User.objects.create_user(
                    username=f'adv_q_{i}',
                    phone=f'0913000000{i}',
                    password='pass12345',
                ),
                role='advisor',
            )
        with CaptureQueriesContext(connection) as ctx_large:
            get_tv_dashboard_payload(self.owner, use_cache=False)
        large_team_queries = len(ctx_large)
        self.assertLessEqual(large_team_queries, 150, msg=f'{large_team_queries} queries for larger team')
        self.assertGreater(large_team_queries, small_team_queries)

    def test_template_uses_json_script(self):
        client = Client()
        client.force_login(self.owner)
        resp = client.get(reverse('workspace:crm_team_tv'))
        self.assertContains(resp, 'tv-cmd')
        self.assertContains(resp, 'crm-tv-body')
        self.assertContains(resp, 'id="crm-tv-initial"')
        self.assertContains(resp, '"ok": true', html=False)

    def test_team_goals_advisor_team_only(self):
        member = CRMAgencyMember.objects.get(user=self.advisor)
        CRMAgencyTeamGoal.objects.create(
            agency=self.agency,
            member=member,
            metric='calls',
            target_value=10,
            period_start=timezone.now().date(),
            period_end=timezone.now().date() + timedelta(days=30),
        )
        CRMAgencyTeamGoal.objects.create(
            agency=self.agency,
            member=None,
            metric='visits',
            target_value=20,
            period_start=timezone.now().date(),
            period_end=timezone.now().date() + timedelta(days=30),
        )
        payload = get_tv_dashboard_payload(self.advisor, use_cache=False)
        self.assertEqual(len(payload['goals']), 1)
        self.assertIn('هدف', payload['goals'][0]['title'])

    def test_agency_logo_in_payload_when_set(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from workspace.models import WorkspaceSettings

        ws, _ = WorkspaceSettings.objects.get_or_create(user=self.owner)
        ws.agency_logo = SimpleUploadedFile('logo.png', b'\x89PNG', content_type='image/png')
        ws.save()
        payload = get_tv_dashboard_payload(self.owner, use_cache=False)
        self.assertTrue(payload['agency']['logo_url'])

    def test_agency_logo_null_when_not_set(self):
        payload = get_tv_dashboard_payload(self.owner, use_cache=False)
        self.assertIsNone(payload['agency']['logo_url'])

    def test_feature_flag_enabled_by_default(self):
        self.assertTrue(is_agency_feature_enabled('tv_mode', self.agency))
