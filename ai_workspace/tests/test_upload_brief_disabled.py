"""upload_brief غیرفعال — بدون LLM و بدون UI."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ai_workspace.constants import FEATURE_UPLOAD_BRIEF
from ai_workspace.services.quota import get_status, status_to_dict


@override_settings(AI_ENABLED=True)
class UploadBriefDisabledTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='uploadai', password='pass', phone='09121112233',
        )
        self.url = reverse('workspace:ai_workspace:upload_brief')

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    @patch('ai_workspace.services.upload_brief.generate_brief')
    def test_endpoint_returns_feature_disabled_without_llm(self, mocked_brief, _license):
        session = self.client.session
        session['upload_batch'] = {'imported': [{'id': '00000000-0000-0000-0000-000000000001'}]}
        session.save()
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data.get('ok', True))
        self.assertEqual(data.get('code'), 'feature_disabled')
        mocked_brief.assert_not_called()

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_quota_status_excludes_upload_brief(self, _license):
        self.client.force_login(self.user)
        status = status_to_dict(get_status(self.user))
        self.assertNotIn(FEATURE_UPLOAD_BRIEF, status.get('features') or {})

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_dataset_list_has_no_upload_brief_cta(self, _license):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:dataset_list'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertNotIn('upload_brief', html)
        self.assertNotIn('تحلیل هوشمند آپلود', html)
        self.assertNotIn('wsAiUploadBrief', html)
