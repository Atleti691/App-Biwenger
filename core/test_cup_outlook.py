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
        self.assertAlmostEqual(outsider['reference_percent'], 20 / 82 * 100)
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

    def test_net_points_postponed_and_open_excluded(self, vip):
        self.records = {('Test', 101): SimpleNamespace(cerrada=True,
            datos={name: {'app': '0', 'q': '2', 'p': '1', 'penalty': '2'} for name in 'ABCDEFG'}),
            ('Test', 8): SimpleNamespace(cerrada=False, datos={'A': {'app': '9999'}}),
            ('Test', 9): SimpleNamespace(cerrada=True, datos={'A': {'app': '9999'}})}
        vip.return_value = {('Test', name): 5 for name in 'ABCDEFG'}
        division = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(division['average'], 23)
        self.assertEqual(division['sample'][0]['number'], 101)
        self.assertEqual(division['players'][0]['total'], 23)

    def test_no_data_and_closed_cutoff(self, _):
        self.assertIsNone(qualification_outlook({}, self.roster)[0]['average'])
        self.records[('Test', 8)] = SimpleNamespace(cerrada=True,
            datos={name: {'app': '0'} for name in 'ABCDEFG'})
        division = qualification_outlook(self.records, self.roster)[0]
        self.assertEqual(division['remaining'], 0)
        self.assertTrue(all(p['needed_if_cutoff_average'] is None for p in division['players']))


class CupOutlookPageTests(TestCase):
    def test_viewer_can_read_without_creating_draw(self):
        user = get_user_model().objects.create_user('outlook-viewer')
        UserAccess.objects.create(user=user, role='viewer', must_change_password=False)
        self.client.force_login(user)
        response = self.client.get('/torneos/copa-del-rey/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Camino a la Copa')
        self.assertContains(response, 'no es probabilidad', count=0)
        self.assertContains(response, 'No hay un máximo de puntos')
