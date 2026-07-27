"""تست زمان‌بندی تطبیق پس از استخراج — نباید درخواست آپلود را block کند."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from workspace.services.crm_match_notifications import (
    notify_matches_after_extract,
    schedule_notify_matches_after_extract,
)

User = get_user_model()


class SchedulePostExtractMatchingTests(TransactionTestCase):
    def test_schedule_starts_background_thread(self):
        user = User.objects.create_user(username='09121112233', password='test')
        with patch('workspace.services.crm_match_notifications.threading.Thread') as thread_cls:
            thread_cls.return_value.start = lambda: None
            schedule_notify_matches_after_extract(user, dataset_id='ds-1')
        thread_cls.assert_called_once()
        kwargs = thread_cls.call_args.kwargs
        self.assertTrue(kwargs.get('daemon'))
        self.assertEqual(kwargs['args'][0], user.pk)
        self.assertEqual(kwargs['args'][1], 'ds-1')

    def test_notify_passes_dataset_scope(self):
        user = User.objects.create_user(username='09124445566', password='test')
        with patch(
            'workspace.services.crm_match_notifications.process_user_customer_matches',
            return_value=0,
        ) as process_mock:
            notify_matches_after_extract(user, dataset_id='abc-123')
        process_mock.assert_called_once()
        _, kwargs = process_mock.call_args
        self.assertEqual(kwargs['dataset_id'], 'abc-123')
        self.assertEqual(kwargs['max_customers'], 60)


class PostExtractMatchingRunnerTests(TestCase):
    def test_runner_ignores_missing_user(self):
        from workspace.services.crm_match_notifications import _run_post_extract_matching

        with patch(
            'workspace.services.crm_match_notifications.notify_matches_after_extract',
        ) as notify_mock:
            _run_post_extract_matching(999_999, dataset_id='x')
        notify_mock.assert_not_called()
