"""Mobile JWT API — Property Content Studio."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty, CRMResourceShare
from workspace.services.crm_sharing import share_property
from workspace.services.property_content_studio.manifest import manifest_version

User = get_user_model()


def _jwt_client(user):
    client = APITestCase.client_class()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
    return client


class MobileContentStudioAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='mowner', password='x', phone='09120000100')
        self.other = User.objects.create_user(username='moth', password='x', phone='09120000101')
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            title='ملک موبایل',
            property_type='آپارتمان',
            neighborhood='ونک',
            city='تهران',
        )

    def test_session_unauthorized_without_jwt(self):
        url = reverse(
            'mobile_api:property_content_studio_session',
            args=[self.prop.pk],
        )
        res = self.client.get(url)
        self.assertIn(res.status_code, (401, 403))

    def test_session_owner_ok(self):
        client = _jwt_client(self.owner)
        url = reverse('mobile_api:property_content_studio_session', args=[self.prop.pk])
        res = client.get(url)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['data']['property']['id'], self.prop.pk)

    def test_session_not_found_for_other_user(self):
        client = _jwt_client(self.other)
        url = reverse('mobile_api:property_content_studio_session', args=[self.prop.pk])
        res = client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_draft_put_masks_response_for_confidential_share(self):
        agency = CRMAgency.objects.create(name='A', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner', is_active=True)
        self.prop.agency = agency
        self.prop.save()
        advisor = User.objects.create_user(username='adv', password='x', phone='09120000102')
        member = CRMAgencyMember.objects.create(agency=agency, user=advisor, role='advisor', is_active=True)
        share_property(
            self.owner,
            self.prop,
            member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
        )
        client = _jwt_client(advisor)
        url = reverse('mobile_api:property_content_studio_draft', args=[self.prop.pk])
        res = client.put(
            url,
            {
                'draft': {
                    'posters': {
                        'pearlescent': {
                            'scene': {
                                'schemaVersion': 2,
                                'layers': [{
                                    'id': 'location-1',
                                    'type': 'bound_text',
                                    'binding': {
                                        'source': 'property',
                                        'field': 'location_line',
                                        'mode': 'override',
                                    },
                                    'text': 'ونک — تهران',
                                }],
                                'layerOrder': ['location-1'],
                            },
                        },
                    },
                },
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        layer = res.json()['data']['draft']['posters']['pearlescent']['scene']['layers'][0]
        self.assertEqual(layer['text'], '')

    def test_manifest_invalid_format_400(self):
        client = _jwt_client(self.owner)
        url = reverse(
            'mobile_api:property_content_studio_template_manifest',
            args=[self.prop.pk, 'pearlescent'],
        )
        res = client.get(url, {'format': 'invalid'})
        self.assertEqual(res.status_code, 400)

    def test_manifest_unknown_template_404(self):
        client = _jwt_client(self.owner)
        url = reverse(
            'mobile_api:property_content_studio_template_manifest',
            args=[self.prop.pk, 'luxury'],
        )
        res = client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_manifest_ok_includes_dynamic_content(self):
        client = _jwt_client(self.owner)
        url = reverse(
            'mobile_api:property_content_studio_template_manifest',
            args=[self.prop.pk, 'pearl_gallery'],
        )
        res = client.get(url, {'format': 'story'})
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']
        self.assertEqual(data.get('manifest_version'), manifest_version())
        self.assertIn('dynamic_content', data)
        self.assertEqual(
            data['dynamic_content']['layers']['meta-1']['resolver'],
            'overlay_meta_summary',
        )

    def _share_confidential(self):
        agency = CRMAgency.objects.create(name='A', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner', is_active=True)
        self.prop.agency = agency
        self.prop.neighborhood = 'ونک'
        self.prop.save()
        advisor = User.objects.create_user(username='adv', password='x', phone='09120000102')
        member = CRMAgencyMember.objects.create(agency=agency, user=advisor, role='advisor', is_active=True)
        share_property(
            self.owner,
            self.prop,
            member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
        )
        return _jwt_client(advisor)

    def _share_collaborative(self):
        agency = CRMAgency.objects.create(name='B', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner', is_active=True)
        self.prop.agency = agency
        self.prop.neighborhood = 'ونک'
        self.prop.save()
        advisor = User.objects.create_user(username='coladv', password='x', phone='09120000103')
        member = CRMAgencyMember.objects.create(agency=agency, user=advisor, role='advisor', is_active=True)
        share_property(
            self.owner,
            self.prop,
            member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_COLLABORATIVE,
        )
        return _jwt_client(advisor)

    def test_session_confidential_masks_location_and_file_code(self):
        client = self._share_confidential()
        url = reverse('mobile_api:property_content_studio_session', args=[self.prop.pk])
        res = client.get(url)
        self.assertEqual(res.status_code, 200)
        prop = res.json()['data']['property']
        self.assertEqual(prop.get('file_code'), '')
        self.assertNotIn('ونک', prop.get('location_line') or '')
        self.assertNotIn('ونک', prop.get('title') or '')
        self.assertNotIn('ونک', prop.get('headline') or '')

    def test_session_collaborative_shows_location(self):
        client = self._share_collaborative()
        url = reverse('mobile_api:property_content_studio_session', args=[self.prop.pk])
        res = client.get(url)
        self.assertEqual(res.status_code, 200)
        prop = res.json()['data']['property']
        self.assertTrue(prop.get('file_code'))
        self.assertIn('ونک', prop.get('location_line') or '')

    def test_draft_sync_property_masks_response_for_confidential(self):
        client = self._share_confidential()
        url = reverse('mobile_api:property_content_studio_draft', args=[self.prop.pk])
        res = client.put(url, {'sync_property': True}, format='json')
        self.assertEqual(res.status_code, 200)
        prop = res.json()['data']['property']
        self.assertNotIn('ونک', prop.get('location_line') or '')

    def test_manifest_unavailable_503(self):
        from unittest.mock import patch

        client = _jwt_client(self.owner)
        url = reverse(
            'mobile_api:property_content_studio_template_manifest',
            args=[self.prop.pk, 'pearl_gallery'],
        )
        with patch(
            'workspace.services.property_content_studio.manifest.manifests_available',
            return_value=False,
        ):
            res = client.get(url, {'format': 'story'})
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json().get('code'), 'MANIFEST_UNAVAILABLE')

    def test_manifest_version_mismatch_503(self):
        from unittest.mock import patch

        from workspace.services.property_content_studio import manifest as manifest_mod

        client = _jwt_client(self.owner)
        url = reverse(
            'mobile_api:property_content_studio_template_manifest',
            args=[self.prop.pk, 'pearl_gallery'],
        )
        with patch.object(manifest_mod, 'manifest_version', return_value='pcs-manifest-indexonly'):
            with patch.object(
                manifest_mod,
                '_load_manifest_file',
                return_value={
                    'scene': {'layers': [], 'layerOrder': []},
                    'manifest_version': 'pcs-manifest-fileonly',
                },
            ):
                res = client.get(url, {'format': 'story'})
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json().get('code'), 'MANIFEST_VERSION_MISMATCH')
