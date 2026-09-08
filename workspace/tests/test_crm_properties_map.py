"""تست نقشه فایل‌های شخصی — reuse Map Pro فایلینگ."""
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from workspace.models import CRMProperty

User = get_user_model()


class CRMPropertyMapViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='crmmap', password='test', phone='09121110901',
        )
        self.other = User.objects.create_user(
            username='crmmapother', password='test', phone='09121110902',
        )
        self.client.force_login(self.user)
        self.sale = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان فروش با مختصات',
            deal_mode='فروش',
            city='تهران',
            neighborhood='ونک',
            latitude=35.757,
            longitude=51.410,
            sale_price=12_000_000_000,
            area=120,
            rooms='2',
            has_elevator=True,
            has_parking=True,
            business_type='مالک',
            images=['https://example.com/p.jpg'],
        )
        self.rent = CRMProperty.objects.create(
            user=self.user,
            title='رهن و اجاره با مختصات',
            deal_mode='رهن و اجاره',
            city='تهران',
            neighborhood='سعادت‌آباد',
            latitude=35.780,
            longitude=51.370,
            deposit=800_000_000,
            monthly_rent=25_000_000,
            area=90,
            business_type='مشاور',
        )
        self.no_geo = CRMProperty.objects.create(
            user=self.user,
            title='بدون مختصات',
            deal_mode='فروش',
            city='تهران',
            sale_price=5_000_000_000,
        )
        CRMProperty.objects.create(
            user=self.other,
            title='ملک کاربر دیگر',
            deal_mode='فروش',
            latitude=35.7,
            longitude=51.4,
            sale_price=1_000_000_000,
        )
        self.url = reverse('workspace:crm_properties_map')

    def test_reuses_filing_map_pro_template_and_init(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'workspace/map/index.html')
        self.assertContains(res, 'map-pro.css')
        self.assertContains(res, 'id="wsMap"')
        self.assertContains(res, 'id="mkMapMarkers"')
        self.assertContains(res, 'id="mkMapConfig"')
        self.assertContains(res, 'initMap(')
        self.assertContains(res, 'mk-map-pro')
        self.assertTrue(res.context['is_crm_map'])

    def test_markers_come_from_personal_properties_only(self):
        res = self.client.get(self.url)
        marker_ids = {m['id'] for m in res.context['markers']}
        self.assertIn(self.sale.pk, marker_ids)
        self.assertIn(self.rent.pk, marker_ids)
        self.assertNotIn(self.no_geo.pk, marker_ids)
        other_ids = set(
            CRMProperty.objects.filter(user=self.other).values_list('pk', flat=True),
        )
        self.assertFalse(marker_ids & other_ids)

    def test_popup_link_goes_to_crm_property_detail(self):
        res = self.client.get(self.url)
        by_id = {m['id']: m for m in res.context['markers']}
        sale_marker = by_id[self.sale.pk]
        detail_url = reverse(
            'workspace:crm_property_detail',
            kwargs={'property_id': self.sale.pk},
        )
        self.assertEqual(sale_marker['platform_url'], detail_url)
        self.assertEqual(sale_marker['lat'], self.sale.latitude)
        self.assertEqual(sale_marker['lng'], self.sale.longitude)
        self.assertEqual(sale_marker['title'], self.sale.title)
        self.assertTrue(sale_marker['thumb'])

    def test_list_filters_apply_to_markers(self):
        res = self.client.get(self.url, {'deal_mode': 'فروش'})
        self.assertEqual(res.status_code, 200)
        marker_ids = {m['id'] for m in res.context['markers']}
        self.assertIn(self.sale.pk, marker_ids)
        self.assertNotIn(self.rent.pk, marker_ids)
        self.assertTrue(res.context['is_map_filtered'])

    def test_back_url_preserves_crm_filters(self):
        res = self.client.get(self.url, {'deal_mode': 'فروش', 'q': 'ونک'})
        back = res.context['map_back_url']
        self.assertIn(reverse('workspace:crm_properties'), back)
        self.assertIn('deal_mode', back)
        self.assertIn('q=', back)

    def test_empty_state_when_no_coordinates(self):
        CRMProperty.objects.filter(user=self.user).update(latitude=None, longitude=None)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['geo_count'], 0)
        self.assertContains(res, 'مختصات جغرافیایی یافت نشد')
        self.assertContains(res, reverse('workspace:crm_properties'))


class CRMPropertyListMapEntryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='crmmaplist', password='test', phone='09121110903',
        )
        self.client.force_login(self.user)
        CRMProperty.objects.create(user=self.user, title='ملک لیست', deal_mode='فروش')

    def test_list_links_to_same_map_pro_route_with_filters(self):
        list_url = reverse('workspace:crm_properties')
        map_url = reverse('workspace:crm_properties_map')
        res = self.client.get(list_url, {'deal_mode': 'فروش', 'folder_id': '3'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, map_url)
        qs = parse_qs(res.context['map_filter_qs'])
        self.assertEqual(qs.get('deal_mode'), ['فروش'])
        self.assertEqual(qs.get('folder_id'), ['3'])
        self.assertNotIn('view', qs)
