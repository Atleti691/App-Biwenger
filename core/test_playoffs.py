from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .playoffs import net_match, promotion_competition, promotion_place, qualification, round_robin, title_competition


class PlayoffRulesTests(SimpleTestCase):
    def test_seven_rounds_all_pairs_once_and_one_bye(self):
        names = [f'M{i}' for i in range(7)]
        rounds = round_robin(names)
        self.assertEqual([stage['journey'] for stage in rounds], list(range(26, 33)))
        pairs = [frozenset(pair) for stage in rounds for pair in stage['pairs']]
        self.assertEqual(len(pairs), 21)
        self.assertEqual(len(set(pairs)), 21)
        self.assertEqual(sorted(stage['bye'] for stage in rounds), names)
        for stage in rounds:
            participants = [name for pair in stage['pairs'] for name in pair]
            self.assertEqual(len(set(participants)), 6)
            self.assertNotIn(stage['bye'], participants)

    @patch('core.views.vip_adjustments_for_journey', return_value={('Test', 'B'): 10})
    def test_total_net_includes_bonuses_penalties_vip_and_cup(self, _):
        roster = {'Test': ['A', 'B']}
        records = {('Test', 25): SimpleNamespace(cerrada=True, datos={
            'A': {'app': 100, 'penalty': 20}, 'B': {'app': 70, 'q': 1, 'p': 1}})}
        match = net_match(records, roster, 'Test', ['A', 'B'], (25,), {(25, 'Test', 'B'): 15}, metric='total')
        self.assertEqual(match['scores'], [80, 110])
        self.assertEqual(match['winner'], 'B')
        app_match = net_match(records, roster, 'Test', ['A', 'B'], (25,), metric='app')
        self.assertEqual(app_match['scores'], [100, 70])
        self.assertEqual(app_match['winner'], 'A')
        records[('Test', 25)].cerrada = False
        self.assertIsNone(net_match(records, roster, 'Test', ['A', 'B'], (25,))['winner'])

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_zero_is_valid_and_general_breaks_tie(self, _):
        roster = {'Test': ['A', 'B']}
        records = {('Test', 24): SimpleNamespace(cerrada=True, datos={'A': {'app': 1}, 'B': {'app': 2}}),
                   ('Test', 25): SimpleNamespace(cerrada=True, datos={'A': {'app': 0}, 'B': {'app': 0}})}
        match = net_match(records, roster, 'Test', ['A', 'B'], (25,))
        self.assertEqual(match['scores'], [0, 0])
        self.assertEqual(match['winner'], 'B')
        records[('Test', 25)].datos['B']['app'] = ''
        self.assertIsNone(net_match(records, roster, 'Test', ['A', 'B'], (25,))['winner'])

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_qualification_stops_at_24(self, _):
        names = [f'M{i}' for i in range(9)]
        roster = {'Test': names}
        records = {('Test', j): SimpleNamespace(cerrada=True, datos={name: {'app': 100-i} for i, name in enumerate(names)}) for j in range(1, 26)}
        records[('Test', 25)].datos['M8']['app'] = 99999
        rows, ready = qualification(records, roster, 'Test', 24)
        self.assertTrue(ready)
        self.assertEqual([row['manager'] for row in rows[:8]], names[:8])
        records[('Test', 24)].cerrada = False
        self.assertFalse(qualification(records, roster, 'Test', 24)[1])

    def full_season(self, division='Segunda División'):
        names = [f'M{i}' for i in range(9)]
        roster = {division: names}
        records = {(division, j): SimpleNamespace(cerrada=True, datos={name: {'app': 100-i} for i, name in enumerate(names)}) for j in range(1, 38)}
        return records, roster

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_full_title_and_four_distinct_promotions(self, _):
        records, roster = self.full_season()
        title = title_competition(records, roster, 'Segunda División')
        self.assertEqual(title['playin']['winner'], 'M6')
        self.assertEqual(title['qualified'], [f'M{i}' for i in range(7)])
        self.assertTrue(title['groups_ready'])
        self.assertEqual([row['played'] for row in title['group_table']], [6]*7)
        self.assertEqual([row['points'] for row in title['group_table']], [18, 15, 12, 9, 6, 3, 0])
        self.assertEqual([match['managers'] for match in title['final_four']], [['M0', 'M3'], ['M1', 'M2']])
        self.assertEqual(title['champion'], 'M0')
        self.assertEqual(title['runner_up'], 'M1')
        self.assertEqual(title['third_place']['winner'], 'M2')
        promotion = promotion_competition(records, roster, title)
        self.assertEqual(promotion['title_promoted'], 'M2')
        self.assertEqual([match['managers'] for match in promotion['semifinals']], [['M3', 'M6'], ['M4', 'M5']])
        self.assertEqual(promotion['promoted'], ['M0', 'M1', 'M2', 'M3'])

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_draws_give_one_each_and_byes_nothing(self, _):
        records, roster = self.full_season('Test')
        for j in range(26, 33):
            for values in records[('Test', j)].datos.values():
                values['app'] = 50
        title = title_competition(records, roster, 'Test')
        self.assertEqual([row['points'] for row in title['group_table']], [6]*7)
        self.assertEqual([row['drawn'] for row in title['group_table']], [6]*7)
        self.assertTrue(title['groups_ready'])

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_open_group_round_blocks_final_four_and_open_final_blocks_promotions(self, _):
        records, roster = self.full_season()
        records[('Segunda División', 32)].cerrada = False
        title = title_competition(records, roster, 'Segunda División')
        self.assertFalse(title['groups_ready'])
        self.assertEqual(title['final_four'], [])
        records[('Segunda División', 32)].cerrada = True
        records[('Segunda División', 36)].cerrada = False
        title = title_competition(records, roster, 'Segunda División')
        self.assertIsNone(title['champion'])
        self.assertEqual(promotion_competition(records, roster, title)['promoted'], [])

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_knockout_scores_ignore_all_bonuses(self, _):
        records, roster = self.full_season()
        records[('Segunda División', 36)].datos['M1']['q'] = 10000
        title = title_competition(records, roster, 'Segunda División')
        self.assertEqual(title['title_final']['scores'], [100, 99])
        self.assertEqual(title['champion'], 'M0')

    def test_title_promotion_fallbacks(self):
        ranking = [{'manager': name} for name in ['A', 'B', 'C', 'D']]
        self.assertEqual(promotion_place('D', 'C', ranking, ['A', 'B']), 'D')
        self.assertEqual(promotion_place('A', 'D', ranking, ['A', 'B']), 'D')
        self.assertEqual(promotion_place('A', 'B', ranking, ['A', 'B']), 'C')


class PlayoffPageTests(TestCase):
    def test_login_required_and_read_only_user_can_view(self):
        url = reverse('league_playoffs')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(get_user_model().objects.create_user('playoff_viewer'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'J34')
        self.assertContains(response, 'J37')
        self.assertContains(response, 'solo puntos APP')
        self.assertContains(response, '3 por victoria')
