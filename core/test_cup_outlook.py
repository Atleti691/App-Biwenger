from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from .cup import qualification_outlook
from .models import UserAccess


@patch('core.views.vip_adjustments_for_journey', return_value={})
class CupOutlookTests(SimpleTestCase):
    def setUp(self):
        self.roster = {'Test': list('ABCDEFG')}
        self.records = {('Test', number): SimpleNamespace(cerrada=True,
            datos={name: {'app': '82', 'q': '', 'p': '0'} for name in 'ABCDEFG'})
            for number in range(1, 8)}
        self.records[('Test', 7)].datos['A']['app'] = '102'
        self.records[('Test', 7)].datos['G']['app'] = '62'

    def test_mean_gap_and_scenario_not_probability(self, _):
        division = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(division['average'], 82)
        self.assertEqual(division['remaining'], 1)
        self.assertEqual(division['sample_count'], 7)
        outsider = next(p for p in division['players'] if p['manager'] == 'G')
        self.assertEqual(outsider['gap'], 20)
        self.assertAlmostEqual(outsider['individual_average'], 554 / 7)
        self.assertAlmostEqual(outsider['reference_percent'], 20 / (554 / 7) * 100)
        self.assertAlmostEqual(outsider['projected_total'], 554 + 554 / 7, places=5)
        self.assertFalse(outsider['projected_inside'])
        self.assertEqual(outsider['needed_if_cutoff_average'], 103)
        self.assertNotIn('probability', outsider)

    def test_guest_does_not_consume_ordinary_slot(self, _):
        roster = {'Primera División': ['Raul C'] + list('ABCDEFG')}
        records = {('Primera División', 1): SimpleNamespace(cerrada=True,
            datos={name: {'app': str(100-index)} for index, name in enumerate(roster['Primera División'])})}
        division = qualification_outlook(records, roster)[0]
        self.assertEqual(division['cutoff'], 'F')
        self.assertEqual(division['cutoff_position'], 7)
        guest = division['players'][0]
        self.assertTrue(guest['guest'])
        self.assertFalse(guest['inside'])

    def test_missing_scores_exclude_entire_sample_not_zero(self, _):
        self.records[('Test', 7)].datos['A']['app'] = ''
        division = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(division['incomplete'], [7])
        self.assertEqual(division['sample_count'], 6)
        self.assertTrue(all('Faltan datos' in p['status'] for p in division['players']))
        self.assertEqual(next(p for p in division['players'] if p['manager'] == 'A')['individual_count'], 6)

    def test_net_points_postponed_and_open_excluded(self, vip):
        self.records = {('Test', 1): SimpleNamespace(cerrada=True,
            datos={name: {'app': '0'} for name in 'ABCDEFG'}),
            ('Test', 101): SimpleNamespace(cerrada=True,
            datos={name: {'app': '0', 'q': '2', 'p': '1', 'penalty': '2'} for name in 'ABCDEFG'}),
            ('Test', 8): SimpleNamespace(cerrada=False, datos={'A': {'app': '9999'}}),
            ('Test', 9): SimpleNamespace(cerrada=True, datos={'A': {'app': '9999'}})}
        vip.side_effect = lambda number: {('Test', name): 5 for name in 'ABCDEFG'} if number == 101 else {}
        division = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(division['average'], 23)
        self.assertEqual(division['sample'][0]['number'], 1)
        self.assertEqual(division['sample_count'], 1)
        self.assertEqual(division['players'][0]['total'], 23)

    def test_no_data_and_closed_cutoff(self, _):
        self.assertIsNone(qualification_outlook({}, self.roster)[0]['average'])
        self.records[('Test', 8)] = SimpleNamespace(cerrada=True,
            datos={name: {'app': '0'} for name in 'ABCDEFG'})
        division = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(division['remaining'], 0)
        self.assertTrue(all(p['needed_if_cutoff_average'] is None for p in division['players']))

    def test_ap_parts_share_denominator_and_update_provisional_mean(self, _):
        before = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(before['postponed_pending'], [101, 106])
        for number, value in [(101, 10), (106, 30)]:
            self.records[('Test', number)] = SimpleNamespace(cerrada=True,
                datos={name: {'app': str(value)} for name in 'ABCDEFG'})
        after = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(after['postponed_pending'], [])
        self.assertEqual(after['sample_count'], 7)
        self.assertAlmostEqual(after['average'], 82 + 40 / 7)
        player = next(p for p in after['players'] if p['manager'] == 'G')
        self.assertEqual(player['individual_count'], 7)
        self.assertEqual(player['total'], 594)
        self.assertAlmostEqual(player['individual_average'], 594 / 7)
        self.assertEqual(after['remaining'], 1)

    def test_open_postponed_not_counted_and_zero_is_a_valid_sample(self, _):
        self.records[('Test', 101)] = SimpleNamespace(cerrada=False, datos={'A': {'app': '99999'}})
        self.records[('Test', 2)].datos['G']['app'] = '0'
        division = qualification_outlook(self.records, self.roster)[0]
        player = next(p for p in division['players'] if p['manager'] == 'G')
        self.assertEqual(player['individual_count'], 7)
        self.assertIn(101, division['postponed_pending'])
        self.assertLess(player['total'], 1000)

    def test_tie_at_projected_boundary_is_not_a_decided_place(self, _):
        self.records[('Test', 7)].datos['G']['app'] = '82'
        division = qualification_outlook(self.records, self.roster)[0]
        player = next(p for p in division['players'] if p['manager'] == 'G')
        self.assertTrue(player['boundary_tie'])
        self.assertIn('Empate', player['status'])

    def test_margin_index_is_bounded_not_probability(self, _):
        self.records[('Test', 7)].datos['G']['app'] = '-200'
        division = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(next(p for p in division['players'] if p['manager'] == 'G')['margin_index'], 0)
        self.assertTrue(all(p['margin_index'] is None or 0 <= p['margin_index'] <= 100 for p in division['players']))


class CupOutlookPageTests(TestCase):
    def test_viewer_can_read_without_creating_draw(self):
        user = get_user_model().objects.create_user('outlook-viewer')
        UserAccess.objects.create(user=user, role='viewer', must_change_password=False)
        self.client.force_login(user)
        response = self.client.get('/torneos/copa-del-rey/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Camino a la Copa')
        self.assertContains(response, 'No es una probabilidad')
        self.assertContains(response, 'Su media')
        self.assertContains(response, 'J1 + 1AP y J6 + 6AP')
