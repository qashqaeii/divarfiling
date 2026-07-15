"""تست‌های مرکز توسعه محصول."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from licenses.models import License
from product_hub.models import (
    BugReport,
    FeatureFollow,
    FeatureRequest,
    FeatureVote,
    ProductFeature,
    ProductHubNotification,
    ProductRelease,
    ReleaseChange,
)
from product_hub.services import workflow as workflow_svc
from product_hub.services.seed import seed_product_hub
from shop.models import LicensePlan, Order, Product

User = get_user_model()


class ProductHubAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='phuser', password='pass1234', phone='09121111111',
        )
        self.staff = User.objects.create_user(
            username='phstaff', password='pass1234', phone='09122222222',
            is_staff=True,
        )
        self.product = Product.objects.create(
            title='ربات تست', slug='ph-bot', description='t', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='ماهانه', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )
        seed_product_hub()

    def _license(self, user=None):
        user = user or self.user
        order = Order.objects.create(
            user=user, product=self.product, plan=self.plan,
            amount=self.plan.price, status='paid',
        )
        return License.objects.create(
            order=order, plan=self.plan, license_key='PH-TEST-KEY-0001',
            status='active', max_activations=1,
        )

    def test_hub_requires_login(self):
        resp = self.client.get(reverse('workspace:product_hub:hub'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/', resp.url)

    def test_hub_accessible_without_license(self):
        self.client.login(username='phuser', password='pass1234')
        resp = self.client.get(reverse('workspace:product_hub:hub'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مرکز توسعه')

    def test_request_create_blocked_without_license(self):
        self.client.login(username='phuser', password='pass1234')
        resp = self.client.post(reverse('workspace:product_hub:request_create'), {
            'title': 'پیشنهاد تست',
            'category': 'crm',
            'problem': 'مشکل تستی برای پیشنهاد قابلیت',
            'why_important': 'چون مهم است برای کار روزانه',
            'priority': 'medium',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/workspace/upgrade/', resp.url)
        self.assertFalse(FeatureRequest.objects.filter(title='پیشنهاد تست').exists())

    def test_request_create_allowed_with_license(self):
        self._license()
        self.client.login(username='phuser', password='pass1234')
        resp = self.client.post(reverse('workspace:product_hub:request_create'), {
            'title': 'پیشنهاد لایسنس‌دار',
            'category': 'filing',
            'problem': 'نیاز به فیلتر پیشرفته‌تر داریم',
            'why_important': 'صرفه‌جویی زمان مشاوران',
            'priority': 'high',
        })
        self.assertEqual(resp.status_code, 302)
        req = FeatureRequest.objects.get(title='پیشنهاد لایسنس‌دار')
        self.assertEqual(req.user, self.user)
        self.assertEqual(req.votes_count, 1)
        self.assertTrue(FeatureVote.objects.filter(request=req, user=self.user).exists())
        self.assertTrue(FeatureFollow.objects.filter(request=req, user=self.user).exists())

    def test_vote_unique_and_toggle(self):
        self._license()
        req = FeatureRequest.objects.create(
            user=self.user, title='رای تست', category='crm',
            problem='p', why_important='w', priority='low',
        )
        voted, count = workflow_svc.toggle_vote(req, self.user)
        self.assertTrue(voted)
        self.assertEqual(count, 1)
        voted, count = workflow_svc.toggle_vote(req, self.user)
        self.assertFalse(voted)
        self.assertEqual(count, 0)
        self.assertEqual(FeatureVote.objects.filter(request=req).count(), 0)

    def test_manage_requires_staff(self):
        self._license()
        self.client.login(username='phuser', password='pass1234')
        resp = self.client.get(reverse('workspace:product_hub:manage'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/workspace/product/', resp.url)

    def test_staff_can_complete_request_and_notify(self):
        self._license()
        release = ProductRelease.objects.filter(is_published=True).first()
        self.assertIsNotNone(release)
        req = FeatureRequest.objects.create(
            user=self.user, title='ارسال مستقیم فایل', category='crm',
            problem='p', why_important='w', priority='high', status='in_development',
        )
        FeatureFollow.objects.create(request=req, user=self.user)
        req.follows_count = 1
        req.save(update_fields=['follows_count'])

        workflow_svc.change_request_status(
            req,
            to_status='completed',
            actor=self.staff,
            released_in=release,
            release_note='این قابلیت در نسخه جدید اضافه شد.',
        )
        req.refresh_from_db()
        self.assertEqual(req.status, 'completed')
        self.assertTrue(
            ProductHubNotification.objects.filter(
                user=self.user, kind='feature_shipped', feature_request=req,
            ).exists()
        )

    def test_bug_resolve_requires_note(self):
        bug = BugReport.objects.create(
            user=self.user, title='باگ تصویر', description='desc', severity='high',
        )
        with self.assertRaises(workflow_svc.WorkflowError):
            workflow_svc.change_bug_status(
                bug, to_status='resolved', actor=self.staff,
            )
        workflow_svc.change_bug_status(
            bug, to_status='resolved', actor=self.staff,
            resolution_note='در نسخه بعدی اصلاح شد.',
        )
        bug.refresh_from_db()
        self.assertEqual(bug.status, 'resolved')
        self.assertTrue(
            ProductHubNotification.objects.filter(
                user=self.user, kind='bug_resolved',
            ).exists()
        )

    def test_seed_creates_features_and_releases(self):
        self.assertTrue(ProductFeature.objects.filter(is_published=True).exists())
        self.assertTrue(ProductRelease.objects.filter(is_published=True).exists())
        self.assertTrue(ReleaseChange.objects.exists())

    def test_changelog_tab_renders(self):
        self.client.login(username='phuser', password='pass1234')
        resp = self.client.get(reverse('workspace:product_hub:hub') + '?tab=changelog')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'تاریخچه نسخه‌ها')
