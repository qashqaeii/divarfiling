"""تست اقدام بعدی، پیگیری و timeline معامله."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMDeal, CRMDealFollowUp, Customer
from workspace.services.crm_deals import create_deal
from workspace.services.crm_deal_followup import (
    clear_next_action,
    complete_next_action,
    create_follow_up,
    get_deal_timeline,
    is_next_action_overdue,
    serialize_next_action,
    set_next_action,
)
from workspace.services.crm_deal_stages import get_user_deal_stages
from workspace.services.crm_scope import deal_for_user

User = get_user_model()


class CRMDealFollowUpTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121111111', password='x', phone='09121111111')
        self.other = User.objects.create_user(username='09122222222', password='x', phone='09122222222')
        self.customer = Customer.objects.create(user=self.user, name='رضایی')
        self.deal = create_deal(self.user, self.customer, title='خرید جردن')

    def test_create_deal_with_next_action(self):
        at = timezone.now() + timedelta(hours=3)
        set_next_action(self.deal, action_type='call', action_at=at, note='پیگیری بازدید')
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.next_action_type, 'call')
        self.assertEqual(self.deal.next_action_note, 'پیگیری بازدید')
        data = serialize_next_action(self.deal)
        self.assertFalse(data['is_overdue'])

    def test_overdue_next_action(self):
        past = timezone.now() - timedelta(hours=2)
        set_next_action(self.deal, action_type='call', action_at=past, save=True)
        self.assertTrue(is_next_action_overdue(self.deal))

    def test_clear_next_action(self):
        set_next_action(self.deal, action_type='call', action_at=timezone.now(), save=True)
        clear_next_action(self.deal, save=True)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.next_action_type, '')
        self.assertIsNone(self.deal.next_action_at)

    def test_create_follow_up(self):
        create_follow_up(self.deal, self.user, follow_up_type='call', note='تماس گرفته شد')
        self.assertEqual(self.deal.follow_ups.count(), 1)
        self.assertEqual(CRMDealFollowUp.objects.filter(deal=self.deal).count(), 1)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.next_action_type, '')

    def test_parse_follow_up_payload_ignores_type(self):
        from workspace.services.crm_deal_followup import _follow_up_next_action_payload, parse_next_action_payload

        payload = {
            'type': 'call',
            'note': 'تماس گرفته شد',
            'next_action_type': '',
            'next_action_at': '',
            'next_action_note': '',
        }
        na = parse_next_action_payload(_follow_up_next_action_payload(payload))
        self.assertEqual(na['action_type'], '')
        self.assertIsNone(na['action_at'])

    def test_follow_up_belongs_to_deal(self):
        fu = create_follow_up(self.deal, self.user, follow_up_type='visit', note='بازدید OK')
        self.assertEqual(fu.deal_id, self.deal.pk)

    def test_cross_user_access_denied(self):
        self.assertIsNone(deal_for_user(self.other, self.deal.pk))

    def test_follow_up_in_timeline(self):
        create_follow_up(self.deal, self.user, follow_up_type='message', note='واتساپ فرستاده شد')
        items = get_deal_timeline(self.deal, limit=20)['items']
        kinds = [i['kind'] for i in items]
        self.assertIn('follow_up', kinds)
        self.assertIn('deal_created', kinds)

    def test_complete_next_action_creates_follow_up(self):
        set_next_action(self.deal, action_type='call', action_at=timezone.now(), note='تماس', save=True)
        complete_next_action(self.deal, self.user, result_note='انجام شد')
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.next_action_type, '')
        self.assertEqual(self.deal.follow_ups.count(), 1)

    def test_create_deal_without_finance_fields_still_has_defaults(self):
        deal = create_deal(self.user, self.customer, title='ساده', value=1_000_000_000)
        self.assertIsNotNone(deal.commission_rate)
        self.assertTrue(deal.deal_kind in ('sale', 'rent'))

    def test_stage_in_user_pipeline(self):
        stages = get_user_deal_stages(self.user)
        self.assertIn(self.deal.stage, stages)

    def test_follow_up_with_explicit_next_action(self):
        at = timezone.now() + timedelta(hours=2)
        create_follow_up(
            self.deal,
            self.user,
            follow_up_type='call',
            note='تماس',
            next_action_type='visit',
            next_action_at=at,
            next_action_note='بازدید',
        )
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.next_action_type, 'visit')
        self.assertEqual(self.deal.next_action_note, 'بازدید')
