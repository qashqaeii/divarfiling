"""تست‌های استودیوی هوشمند ملک."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import (
    CRMProperty,
    CRMPropertyContentStudioDraft,
    CRMPropertyPublicShare,
    CRMResourceShare,
    WorkspaceSettings,
)
from workspace.services.property_content_studio.adapter import build_studio_property_payload
from workspace.services.property_content_studio.adapter import build_studio_property_payload
from workspace.services.property_content_studio.draft import save_draft, sync_draft_with_property
from workspace.services.property_content_studio.draft_validate import DraftValidationError, validate_and_merge_draft
from workspace.services.property_content_studio.fingerprint import property_content_fingerprint
from workspace.services.property_content_studio.quality import build_quality_report
from workspace.services.property_public_share import existing_property_share_for_user
from ai_workspace.services.property_content_studio_payload import enforce_property_facts

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
            notes='یادداشت محرمانه CRM — نباید در استودیو باشد',
        )

    def test_does_not_claim_parking_when_absent(self):
        payload = build_studio_property_payload(self.prop)
        self.assertFalse(payload['has_parking'])
        amenities = payload['amenities']
        self.assertIn('آسانسور', amenities)
        self.assertIn('انباری', amenities)
        self.assertNotIn('پارکینگ', amenities)

    def test_notes_not_in_public_description(self):
        payload = build_studio_property_payload(self.prop)
        self.assertEqual(payload['description_excerpt'], '')

    def test_fingerprint_changes_when_price_changes(self):
        fp1 = property_content_fingerprint(self.prop)
        self.prop.sale_price = 21_000_000_000
        self.prop.save()
        fp2 = property_content_fingerprint(self.prop)
        self.assertNotEqual(fp1, fp2)

    def test_payload_includes_extended_poster_details(self):
        self.prop.floor = 3
        self.prop.total_floors = 8
        self.prop.build_year = 1400
        self.prop.feature_data = {'جنس کف': 'سرامیک'}
        self.prop.save()
        payload = build_studio_property_payload(self.prop)
        self.assertEqual(payload['floor_label'], 'طبقه 3 از 8')
        self.assertEqual(payload['build_year_label'], 'ساخت 1400')
        joined = ' '.join(payload['detail_chips'])
        self.assertIn('سرامیک', joined)

    def test_detail_chips_exclude_internal_location_metadata(self):
        self.prop.feature_data = {
            'جنس کف': 'سرامیک',
            '_location_precision': 'approximate',
            '_location_source': 'listing_coordinates',
        }
        self.prop.save()
        payload = build_studio_property_payload(self.prop)
        joined = ' '.join(payload['detail_chips'])
        self.assertIn('سرامیک', joined)
        self.assertNotIn('location_precision', joined)
        self.assertNotIn('location_source', joined)
        self.assertNotIn('approximate', joined.lower())


class PropertyContentStudioAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='advisor2', password='x', phone='09120000002')
        self.other = User.objects.create_user(username='other', password='x', phone='09120000003')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک تست',
            property_type='آپارتمان',
            sale_price=1_000_000_000,
            neighborhood='ونک',
            notes='محرمانه',
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

    def test_session_does_not_auto_create_public_share(self):
        before = CRMPropertyPublicShare.objects.filter(property=self.prop).count()
        url = reverse('workspace:crm_property_content_studio_session', args=[self.prop.pk])
        self.client.get(url)
        after = CRMPropertyPublicShare.objects.filter(property=self.prop).count()
        self.assertEqual(before, after)
        self.assertEqual(existing_property_share_for_user(self.user, self.prop), None)

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

    def test_draft_rejects_invalid_payload(self):
        url = reverse('workspace:crm_property_content_studio_draft', args=[self.prop.pk])
        res = self.client.put(
            url,
            data=json.dumps({'draft': {'format': 'invalid-format-name'}}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_save_keeps_stale_until_sync(self):
        fp1 = property_content_fingerprint(self.prop)
        save_draft(self.user, self.prop, {'format': 'story'})
        self.prop.sale_price = 2_000_000_000
        self.prop.save()
        fp2 = property_content_fingerprint(self.prop)
        self.assertNotEqual(fp1, fp2)
        draft = CRMPropertyContentStudioDraft.objects.get(property=self.prop, user=self.user)
        self.assertEqual(draft.property_fingerprint, fp1)
        url = reverse('workspace:crm_property_content_studio_draft', args=[self.prop.pk])
        res = self.client.put(
            url,
            data=json.dumps({'draft': {'active_tab': 'posters'}}),
            content_type='application/json',
        )
        data = res.json()
        self.assertTrue(data['draft_stale'])
        draft.refresh_from_db()
        self.assertEqual(draft.property_fingerprint, fp1)
        res = self.client.put(
            url,
            data=json.dumps({'sync_property': True}),
            content_type='application/json',
        )
        self.assertTrue(res.json()['ok'])
        draft.refresh_from_db()
        self.assertEqual(draft.property_fingerprint, fp2)

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

    def test_draft_put_rejects_invalid_json(self):
        url = reverse('workspace:crm_property_content_studio_draft', args=[self.prop.pk])
        res = self.client.put(url, data='not-json', content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])

    def test_draft_put_rejects_json_array_body(self):
        url = reverse('workspace:crm_property_content_studio_draft', args=[self.prop.pk])
        res = self.client.put(url, data='[]', content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_brand_put_rejects_invalid_json(self):
        url = reverse('workspace:crm_property_content_studio_brand', args=[self.prop.pk])
        res = self.client.put(url, data='"text"', content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_draft_brand_override_cleared_via_api(self):
        url = reverse('workspace:crm_property_content_studio_draft', args=[self.prop.pk])
        self.client.put(
            url,
            data=json.dumps({'draft': {'brand_override': {'brand_name': 'موقت'}}}),
            content_type='application/json',
        )
        res = self.client.put(
            url,
            data=json.dumps({'draft': {'brand_override': {}}}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        draft = CRMPropertyContentStudioDraft.objects.get(property=self.prop, user=self.user)
        self.assertEqual(draft.payload.get('brand_override'), {})

    def test_sync_updates_storyboard_price_and_keeps_cta(self):
        from workspace.services.property_content_studio.storyboard import build_default_storyboard

        prop_payload = build_studio_property_payload(self.prop)
        storyboard = build_default_storyboard(self.prop, prop_payload)
        for slide in storyboard['slides']:
            if slide['id'] == 'contact':
                slide['cta'] = 'CTA دستی'
        save_draft(self.user, self.prop, {'storyboard': storyboard})
        old_price = next(
            s['price_label'] for s in storyboard['slides'] if s['id'] == 'gallery_price'
        )
        self.prop.sale_price = 9_999_999_999
        self.prop.save()
        meta = sync_draft_with_property(self.user, self.prop)
        slides = meta['draft']['storyboard']['slides']
        gallery = next(s for s in slides if s['id'] == 'gallery_price')
        contact = next(s for s in slides if s['id'] == 'contact')
        self.assertNotEqual(gallery['price_label'], old_price)
        self.assertEqual(contact['cta'], 'CTA دستی')
        self.assertFalse(meta['needs_manual_review'])
        self.assertFalse(meta['stale'])

    def test_sync_stays_stale_when_ai_needs_review(self):
        save_draft(
            self.user,
            self.prop,
            {'ai': {'divar': {'body': 'متن تولید شده'}}},
        )
        self.prop.sale_price = 5_555_555_555
        self.prop.save()
        meta = sync_draft_with_property(self.user, self.prop)
        self.assertTrue(meta['needs_manual_review'])
        self.assertTrue(meta['stale'])
        draft = CRMPropertyContentStudioDraft.objects.get(property=self.prop, user=self.user)
        self.assertNotEqual(draft.property_fingerprint, property_content_fingerprint(self.prop))


class PropertyContentStudioConfidentialShareTests(TestCase):
    def setUp(self):
        from workspace.models import CRMAgency, CRMAgencyMember
        from workspace.services.crm_sharing import share_property

        self.owner = User.objects.create_user(username='owner', password='x', phone='09120000010')
        self.recipient = User.objects.create_user(username='recv', password='x', phone='09120000011')
        self.agency = CRMAgency.objects.create(name='آژانس استودیو', owner=self.owner)
        CRMAgencyMember.objects.create(agency=self.agency, user=self.owner, role='owner', is_active=True)
        advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.recipient, role='advisor', is_active=True,
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='ملک محرمانه',
            property_type='آپارتمان',
            neighborhood='محله خاص',
            city='تهران',
            notes='یادداشت مخفی',
        )
        share_property(
            self.owner,
            self.prop,
            advisor_member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
        )
        self.client = Client()
        self.client.force_login(self.recipient)

    def test_session_masks_neighborhood_for_confidential(self):
        url = reverse('workspace:crm_property_content_studio_session', args=[self.prop.pk])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['mask_sensitive'])
        self.assertEqual(data['property']['neighborhood'], '')
        self.assertNotIn('محله خاص', data['property']['location_line'])


class PropertyContentStudioDraftValidateTests(TestCase):
    def test_merge_accepts_legacy_draft(self):
        legacy = {'format': 'story', 'posters': {'luxury': {'headline': 'تست'}}}
        merged, _ = validate_and_merge_draft(None, legacy)
        self.assertEqual(merged['format'], 'story')
        self.assertEqual(merged['posters']['luxury']['headline'], 'تست')

    def test_rejects_unknown_keys(self):
        with self.assertRaises(DraftValidationError):
            validate_and_merge_draft(None, {'hack_field': True})

    def test_clears_brand_override_when_empty_dict_sent(self):
        stored = {'brand_override': {'brand_name': 'قدیمی', 'colors': {'primary': '#111111'}}}
        merged, _ = validate_and_merge_draft(stored, {'brand_override': {}})
        self.assertEqual(merged['brand_override'], {})

    def test_removes_poster_template_on_null(self):
        stored = {
            'posters': {
                'luxury': {'headline': 'سفارشی', 'pip_enabled': True},
                'minimal': {'headline': 'بماند'},
            },
        }
        merged, _ = validate_and_merge_draft(stored, {'posters': {'luxury': None}})
        self.assertNotIn('luxury', merged['posters'])
        self.assertEqual(merged['posters']['minimal']['headline'], 'بماند')

    def test_poster_reset_replaces_not_shallow_merge(self):
        stored = {'posters': {'luxury': {'headline': 'قدیم', 'pip_enabled': True}}}
        merged, _ = validate_and_merge_draft(
            stored,
            {'posters': {'luxury': {'headline': 'جدید'}}},
        )
        self.assertEqual(merged['posters']['luxury']['headline'], 'جدید')
        self.assertNotIn('pip_enabled', merged['posters']['luxury'])


class PropertyContentStudioQualityTests(TestCase):
    def test_quality_warns_short_notes(self):
        user = User.objects.create_user(username='q', password='x', phone='09120000004')
        prop = CRMProperty.objects.create(user=user, title='x', notes='کوتاه')
        report = build_quality_report(prop, user)
        labels = [i['label'] for i in report['items']]
        self.assertTrue(any('توضیحات' in l for l in labels))


class PropertyContentStudioAIFactsTests(TestCase):
    def test_strips_false_parking_claim(self):
        user = User.objects.create_user(username='aiu', password='x', phone='09120000012')
        prop = CRMProperty.objects.create(
            user=user,
            title='x',
            has_parking=False,
        )
        data = enforce_property_facts(
            prop,
            'divar_body',
            {'body': 'آپارتمان با پارکینگ دارد و نور عالی'},
        )
        self.assertNotIn('پارکینگ', data['body'])
