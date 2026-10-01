from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .cup import ROUNDS, build_bracket, cup_awards, participants
from .models import CopaReySorteo, JornadaRegistro, UserAccess


class BracketTests(SimpleTestCase):
    def setUp(self):
        self.people = [{'manager': f'M{i}', 'division': 'Test', 'guest': False} for i in range(32)]
        self.roster = {'Test': [person['manager'] for person in self.people]}
        self.records = {('Test', journey): SimpleNamespace(cerrada=True, datos={f'M{i}': {'app': 100-i} for i in range(32)}) for _, journeys in ROUNDS for journey in journeys}

    def test_full_bracket_and_prizes_use_only_app(self):
        self.records[('Test', 12)].datos['M1']['q'] = 999
        bracket = build_bracket(self.people, self.records, self.roster)
        self.assertEqual([len(stage['matches']) for stage in bracket], [16, 8, 4, 2, 1])
        self.assertEqual(bracket[0]['matches'][0]['winner']['manager'], 'M0')
        self.assertEqual(bracket[-1]['matches'][0]['winner']['manager'], 'M0')
        self.assertEqual([row['prize'] for row in bracket[-1]['matches'][0]['rows']], [50, 25])
        self.assertEqual(sum(row['prize'] for stage in bracket for match in stage['matches'] for row in match['rows']), 525)

    def test_open_or_missing_scores_do_not_advance(self):
        self.records[('Test', 13)].cerrada = False
        bracket = build_bracket(self.people, self.records, self.roster)
        self.assertTrue(all(match['winner'] is None for stage in bracket for match in stage['matches']))
        self.assertFalse(any(row['prize'] for stage in bracket for match in stage['matches'] for row in match['rows']))
        self.records[('Test', 13)].cerrada = True
        del self.records[('Test', 13)].datos['M0']['app']
        bracket = build_bracket(self.people, self.records, self.roster)
        self.assertIsNone(bracket[0]['matches'][0]['winner'])

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_general_position_breaks_app_tie(self, _):
        self.records[('Test', 13)].datos['M1']['app'] = 101
        self.records[('Test', 12)].datos['M1']['q'] = 4
        bracket = build_bracket(self.people, self.records, self.roster)
        self.assertEqual(bracket[0]['matches'][0]['winner']['manager'], 'M1')
        self.assertIn('Desempate', bracket[0]['matches'][0]['reason'])

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_equal_general_position_stays_pending(self, _):
        self.records[('Test', 13)].datos['M1']['app'] = 101
        bracket = build_bracket(self.people, self.records, self.roster)
        match = bracket[0]['matches'][0]
        self.assertIsNone(match['winner'])
        self.assertIn('pendiente', match['reason'])
        self.assertFalse(any(row['prize'] for row in match['rows']))

    @patch('core.views.vip_adjustments_for_journey', return_value={})
    def test_guest_replaces_ordinary_slot(self, _):
        roster = {'Primera División': ['Raul C']+[f'A{i}' for i in range(8)]}
        records = {('Primera División', journey): SimpleNamespace(cerrada=True, datos={name:{'app':100-i} for i,name in enumerate(roster['Primera División'])}) for journey in range(1,9)}
        people, missing = participants(records, roster)
        self.assertFalse(missing)
        self.assertEqual(len(people),7)
        self.assertEqual(len({person['manager'] for person in people}),7)


class CupIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('cup_admin', password='Testing123!')
        self.access = UserAccess.objects.create(user=self.user, role='admin', must_change_password=False)
        self.people = [{'manager': f'M{i}', 'division': 'Test', 'guest': False} for i in range(32)]
        self.roster = {'Test':[person['manager'] for person in self.people]}
        self.client.force_login(self.user)

    def test_draw_is_persistent_and_permission_checked(self):
        with patch('core.cup.participants', return_value=(self.people,[])), patch('core.views.active_league_managers', return_value=self.roster):
            self.client.post('/torneos/copa-del-rey/')
            original = CopaReySorteo.objects.get(season=2026).participantes
            self.client.post('/torneos/copa-del-rey/')
            self.assertEqual(CopaReySorteo.objects.get(season=2026).participantes, original)
            self.assertEqual(len(original), 32)
            self.assertEqual(len({p['manager'] for p in original}),32)
            self.assertEqual(self.client.get('/torneos/copa-del-rey/').status_code,200)
        CopaReySorteo.objects.all().delete()
        self.access.role='viewer'
        self.access.save()
        with patch('core.cup.participants', return_value=(self.people,[])):
            self.client.post('/torneos/copa-del-rey/')
        self.assertFalse(CopaReySorteo.objects.exists())

    def test_awards_reach_general_and_round_and_reopen_removes_them(self):
        CopaReySorteo.objects.create(season=2026,participantes=self.people,creado_por=self.user)
        for journey in [12,13]:
            JornadaRegistro.objects.create(user_access=self.access,division='Test',season=2026,jornada=journey,cerrada=True,datos={f'M{i}':{'app':100-i} for i in range(32)})
        with patch('core.views.active_league_managers', return_value=self.roster):
            awards=cup_awards(2026)
            self.assertEqual(awards[(13,'Test','M0')],15)
            round_data=self.client.get('/api/estadisticas/2026/13/?division=Test').json()
            winner=next(row for row in round_data['rows'] if row['manager']=='M0')
            self.assertEqual((winner['app'],winner['cup'],winner['total']),(100,15,115))
            general=self.client.get('/api/estadisticas/2026/13/?division=Test&mode=general').json()
            winner=next(row for row in general['rows'] if row['manager']=='M0')
            self.assertEqual(winner['total'],215)
            self.assertEqual(self.client.get('/api/jornada/2026/13/?division=Test').json()['cup_prizes']['M0'],15)
            JornadaRegistro.objects.filter(jornada=13).update(cerrada=False)
            self.assertEqual(cup_awards(2026),{})
