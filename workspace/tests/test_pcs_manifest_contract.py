"""PCS static manifest contract — parity with pcs-template-scenes.js (no runtime Node)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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
_FIXTURES = Path(settings.BASE_DIR) / 'workspace' / 'tests' / 'fixtures' / 'pcs'
_SENTINEL = 'PCS_MANIFEST_'


def _load_manifest(tid: str, fmt: str) -> dict:
    return json.loads((_MANIFEST_ROOT / tid / f'{fmt}.json').read_text(encoding='utf-8'))


def _layer_by_id(data: dict, layer_id: str):
    for layer in data.get('scene', {}).get('layers') or []:
        if layer.get('id') == layer_id:
            return layer
    return None


def _meta_resolver_for_template(template_id: str) -> str:
    return 'pearlescent_meta_lines' if template_id == 'pearlescent' else 'overlay_meta_summary'


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
        self.assertNotIn('generated_at', index)
        for tid in _ACTIVE_IDS:
            for fmt in _FORMATS:
                path = _MANIFEST_ROOT / tid / f'{fmt}.json'
                self.assertTrue(path.is_file(), msg=f'missing {tid}/{fmt}')
                data = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(data.get('manifest_version'), ver)
                self.assertNotIn(_SENTINEL, path.read_text(encoding='utf-8'))

    def test_all_templates_dynamic_headline_meta_contracts(self):
        ver = manifest_version()
        self.assertTrue(ver)
        for tid in _ACTIVE_IDS:
            for fmt in _FORMATS:
                data = _load_manifest(tid, fmt)
                self.assertEqual(data.get('manifest_version'), ver)
                dc = data.get('dynamic_content') or {}
                self.assertEqual(dc.get('schema_version'), 1)
                headline = _layer_by_id(data, 'headline-1')
                if headline:
                    self.assertEqual(headline.get('text'), '')
                    self.assertEqual(
                        headline.get('contentContract', {}).get('resolver'),
                        'poster_headline',
                    )
                    self.assertEqual(
                        dc.get('layers', {}).get('headline-1', {}).get('resolver'),
                        'poster_headline',
                    )
                meta = _layer_by_id(data, 'meta-1')
                if meta:
                    expected = _meta_resolver_for_template(tid)
                    self.assertEqual(meta.get('text'), '')
                    self.assertEqual(meta.get('contentContract', {}).get('resolver'), expected)
                    self.assertEqual(dc.get('layers', {}).get('meta-1', {}).get('resolver'), expected)
                for layer in data['scene']['layers']:
                    if layer.get('type') not in ('text', 'bound_text'):
                        continue
                    text = layer.get('text') or ''
                    self.assertNotIn(_SENTINEL, text)
                    if layer.get('contentContract') and layer.get('binding', {}).get('mode') != 'detached':
                        self.assertEqual(text, '', msg=f'{tid}/{fmt} layer {layer.get("id")}')
                    if '·' in text and ':' in text:
                        self.fail(f'orphan label text in {tid}/{fmt} {layer.get("id")!r}: {text!r}')

    def test_dynamic_content_contract_pearl_gallery_story(self):
        data = _load_manifest('pearl_gallery', 'story')
        dc = data.get('dynamic_content') or {}
        self.assertEqual(dc.get('schema_version'), 1)
        layers = dc.get('layers') or {}
        self.assertEqual(layers.get('headline-1', {}).get('resolver'), 'poster_headline')
        self.assertEqual(layers.get('meta-1', {}).get('resolver'), 'overlay_meta_summary')
        headline = _layer_by_id(data, 'headline-1')
        self.assertEqual(headline['style']['fill'], '#f4f1eb')
        self.assertEqual(headline.get('contentContract', {}).get('resolver'), 'poster_headline')
        self.assertEqual(headline.get('text'), '')

    def test_dynamic_content_contract_pearlescent_story(self):
        data = _load_manifest('pearlescent', 'story')
        dc = data.get('dynamic_content') or {}
        self.assertEqual(
            dc.get('layers', {}).get('meta-1', {}).get('resolver'),
            'pearlescent_meta_lines',
        )
        loc = _layer_by_id(data, 'location-1')
        self.assertEqual(loc['binding']['field'], 'location_line')
        footer = _layer_by_id(data, 'footer-1')
        self.assertEqual(footer['binding']['source'], 'brand')

    def test_golden_fixture_pearl_gallery_headline_geometry_and_style(self):
        golden = json.loads(
            (_FIXTURES / 'golden_pearl_gallery_story_headline.json').read_text(encoding='utf-8'),
        )
        data = _load_manifest(golden['template_id'], golden['format'])
        layer = _layer_by_id(data, golden['layer_id'])
        self.assertIsNotNone(layer)
        for key, val in golden['style'].items():
            self.assertEqual(layer['style'].get(key), val, msg=f'style.{key}')
        for key, val in golden['geometry'].items():
            self.assertEqual(layer.get(key), val, msg=f'geometry.{key}')
        self.assertEqual(layer.get('contentContract'), golden['contentContract'])
        self.assertEqual(layer.get('text'), '')

    def test_golden_fixture_pearlescent_meta_contract(self):
        golden = json.loads(
            (_FIXTURES / 'golden_pearlescent_story_meta.json').read_text(encoding='utf-8'),
        )
        data = _load_manifest(golden['template_id'], golden['format'])
        layer = _layer_by_id(data, golden['layer_id'])
        self.assertIsNotNone(layer)
        self.assertEqual(layer.get('contentContract'), golden['contentContract'])
        self.assertEqual(layer.get('text'), '')
        self.assertEqual(layer['style'].get('fill'), golden['style']['fill'])

    def test_manifest_version_mismatch_raises(self):
        from workspace.services.property_content_studio import manifest as manifest_mod

        manifest_mod.clear_manifest_cache()
        with patch.object(manifest_mod, 'manifest_version', return_value='pcs-manifest-indexonly'):
            with patch.object(
                manifest_mod,
                '_load_manifest_file',
                return_value={
                    'scene': {'layers': [], 'layerOrder': []},
                    'manifest_version': 'pcs-manifest-fileonly',
                },
            ):
                with self.assertRaises(ManifestNotFoundError):
                    get_template_manifest('pearlescent', 'story', request=None)
        manifest_mod.clear_manifest_cache()
