from django.test import SimpleTestCase

from workspace.services.contact_nba import build_contact_workflow, has_no_preferences


class _C:
    def __init__(self, **kwargs):
        defaults = dict(
            customer_type='خریدار',
            property_type='',
            budget_min=None,
            budget_max=None,
            deposit_min=None,
            deposit_max=None,
            rent_min=None,
            rent_max=None,
            min_area=None,
            max_area=None,
            rooms_min=None,
            rooms_max=None,
            rooms='',
            year_min=None,
            year_max=None,
            floor_min=None,
            floor_max=None,
            want_parking=False,
            want_storage=False,
            want_elevator=False,
            areas='',
            builder_buy_property_types='',
            builder_buy_budget_min=None,
            builder_buy_budget_max=None,
            builder_buy_min_area=None,
            builder_buy_max_area=None,
            builder_buy_areas='',
            phone='09120000000',
            next_follow_up=None,
        )
        defaults.update(kwargs)
        self.__dict__.update(defaults)


class _Deal:
    def __init__(self, pk, stage, title='معامله', closed_at=None):
        self.pk = pk
        self.stage = stage
        self.title = title
        self.closed_at = closed_at


class ContactNbaTests(SimpleTestCase):
    def test_empty_prefs_detected(self):
        self.assertTrue(has_no_preferences(_C()))
        self.assertFalse(has_no_preferences(_C(areas='نیاوران', budget_max=10)))

    def test_overdue_beats_empty_prefs_and_matches(self):
        data = build_contact_workflow(
            customer=_C(),
            follow_up_state='overdue',
            activities=[],
            match_data={'eligible': True, 'total_count': 4},
            property_links=[],
            linked_listings=[],
            visits=['v'],
            deals=[],
            can_edit=True,
        )
        self.assertEqual(data['nba']['key'], 'followup')

    def test_fresh_contact_cta_is_register_need(self):
        data = build_contact_workflow(
            customer=_C(),
            follow_up_state='none',
            activities=[],
            match_data={'eligible': False},
            property_links=[],
            linked_listings=[],
            visits=[],
            deals=[],
            can_edit=True,
        )
        self.assertEqual(data['nba']['key'], 'need')
        self.assertEqual(data['nba']['cta'], 'ثبت نیاز')

    def test_matches_before_linked_send(self):
        link = type('L', (), {'role': 'پیشنهادی'})()
        data = build_contact_workflow(
            customer=_C(areas='فرشته', budget_min=1),
            follow_up_state='none',
            activities=[],
            match_data={'eligible': True, 'total_count': 3},
            property_links=[link],
            linked_listings=[],
            visits=[],
            deals=[],
            can_edit=True,
        )
        self.assertEqual(data['nba']['key'], 'matches')
        self.assertEqual(data['nba']['tab'], 'matches')

    def test_send_when_suggested_linked_and_no_live_matches(self):
        link = type('L', (), {'role': 'پیشنهادی'})()
        data = build_contact_workflow(
            customer=_C(areas='فرشته', budget_min=1),
            follow_up_state='none',
            activities=[],
            match_data={'eligible': True, 'total_count': 0},
            property_links=[link],
            linked_listings=[],
            visits=[],
            deals=[],
            can_edit=True,
        )
        self.assertEqual(data['nba']['key'], 'send')
        self.assertEqual(data['nba']['tab'], 'properties')

    def test_overdue_uses_log_call_when_phone(self):
        data = build_contact_workflow(
            customer=_C(areas='فرشته', budget_min=1),
            follow_up_state='overdue',
            activities=[],
            match_data={'eligible': False},
            property_links=[],
            linked_listings=[],
            visits=[],
            deals=[],
            can_edit=True,
        )
        self.assertEqual(data['nba']['form_action'], 'log_call')

    def test_visit_without_active_deal(self):
        data = build_contact_workflow(
            customer=_C(areas='فرشته', budget_min=1),
            follow_up_state='none',
            activities=[],
            match_data={'eligible': False},
            property_links=[],
            linked_listings=[],
            visits=['v'],
            deals=[_Deal(1, 'بسته‌شده')],
            can_edit=True,
        )
        self.assertEqual(data['nba']['key'], 'deal_start')

    def test_active_deal_before_live_matches(self):
        data = build_contact_workflow(
            customer=_C(areas='فرشته', budget_min=1),
            follow_up_state='none',
            activities=[],
            match_data={'eligible': True, 'total_count': 3},
            property_links=[],
            linked_listings=[],
            visits=[],
            deals=[_Deal(9, 'مذاکره', 'واحد نیاوران')],
            can_edit=True,
        )
        self.assertEqual(data['nba']['key'], 'deal_open')
        data = build_contact_workflow(
            customer=_C(areas='فرشته', budget_min=1),
            follow_up_state='none',
            activities=[],
            match_data={'eligible': False},
            property_links=[],
            linked_listings=[],
            visits=[],
            deals=[_Deal(9, 'مذاکره', 'واحد نیاوران')],
            can_edit=True,
        )
        self.assertEqual(data['nba']['key'], 'deal_open')
        self.assertIn('/9/', data['nba']['url'])

    def test_upcoming_followup_has_no_fallback_nba(self):
        data = build_contact_workflow(
            customer=_C(areas='فرشته', budget_min=1),
            follow_up_state='upcoming',
            activities=[],
            match_data={'eligible': False},
            property_links=[],
            linked_listings=[],
            visits=[],
            deals=[],
            can_edit=True,
        )
        self.assertIsNone(data['nba'])
        data = build_contact_workflow(
            customer=_C(),
            follow_up_state='overdue',
            activities=[],
            match_data={'eligible': True, 'total_count': 2},
            property_links=[],
            linked_listings=[],
            visits=[],
            deals=[],
            can_edit=False,
        )
        self.assertEqual(data['nba']['key'], 'matches')
