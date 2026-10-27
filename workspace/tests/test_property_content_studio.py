"""تست‌های استودیوی هوشمند ملک."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMProperty, CRMPropertyContentStudioDraft, WorkspaceSettings
from workspace.services.property_content_studio.adapter import build_studio_property_payload
from workspace.services.property_content_studio.draft import save_draft
from workspace.services.property_content_studio.fingerprint import property_content_fingerprint
from workspace.services.property_content_studio.quality import build_quality_report

User = get_user_model()


class PropertyContentStudioAdapterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='advisor1', password='x', phone='09120000001')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ۶۵ متری',
            property_type='آپارتمان',
            deal_mode='فروش',
            area=65,
            rooms='۱',
            neighborhood='سعادت‌آباد',
            city='تهران',
            sale_price=20_000_000_000,
            has_elevator=True,
            has_storage=True,
            has_parking=False,
            images=['/media/test/a.jpg'],
        )

    def test_does_not_claim_parking_when_absent(self):
        payload = build_studio_property_payload(self.prop)
        self.assertFalse(payload['has_parking'])
        amenities = payload['amenities']
        self.assertIn('آسانسور', amenities)
        self.assertIn('انباری', amenities)
        self.assertNotIn('پارکینگ', amenities)

    def test_fingerprint_changes_when_price_changes(self):
        fp1 = property_content_fingerprint(self.prop)
        self.prop.sale_price = 21_000_000_000
        self.prop.save()
        fp2 = property_content_fingerprint(self.prop)
        self.assertNotEqual(fp1, fp2)


class PropertyContentStudioAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='advisor2', password='x', phone='09120000002')
        self.other = User.objects.create_user(username='other', password='x', phone='09120000003')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک تست',
            property_type='آپارتمان',
            sale_price=1_000_000_000,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_session_requires_auth(self):
        anon = Client()
        url = reverse('workspace:crm_property_content_studio_session', args=[self.prop.pk])
        res = anon.get(url)
        self.assertEqual(res.status_code, 302)

    def test_session_ok_for_owner(self):
        url = reverse('workspace:crm_property_content_studio_session', args=[self.prop.pk])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['property']['id'], self.prop.pk)

    def test_session_404_for_other_user(self):
        self.client.force_login(self.other)
        url = reverse('workspace:crm_property_content_studio_session', args=[self.prop.pk])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_draft_roundtrip(self):
        url = reverse('workspace:crm_property_content_studio_draft', args=[self.prop.pk])
        payload = {'active_tab': 'divar', 'format': 'post', 'ai': {'divar': {'body': 'متن'}}}
        res = self.client.put(
            url,
            data=json.dumps({'draft': payload}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        draft = CRMPropertyContentStudioDraft.objects.get(property=self.prop, user=self.user)
        self.assertEqual(draft.payload.get('format'), 'post')

    def test_brand_defaults_saved(self):
        url = reverse('workspace:crm_property_content_studio_brand', args=[self.prop.pk])
        res = self.client.put(
            url,
            data=json.dumps({'brand_name': 'آژانس تست', 'colors': {'primary': '#112233'}}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        ws = WorkspaceSettings.objects.get(user=self.user)
        self.assertEqual(ws.content_studio_defaults.get('brand_name'), 'آژانس تست')


class PropertyContentStudioQualityTests(TestCase):
    def test_quality_warns_short_notes(self):
        user = User.objects.create_user(username='q', password='x', phone='09120000004')
        prop = CRMProperty.objects.create(user=user, title='x', notes='کوتاه')
        report = build_quality_report(prop, user)
        labels = [i['label'] for i in report['items']]
        self.assertTrue(any('توضیحات' in l for l in labels))
