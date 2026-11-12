"""Premium V2 / 02C — user table filters, error states and table actions."""
from pathlib import Path
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_users_management import list_users_management
from licenses.models import ClientAppEvent, License, LicenseActivation
from mobile_api.models import MobileDevice
from shop.models import DownloadLog, LicensePlan, Order, OrderRenewalItem, Product
from workspace.models import Customer, Dataset

User = get_user_model()


class UserTableFilterContractTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='phase02c_admin', phone='09129995111', password='pass',
            is_staff=True, is_superuser=True,
        )
        self.active = User.objects.create_user(
            username='phase02c_user_active', phone='09129995112', password='pass',
        )
        self.idle = User.objects.create_user(
            username='phase02c_user_idle', phone='09129995113', password='pass',
        )
        self.product = Product.objects.create(
            title='Phase 02C Product', slug='phase-02c-product', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='Monthly', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )
        self.order = Order.objects.create(
            user=self.active, product=self.product, plan=self.plan,
            amount=Decimal('100000'), status='paid', paid_at=timezone.now(),
        )
        DownloadLog.objects.create(user=self.active, order=self.order)
        MobileDevice.objects.create(user=self.active, device_id='phase02c-android')
        self.license = License.objects.create(
            order=self.order, plan=self.plan, status='active',
            license_key='PHASE02C-LICENSE-A',
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.activation = LicenseActivation.objects.create(
            license=self.license, hardware_fingerprint='phase02c-win',
            is_active=True,
        )
        ClientAppEvent.objects.create(
            license=self.license, user=self.active,
            activation=self.activation, hardware_fingerprint='phase02c-win',
            event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
        )
        Dataset.objects.create(
            user=self.active, name='Dataset A',
            original_filename='a.csv', file_format='csv',
        )
        Customer.objects.create(user=self.active, name='Customer A')

    def ids(self, **filters):
        payload = list_users_management(
            q='phase02c_user_', page_size=25, filters=filters,
        )
        self.assertTrue(payload['ok'])
        return {row['id'] for row in payload['results']}

    def test_ui_license_yes_no_and_legacy_values(self):
        self.assertEqual(self.ids(license='yes'), {self.active.pk})
        self.assertEqual(self.ids(license='no'), {self.idle.pk})
        self.assertEqual(self.ids(license='active'), {self.active.pk})
        self.assertEqual(self.ids(license='none'), {self.idle.pk})

    def test_windows_criteria_are_distinct_and_keep_legacy_boolean(self):
        for value in ('downloaded', 'activated', 'launched', '1', 'yes'):
            with self.subTest(filter=value):
                self.assertEqual(self.ids(windows=value), {self.active.pk})
        self.assertEqual(self.ids(windows='0'), {self.idle.pk})

    def test_android_paid_datasets_crm_ui_filters_actually_filter(self):
        for name in ('android', 'paid', 'datasets', 'crm'):
            with self.subTest(name=name):
                self.assertEqual(self.ids(**{name: 'yes'}), {self.active.pk})
                self.assertEqual(self.ids(**{name: 'no'}), {self.idle.pk})
                self.assertEqual(self.ids(**{name: '1'}), {self.active.pk})
                self.assertEqual(self.ids(**{name: '0'}), {self.idle.pk})

    def test_api_composes_multiple_ui_filters(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin_panel_users_json'), {
            'q': 'phase02c_user_', 'windows': 'launched',
            'android': 'yes', 'paid': 'yes',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['results'][0]['id'], self.active.pk)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_no_results_is_empty_not_unfiltered(self):
        self.assertEqual(self.ids(android='yes', paid='no'), set())

    def test_table_controls_and_accessible_dialog_are_rendered(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin_panel_users'))
        self.assertEqual(response.status_code, 200)
        for token in (
            'id="eccUsersMgmtReset"',
            'id="eccUsersMgmtStatus"',
            'aria-live="polite"',
            'aria-modal="true"',
            'mizkar-admin-users-mgmt.js',
        ):
            self.assertContains(response, token)

    def test_license_and_sales_links_respect_django_permissions(self):
        staff = User.objects.create_user(
            username='phase02c_staff', phone='09129995114',
            password='pass', is_staff=True,
        )
        self.client.force_login(staff)
        licenses = self.client.get(reverse('admin_panel_licenses'))
        self.assertEqual(licenses.status_code, 200)
        self.assertNotContains(
            licenses,
            reverse('admin_panel_export', args=['expiring_licenses']) + '?format=xlsx',
        )
        self.assertNotContains(
            licenses,
            reverse('admin_panel_export', args=['expired_licenses']) + '?format=xlsx',
        )
        sales = self.client.get(reverse('admin_panel_sales'))
        self.assertEqual(sales.status_code, 200)
        self.assertNotContains(sales, 'مشاهده سفارش‌ها')

    def test_multi_license_renewal_is_not_labeled_new_key(self):
        renewal = Order.objects.create(
            user=self.active, product=self.product, plan=self.plan,
            amount=Decimal('100000'), status='paid', paid_at=timezone.now(),
        )
        OrderRenewalItem.objects.create(
            order=renewal, license=self.license,
            unit_original_price=Decimal('100000'),
            unit_final_price=Decimal('100000'),
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin_panel_licenses'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'تمدید رسمی')


class UserTableInteractionSourceTests(SimpleTestCase):
    def test_js_has_retry_reset_race_guards_and_focus_restoration(self):
        root = Path(__file__).resolve().parents[2]
        js = (root / 'static/js/mizkar-admin-users-mgmt.js').read_text(
            encoding='utf-8',
        )
        for token in (
            'listRequestId',
            'detailRequestId',
            'data-retry-users-list',
            'data-reset-users-filter',
            'pagerEl.hidden = totalPages <= 1',
            'drawerReturnFocus.focus()',
            "event.key !== 'Tab'",
        ):
            with self.subTest(token=token):
                self.assertIn(token, js)
