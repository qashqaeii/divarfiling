"""تست‌های API موبایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from workspace.models import Customer

User = get_user_model()


class MobileAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121111111',
            phone='09121111111',
            password='testpass123',
        )
        product = Product.objects.create(title='ربات', slug='bot', description='تست', is_active=True)
        plan = LicensePlan.objects.create(
            product=product,
            name='Pro',
            plan_type='yearly',
            price=1000000,
            duration_days=365,
            max_activations=2,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=1000000,
            status='paid',
        )
        self.license = License.objects.create(
            order=order,
            license_key='TEST-KEY-1234',
            plan=plan,
            status='active',
            max_activations=2,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        self.client = APIClient()

    def _login(self):
        resp = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09121111111',
            'password': 'testpass123',
        }, format='json')
        self.assertTrue(resp.data.get('ok'), resp.data)
        token = resp.data['data']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return resp.data['data']

    def test_login_and_license(self):
        data = self._login()
        self.assertIn('access', data)
        resp = self.client.get('/api/mobile/v1/license/status')
        self.assertTrue(resp.data['ok'])
        self.assertTrue(resp.data['data']['valid'])

    def test_quick_lead(self):
        self._login()
        resp = self.client.post('/api/mobile/v1/crm/contacts/quick-lead', {
            'full_name': 'علی تست',
            'phone': '09123334444',
        }, format='json')
        self.assertTrue(resp.data['ok'], resp.data)
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)

    def test_extraction_requires_items(self):
        self._login()
        resp = self.client.post('/api/mobile/v1/extractions/upload', {
            'filters': {'category': 'apartment-rent', 'max_items': 1, 'city_id': '1'},
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [],
        }, format='json')
        self.assertFalse(resp.data['ok'])

    def test_extraction_denied_without_license(self):
        user2 = User.objects.create_user(username='0922', phone='09222222222', password='x')
        client = APIClient()
        resp = client.post('/api/mobile/v1/auth/login', {
            'username': '09222222222',
            'password': 'x',
        }, format='json')
        token = resp.data['data']['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = client.get('/api/mobile/v1/license/status')
        self.assertFalse(resp.data['data']['valid'])

    def test_dashboard(self):
        self._login()
        Customer.objects.create(
            user=self.user, name='تست', phone='09120000000',
            customer_type='خریدار', status='جدید',
        )
        resp = self.client.get('/api/mobile/v1/dashboard')
        self.assertTrue(resp.data['ok'], resp.data)
        data = resp.data['data']
        self.assertIn('stats', data)
        self.assertIn('license', data)
        self.assertGreaterEqual(data['stats']['contacts'], 1)

    def test_contact_detail(self):
        self._login()
        c = Customer.objects.create(
            user=self.user, name='علی', phone='09123334444',
            customer_type='خریدار', status='جدید',
        )
        resp = self.client.get(f'/api/mobile/v1/crm/contacts/{c.pk}')
        self.assertTrue(resp.data['ok'], resp.data)
        self.assertIn('contact', resp.data['data'])
        self.assertIn('activities', resp.data['data'])

    def test_create_activity(self):
        self._login()
        c = Customer.objects.create(
            user=self.user, name='علی', phone='09123334444',
            customer_type='خریدار', status='جدید',
        )
        resp = self.client.post(
            f'/api/mobile/v1/crm/contacts/{c.pk}/activities',
            {'activity_type': 'call', 'content': 'تماس گرفته شد'},
            format='json',
        )
        self.assertTrue(resp.data['ok'], resp.data)
        self.assertEqual(resp.data['data']['activity_type'], 'call')
