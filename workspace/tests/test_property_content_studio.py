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
from workspace.services.property_content_studio.adapter import (
    build_studio_property_payload,
    format_divar_facts_outline,
)
from workspace.services.property_content_studio.draft import save_draft, sync_draft_with_property
from workspace.services.property_content_studio.draft_validate import (
    DraftValidationError,
    _normalize_poster_config,
    validate_and_merge_draft,
)
from workspace.services.property_content_studio.feature_catalog import (
    EDITOR_FEATURE_STABLE_KEYS,
    build_editor_feature_catalog,
)
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
        self.prop.amenities = 'نورگیر عالی و بالکن'
        self.prop.save()
        payload2 = build_studio_property_payload(self.prop)
        self.assertIn('نورگیر', payload2['description_excerpt'])
        self.assertNotIn('یادداشت محرمانه', payload2['description_excerpt'])

    def test_divar_facts_outline_lists_core_specs(self):
        payload = build_studio_property_payload(self.prop)
        outline = format_divar_facts_outline(payload)
        self.assertIn('متراژ', outline)
        self.assertIn('سعادت', outline)
        self.assertIn('آسانسور', outline)
        self.assertNotIn('پارکینگ', outline)

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
        cover = next(s for s in storyboard['slides'] if s['id'] == 'cover')
        self.assertEqual(cover.get('template_id'), 'pearlescent')
        self.assertEqual(cover.get('label'), 'قاب استوری')
        self.assertEqual(cover.get('poster', {}).get('font_key'), 'gulzar')
        self.assertEqual(cover.get('poster', {}).get('headline_scale'), 130)
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

    def test_storyboard_extra_photos_when_more_than_three_images(self):
        from workspace.services.property_content_studio.storyboard import (
            build_default_storyboard,
            merge_storyboard_with_property,
        )

        payload = {
            'images': ['a.jpg', 'b.jpg', 'c.jpg', 'd.jpg'],
            'headline': 'عنوان',
            'location_line': 'تهران',
            'price': {'show': True, 'label': '۱۲ میلیارد'},
        }
        storyboard = build_default_storyboard(None, payload)
        ids = [s['id'] for s in storyboard['slides']]
        self.assertIn('extra_photos', ids)
        extra = next(s for s in storyboard['slides'] if s['id'] == 'extra_photos')
        self.assertEqual(extra.get('template_id'), 'sculptural')
        self.assertEqual(extra.get('label'), 'عاج')
        self.assertEqual(extra.get('image_index'), 3)

        few = build_default_storyboard(None, {'images': ['a.jpg', 'b.jpg', 'c.jpg']})
        self.assertNotIn('extra_photos', [s['id'] for s in few['slides']])

        merged = merge_storyboard_with_property(storyboard, {'images': ['a.jpg', 'b.jpg']})
        self.assertNotIn('extra_photos', [s['id'] for s in merged['slides']])

    def test_storyboard_emerald_showcase_when_at_least_two_images(self):
        from workspace.services.property_content_studio.storyboard import (
            build_default_storyboard,
            merge_storyboard_with_property,
        )

        payload = {
            'images': ['a.jpg', 'b.jpg'],
            'headline': 'عنوان',
            'location_line': 'تهران',
        }
        storyboard = build_default_storyboard(None, payload)
        ids = [s['id'] for s in storyboard['slides']]
        self.assertIn('emerald_showcase', ids)
        emerald = next(s for s in storyboard['slides'] if s['id'] == 'emerald_showcase')
        self.assertEqual(emerald.get('template_id'), 'emerald_atelier')
        self.assertEqual(emerald.get('label'), 'زمرد')
        self.assertEqual(emerald.get('image_index'), 0)
        self.assertEqual(emerald.get('image_indices'), [1])

        one = build_default_storyboard(None, {'images': ['a.jpg']})
        self.assertNotIn('emerald_showcase', [s['id'] for s in one['slides']])

        merged = merge_storyboard_with_property(storyboard, {'images': ['a.jpg']})
        self.assertNotIn('emerald_showcase', [s['id'] for s in merged['slides']])

    def test_storyboard_pearl_showcase_when_at_least_two_images(self):
        from workspace.services.property_content_studio.storyboard import (
            build_default_storyboard,
            merge_storyboard_with_property,
        )

        payload = {
            'images': ['a.jpg', 'b.jpg'],
            'headline': 'عنوان',
            'location_line': 'تهران',
        }
        storyboard = build_default_storyboard(None, payload)
        ids = [s['id'] for s in storyboard['slides']]
        self.assertIn('pearl_showcase', ids)
        pearl = next(s for s in storyboard['slides'] if s['id'] == 'pearl_showcase')
        self.assertEqual(pearl.get('template_id'), 'pearl_gallery')
        self.assertEqual(pearl.get('label'), 'مروارید')
        self.assertEqual(pearl.get('image_index'), 0)
        self.assertEqual(pearl.get('image_indices'), [1])

        one = build_default_storyboard(None, {'images': ['a.jpg']})
        self.assertNotIn('pearl_showcase', [s['id'] for s in one['slides']])

        merged = merge_storyboard_with_property(storyboard, {'images': ['a.jpg']})
        self.assertNotIn('pearl_showcase', [s['id'] for s in merged['slides']])

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


class PropertyContentStudioSceneAndFeatureCatalogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pcs_scene', password='x', phone='09120000020')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ۸۰ متری',
            property_type='آپارتمان',
            deal_mode='فروش',
            area=80,
            rooms='۲',
            neighborhood='جردن',
            city='تهران',
            sale_price=30_000_000_000,
            has_elevator=True,
            has_parking=True,
            feature_data={'جنس کف': 'سرامیک', '_location_precision': 'approximate'},
        )

    def _valid_scene(self, **overrides):
        base = {
            'schemaVersion': 2,
            'canvas': {'width': 1080, 'height': 1920, 'format': 'story'},
            'templateId': 'luxury',
            'layers': [
                {
                    'id': 'headline-1',
                    'type': 'bound_text',
                    'name': 'عنوان',
                    'x': 40,
                    'y': 120,
                    'width': 400,
                    'height': 80,
                    'binding': {'source': 'property', 'field': 'price', 'mode': 'linked'},
                },
            ],
            'layerOrder': ['headline-1'],
        }
        base.update(overrides)
        return base

    def test_scene_normalization_in_poster_config(self):
        conf = _normalize_poster_config(
            {'headline': 'تست', 'scene': self._valid_scene()},
            'luxury',
        )
        self.assertIn('scene', conf)
        scene = conf['scene']
        self.assertEqual(scene['schemaVersion'], 2)
        self.assertEqual(scene['canvas']['format'], 'story')
        self.assertEqual(len(scene['layers']), 1)
        self.assertEqual(scene['layerOrder'], ['headline-1'])
        self.assertEqual(conf['headline'], 'تست')

    def test_poster_settings_merged_with_scene(self):
        conf = _normalize_poster_config(
            {
                'posterSettings': {'headline_scale': 120},
                'scene': self._valid_scene(),
            },
            'luxury',
        )
        self.assertEqual(conf['headline_scale'], 120)
        self.assertIn('posterSettings', conf)
        self.assertEqual(conf['posterSettings']['headline_scale'], 120)

    def test_scene_rejects_nan_coordinates(self):
        scene = self._valid_scene()
        scene['layers'][0]['x'] = float('nan')
        with self.assertRaises(DraftValidationError):
            _normalize_poster_config({'scene': scene}, 'luxury')

    def test_scene_rejects_duplicate_layer_ids(self):
        scene = self._valid_scene()
        scene['layers'].append(dict(scene['layers'][0]))
        with self.assertRaises(DraftValidationError):
            _normalize_poster_config({'scene': scene}, 'luxury')

    def test_scene_rejects_layer_order_mismatch(self):
        scene = self._valid_scene(layerOrder=['missing-id'])
        with self.assertRaises(DraftValidationError):
            _normalize_poster_config({'scene': scene}, 'luxury')

    def test_scene_rejects_parent_cycle(self):
        scene = self._valid_scene(
            layers=[
                {'id': 'a', 'type': 'group', 'name': 'A', 'parentId': 'b'},
                {'id': 'b', 'type': 'group', 'name': 'B', 'parentId': 'a'},
            ],
            layerOrder=['a', 'b'],
        )
        with self.assertRaises(DraftValidationError):
            _normalize_poster_config({'scene': scene}, 'luxury')

    def test_editor_features_in_payload(self):
        payload = build_studio_property_payload(self.prop)
        features = payload['editor_features']
        self.assertTrue(features)
        keys = {item['key'] for item in features}
        self.assertIn('area_label', keys)
        self.assertIn('price', keys)
        self.assertIn('amenity.0', keys)
        for item in features:
            self.assertIn('visibilityKey', item)
            self.assertTrue(item['key'] == item['id'])
            self.assertNotIn('_location_precision', item['key'])

    def test_feature_catalog_respects_stable_keys(self):
        catalog = build_editor_feature_catalog(self.prop, {'amenities': True})
        for item in catalog:
            key = item['key']
            if key.startswith('amenity.'):
                self.assertTrue(key[8:].isdigit())
            else:
                self.assertIn(key, EDITOR_FEATURE_STABLE_KEYS)

    def test_feature_catalog_visibility_masks_price(self):
        catalog = build_editor_feature_catalog(self.prop, {'price': False})
        price_row = next(item for item in catalog if item['key'] == 'price')
        self.assertEqual(price_row['value'], '')
        area_row = next(item for item in catalog if item['key'] == 'area_label')
        self.assertTrue(area_row['value'])

    def test_draft_merge_accepts_poster_with_scene(self):
        merged, _ = validate_and_merge_draft(
            None,
            {'posters': {'luxury': {'scene': self._valid_scene()}}},
        )
        self.assertIn('scene', merged['posters']['luxury'])


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


class PropertyContentStudioPosterHeadlineAiTests(TestCase):
    def test_normalize_poster_headlines_clips_length(self):
        from ai_workspace.services.property_content_studio_payload import (
            normalize_studio_ai_payload,
            validate_studio_ai_payload,
        )
        from workspace.services.property_content_studio.constants import POSTER_AD_HEADLINE_MAX_CHARS

        long = 'ا' * 80
        data = normalize_studio_ai_payload('poster_headlines', {
            'titles': [{'style': 'کوتاه', 'text': long}],
        })
        self.assertTrue(validate_studio_ai_payload('poster_headlines', data))
        self.assertLessEqual(len(data['titles'][0]['text']), POSTER_AD_HEADLINE_MAX_CHARS)
