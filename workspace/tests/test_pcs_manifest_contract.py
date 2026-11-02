"""PCS static manifest contract — parity with pcs-template-scenes.js (no runtime Node)."""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from workspace.services.property_content_studio.constants import POSTER_TEMPLATES, OUTPUT_FORMATS
from workspace.services.property_content_studio.manifest import (
    ManifestNotFoundError,
    get_template_manifest,
    manifest_version,
)

_ACTIVE_IDS = [t['id'] for t in POSTER_TEMPLATES]
_FORMATS = list(OUTPUT_FORMATS.keys())
_MANIFEST_ROOT = Path(settings.BASE_DIR) / 'static' / 'workspace' / 'pcs' / 'manifests'
_SENTINEL = 'PCS_MANIFEST_'


class PCSManifestCatalogTests(SimpleTestCase):
    def test_thirteen_templates_three_formats_on_disk(self):
        index = json.loads((_MANIFEST_ROOT / 'index.json').read_text(encoding='utf-8'))
        self.assertEqual(len(_ACTIVE_IDS), 13)
        self.assertEqual(set(index.get('templates') or []), set(_ACTIVE_IDS))
        self.assertEqual(set(index.get('formats') or []), set(_FORMATS))
        entries = index.get('entries') or []
        self.assertEqual(len(entries), 39)
        ver = index.get('manifest_version')
        self.assertTrue(str(ver).startswith('pcs-manifest-'))
        for tid in _ACTIVE_IDS:
            for fmt in _FORMATS:
                path = _MANIFEST_ROOT / tid / f'{fmt}.json'
                self.assertTrue(path.is_file(), msg=f'missing {tid}/{fmt}')
                data = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(data.get('manifest_version'), ver)
                self.assertNotIn(_SENTINEL, path.read_text(encoding='utf-8'))

    def test_dynamic_content_contract_pearl_gallery_story(self):
        data = json.loads(
            (_MANIFEST_ROOT / 'pearl_gallery' / 'story.json').read_text(encoding='utf-8'),
        )
        dc = data.get('dynamic_content') or {}
        self.assertEqual(dc.get('schema_version'), 1)
        layers = dc.get('layers') or {}
        self.assertEqual(layers.get('headline-1', {}).get('resolver'), 'poster_headline')
        self.assertEqual(layers.get('meta-1', {}).get('resolver'), 'overlay_meta_summary')
        headline = next(l for l in data['scene']['layers'] if l['id'] == 'headline-1')
        self.assertEqual(headline['style']['fill'], '#f4f1eb')
        self.assertEqual(headline.get('contentContract', {}).get('resolver'), 'poster_headline')
        self.assertEqual(headline.get('text'), '')

    def test_dynamic_content_contract_pearlescent_story(self):
        data = json.loads(
            (_MANIFEST_ROOT / 'pearlescent' / 'story.json').read_text(encoding='utf-8'),
        )
        dc = data.get('dynamic_content') or {}
        self.assertEqual(
            dc.get('layers', {}).get('meta-1', {}).get('resolver'),
            'pearlescent_meta_lines',
        )
        loc = next(l for l in data['scene']['layers'] if l['id'] == 'location-1')
        self.assertEqual(loc['binding']['field'], 'location_line')
        footer = next(l for l in data['scene']['layers'] if l['id'] == 'footer-1')
        self.assertEqual(footer['binding']['source'], 'brand')

    def test_manifest_version_mismatch_raises(self):
        from workspace.services.property_content_studio import manifest as manifest_mod

        manifest_mod.clear_manifest_cache()
        index_ver = manifest_version()
        path = _MANIFEST_ROOT / 'pearlescent' / 'story.json'
        raw = json.loads(path.read_text(encoding='utf-8'))
        try:
            raw['manifest_version'] = 'pcs-manifest-deadbeef000000'
            path.write_text(json.dumps(raw), encoding='utf-8')
            manifest_mod.clear_manifest_cache()
            with self.assertRaises(ManifestNotFoundError):
                get_template_manifest('pearlescent', 'story', request=None)
        finally:
            raw['manifest_version'] = index_ver
            path.write_text(json.dumps(raw, indent=2) + '\n', encoding='utf-8')
            manifest_mod.clear_manifest_cache()
