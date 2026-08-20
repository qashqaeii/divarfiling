from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from workspace.services.home_nba import build_home_nba


def _build(user, **kwargs):
    defaults = dict(
        crm_nav_counts={'today_overdue': 0, 'today_due': 0},
        datasets_qs=MagicMock(),
        has_bot_license=False,
        contact_count=0,
        dataset_count=0,
    )
    defaults.update(kwargs)
    with patch('workspace.services.home_nba.reverse', side_effect=lambda name, **kw: f'/{name}'):
        with patch('workspace.services.home_nba.can_view_team_inbox', return_value=False):
            return build_home_nba(user, **defaults)


class HomeNbaTests(SimpleTestCase):
    def test_zero_counts_yield_no_cards(self):
        self.assertEqual(_build(MagicMock()), [])

    def test_overdue_before_today(self):
        cards = _build(
            MagicMock(),
            crm_nav_counts={'today_overdue': 2, 'today_due': 3},
        )
        self.assertEqual([c['key'] for c in cards], ['overdue', 'today'])
        self.assertEqual(cards[0]['count'], 2)
        self.assertEqual(cards[0]['cta'], 'شروع پیگیری')

    def test_limit_three_drops_lower_priority(self):
        inbox_qs = MagicMock()
        inbox_qs.count.return_value = 4
        match_qs = MagicMock()
        match_qs.values.return_value.distinct.return_value.count.return_value = 5
        with patch('workspace.services.home_nba.reverse', side_effect=lambda name, **kw: f'/{name}'):
            with patch('workspace.services.home_nba.can_view_team_inbox', return_value=True):
                with patch('workspace.services.home_nba.team_inbox_qs', return_value=inbox_qs):
                    with patch('workspace.services.home_nba._match_opportunity', return_value={'key': 'matches'}):
                        cards = build_home_nba(
                            MagicMock(),
                            crm_nav_counts={'today_overdue': 1, 'today_due': 2},
                            datasets_qs=MagicMock(),
                            has_bot_license=True,
                            contact_count=9,
                            dataset_count=3,
                        )
        self.assertEqual([c['key'] for c in cards], ['overdue', 'agency_inbox', 'today'])
        self.assertEqual(len(cards), 3)

    def test_skips_new_filing_without_datasets(self):
        datasets_qs = MagicMock()
        cards = _build(
            MagicMock(),
            has_bot_license=True,
            dataset_count=0,
            datasets_qs=datasets_qs,
        )
        datasets_qs.filter.assert_not_called()
        self.assertEqual(cards, [])

    def test_single_match_deep_links_to_contact(self):
        qs = MagicMock()
        qs.values.return_value.distinct.return_value.count.return_value = 1
        qs.values_list.return_value.first.return_value = 42
        with patch('workspace.services.home_nba.reverse', side_effect=lambda name, args=None, kwargs=None, **extra: f'/{name}/{(kwargs or {}).get("customer_id", "")}'):
            with patch('workspace.services.home_nba.PropertyMatchAlert.objects.filter', return_value=qs):
                from workspace.services.home_nba import _match_opportunity
                card = _match_opportunity(MagicMock())
        self.assertEqual(card['count'], 1)
        self.assertIn('tab=matches', card['url'])
        self.assertIn('/workspace:crm_detail/42', card['url'])
        self.assertEqual(card['cta'], 'مشاهده پیشنهادها')

    def test_multi_match_goes_to_contacts_queue(self):
        qs = MagicMock()
        qs.values.return_value.distinct.return_value.count.return_value = 7
        with patch('workspace.services.home_nba.reverse', side_effect=lambda name, **kw: f'/{name}'):
            with patch('workspace.services.home_nba.PropertyMatchAlert.objects.filter', return_value=qs):
                from workspace.services.home_nba import _match_opportunity
                card = _match_opportunity(MagicMock())
        self.assertEqual(card['count'], 7)
        self.assertIn('match_alerts=1', card['url'])
        self.assertIn('/workspace:crm_contacts', card['url'])
        self.assertNotIn('crm_detail', card['url'])
        qs.values_list.assert_not_called()
