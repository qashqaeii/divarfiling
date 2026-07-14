"""تست سرویس ممیزی تیم آژانس."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMAgencyAuditLog
from workspace.services.crm_agency import create_agency
from workspace.services.crm_audit import (
    audit_event_label,
    build_audit_timeline,
    describe_audit_log,
    log_agency_audit,
)

User = get_user_model()


class CRMAuditServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner1', password='x')
        self.agency = create_agency(self.owner, 'آژانس تست')

    def test_log_and_describe_message_event(self):
        log = log_agency_audit(
            self.agency, self.owner, 'message.sent',
            {'thread_id': 5, 'message_id': 9, 'kind': 'direct'},
        )
        meta = describe_audit_log(log)
        self.assertEqual(meta['category'], 'messages')
        self.assertEqual(meta['tone'], 'create')
        self.assertIn('ارسال', meta['summary'])
        self.assertTrue(any(c['label'] == 'گفتگو' for c in meta['payload_chips']))

    def test_audit_event_label_persian(self):
        self.assertEqual(audit_event_label('lead.assigned'), 'سرنخ به مشاور تخصیص یافت')

    def test_build_timeline_groups_by_day(self):
        log_agency_audit(self.agency, self.owner, 'agency.updated', {'fields': ['name']})
        log_agency_audit(self.agency, self.owner, 'api_key.regenerated', {})
        timeline = build_audit_timeline(
            list(CRMAgencyAuditLog.objects.filter(agency=self.agency).select_related('actor'))
        )
        self.assertEqual(timeline['stats']['total'], 2)
        self.assertGreaterEqual(len(timeline['groups']), 1)
        self.assertEqual(timeline['groups'][0]['label'], 'امروز')

    def test_agency_updated_summary_uses_persian_labels(self):
        log = log_agency_audit(self.agency, self.owner, 'agency.updated', {'fields': ['name', 'updated_at']})
        meta = describe_audit_log(log)
        self.assertIn('نام آژانس', meta['summary'])
        self.assertNotIn('name', meta['summary'])
        self.assertNotIn('updated_at', meta['summary'])
        chip_values = ' '.join(c['value'] for c in meta['payload_chips'])
        self.assertNotIn('updated_at', chip_values)

    def test_system_actor_label(self):
        log = CRMAgencyAuditLog.objects.create(
            agency=self.agency, actor=None, event='sync.import',
            payload={'contacts': 3}, created_at=timezone.now(),
        )
        meta = describe_audit_log(log)
        self.assertEqual(meta['actor_name'], 'سیستم')
        self.assertTrue(meta['actor_is_system'])
