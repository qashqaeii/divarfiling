"""Confidential export masking for mobile Property Content Studio."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, CRMPropertyContentStudioDraft, CRMResourceShare
from workspace.services.property_content_studio.adapter import build_studio_property_payload
from workspace.services.property_content_studio.draft import export_draft_payload_for_access, save_draft, sync_draft_with_property
from workspace.services.property_content_studio.mobile_export import (
    collect_redact_fragments,
    enrich_property_payload_for_mobile_export,
)

User = get_user_model()


class PropertyContentStudioMobileExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='masku', password='x', phone='09120000099')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان محله خاص',
            property_type='آپارتمان',
            neighborhood='محله خاص',
            city='تهران',
            sale_price=1_000_000_000,
        )

    def test_property_payload_masks_file_code_and_features(self):
        full = build_studio_property_payload(self.prop, mask_sensitive=False)
        masked = build_studio_property_payload(self.prop, mask_sensitive=True)
        self.assertTrue(full.get('file_code'))
        self.assertEqual(masked.get('file_code'), '')
        self.assertNotIn('محله خاص', masked.get('location_line') or '')
        enriched = enrich_property_payload_for_mobile_export(masked, self.prop, mask_sensitive=True)
        codes = [r['value'] for r in enriched.get('editor_features') or [] if r.get('key') == 'file_code']
        self.assertTrue(all(v == '' for v in codes))

    def test_draft_export_redacts_linked_location_without_db_mutation(self):
        draft_payload = {
            'posters': {
                'pearlescent': {
                    'scene': {
                        'schemaVersion': 2,
                        'layers': [
                            {
                                'id': 'location-1',
                                'type': 'bound_text',
                                'binding': {
                                    'source': 'property',
                                    'field': 'location_line',
                                    'mode': 'linked',
                                },
                                'text': 'محله خاص — تهران',
                            },
                        ],
                        'layerOrder': ['location-1'],
                    },
                },
            },
        }
        save_draft(self.user, self.prop, draft_payload)
        row = CRMPropertyContentStudioDraft.objects.get(property=self.prop, user=self.user)
        stored_text = row.payload['posters']['pearlescent']['scene']['layers'][0]['text']

        exported = export_draft_payload_for_access(
            row.payload,
            mask_sensitive=True,
            prop=self.prop,
        )
        self.assertEqual(
            exported['posters']['pearlescent']['scene']['layers'][0]['text'],
            '',
        )
        row.refresh_from_db()
        self.assertEqual(
            row.payload['posters']['pearlescent']['scene']['layers'][0]['text'],
            stored_text,
        )

    def test_sync_uses_mask_sensitive_on_property(self):
        CRMPropertyContentStudioDraft.objects.create(
            property=self.prop,
            user=self.user,
            payload={'version': 1, 'storyboard': {'slides': [], 'order': []}},
        )
        meta = sync_draft_with_property(self.user, self.prop, mask_sensitive=True)
        self.assertNotIn('محله خاص', meta['property'].get('location_line') or '')

    def test_collect_redact_fragments_includes_neighborhood(self):
        frags = collect_redact_fragments(self.prop)
        self.assertTrue(any('محله خاص' in f for f in frags))

    def test_property_payload_sale_rent_and_sparse(self):
        sale = build_studio_property_payload(self.prop, mask_sensitive=False)
        self.assertTrue(sale['price']['show'])
        self.assertIn('deal_mode', sale['price'])

        rent_prop = CRMProperty.objects.create(
            user=self.user,
            title='اجاره',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            deposit=500_000_000,
            monthly_rent=20_000_000,
            city='تهران',
        )
        rent = build_studio_property_payload(rent_prop, mask_sensitive=False)
        self.assertTrue(rent['price']['show'])
        self.assertIn('ودیعه', rent['price']['label'])

        sparse = CRMProperty.objects.create(
            user=self.user,
            title='',
            property_type='زمین',
            city='اصفهان',
        )
        sparse_payload = build_studio_property_payload(sparse, mask_sensitive=False)
        self.assertEqual(sparse_payload.get('area_label'), '')
        self.assertFalse(sparse_payload['price']['show'])

    def test_detached_custom_text_preserved_when_not_property_derived(self):
        draft_payload = {
            'posters': {
                'pearlescent': {
                    'scene': {
                        'schemaVersion': 2,
                        'layers': [
                            {
                                'id': 'headline-1',
                                'type': 'text',
                                'binding': {
                                    'source': 'property',
                                    'field': 'headline',
                                    'mode': 'detached',
                                },
                                'text': 'عنوان سفارشی مشاور',
                            },
                        ],
                        'layerOrder': ['headline-1'],
                    },
                },
            },
        }
        exported = export_draft_payload_for_access(
            draft_payload,
            mask_sensitive=True,
            prop=self.prop,
        )
        self.assertEqual(
            exported['posters']['pearlescent']['scene']['layers'][0]['text'],
            'عنوان سفارشی مشاور',
        )

    def test_confidential_title_and_headline_hide_neighborhood_in_raw_title(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ۱۲۰ متری ونک',
            property_type='آپارتمان',
            neighborhood='ونک',
            city='تهران',
            area=120,
        )
        masked = build_studio_property_payload(prop, mask_sensitive=True)
        self.assertNotIn('ونک', masked['title'])
        self.assertNotIn('ونک', masked['headline'])
        self.assertIn('تهران', masked['title'])

    def test_detached_redacts_when_text_contains_neighborhood(self):
        draft_payload = {
            'posters': {
                'pearlescent': {
                    'scene': {
                        'schemaVersion': 2,
                        'layers': [
                            {
                                'id': 'headline-1',
                                'type': 'text',
                                'binding': {
                                    'source': 'property',
                                    'field': 'headline',
                                    'mode': 'detached',
                                },
                                'text': 'فروش در ونک',
                            },
                        ],
                        'layerOrder': ['headline-1'],
                    },
                },
            },
        }
        exported = export_draft_payload_for_access(
            draft_payload,
            mask_sensitive=True,
            prop=self.prop,
        )
        self.assertEqual(
            exported['posters']['pearlescent']['scene']['layers'][0]['text'],
            '',
        )
