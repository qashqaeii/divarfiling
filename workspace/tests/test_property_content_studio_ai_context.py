"""Property Content Studio AI context — confidential access."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty
from ai_workspace.services.property_content_studio_ai import _studio_context

User = get_user_model()


class PropertyContentStudioAIContextMaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='aiu2', password='x', phone='09120000021')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان محله مخفی',
            property_type='آپارتمان',
            neighborhood='محله مخفی',
            city='تهران',
            token='SECRET-TOKEN',
            notes='یادداشت CRM',
        )

    def test_studio_context_masks_title_token_and_notes_paths(self):
        ctx = _studio_context(self.user, self.prop, 'divar_titles', mask_sensitive=True)
        self.assertNotIn('محله مخفی', ctx.get('title') or '')
        self.assertNotIn(self.prop.title, ctx.get('title') or '')
        self.assertEqual(ctx.get('token'), '')
        self.assertEqual(ctx.get('tab_extra'), '')
        self.assertEqual(ctx.get('tab_text'), '')
        self.assertNotIn('محله مخفی', ctx.get('studio', {}).get('location_line') or '')
        self.assertNotIn('محله مخفی', ctx.get('studio', {}).get('title') or '')
