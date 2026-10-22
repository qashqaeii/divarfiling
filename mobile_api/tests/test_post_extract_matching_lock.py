from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.services.crm_match_notifications import _run_post_extract_matching

User = get_user_model()


class PostExtractMatchingLockTests(TestCase):
    def test_duplicate_run_skipped_while_lock_held(self):
        user = User.objects.create_user(username='09129990000', password='x')
        with patch('django.core.cache.cache') as cache_mock:
            cache_mock.add.side_effect = [True, False]
            with patch(
                'workspace.services.crm_match_notifications.notify_matches_after_extract',
            ) as notify_mock:
                _run_post_extract_matching(user.pk, dataset_id='ds-1')
                _run_post_extract_matching(user.pk, dataset_id='ds-1')
        notify_mock.assert_called_once()
