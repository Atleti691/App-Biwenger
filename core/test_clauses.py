import json
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .clause_data import clause_totals, merge_journey_data, normalize_clauses
from .models import CambioRegistro, JornadaRegistro, UserAccess


class ClauseDataTests(SimpleTestCase):
    def test_old_save_preserves_details_and_totals(self):
        old = {'A': {'app': '10', 'clauses': [{'to': 'B', 'value': 1000000}], 'money': '100.000 €', 'penalty': '2'}}
        for row in ({'app': '20'}, {'app': '20', 'clauses': [], 'money': '', 'penalty': '0'}, {'app': '20', 'clauses': [5000000], 'money': '500.000 €', 'penalty': '2'}):
            data = merge_journey_data(old, {'A': row})
            self.assertEqual(data['A']['app'], '20')
            for key in ('clauses', 'money', 'penalty'):
                self.assertEqual(data['A'][key], old['A'][key])

    def test_compact_removal_recalculates_tiers(self):
        clauses = normalize_clauses([{'to': 'A', 'value': 1000000}, {'to': 'B', 'value': 2000000}, {'to': 'C', 'value': 3000000}])
        self.assertEqual(clause_totals(clauses), {'money': '900.000 €', 'penalty': '8'})
        del clauses[0]
        self.assertEqual(clause_totals(clauses), {'money': '500.000 €', 'penalty': '4'})
        self.assertEqual(clause_totals([]), {'money': '0 €', 'penalty': '0'})

    def test_normalization_rejects_invalid_and_accepts_legacy(self):
        self.assertEqual(normalize_clauses([1000, {'by': 'B', 'value': '2000'}, 0]), [{'to': '', 'value': 1000}, {'to': 'B', 'value': 2000}])
        for invalid in ([{'value': -1}], [{'value': 'texto'}], [True], [1.5], [1]*13):
            with self.assertRaises(ValueError):
                normalize_clauses(invalid)


class ClauseSaveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('clause_admin')
        self.access = UserAccess.objects.create(user=self.user, role='admin', must_change_password=False)
        self.client.force_login(self.user)
        self.data = {'A': {'app': '30', 'q': '4', 'p': '2', 'clauses': [{'to': 'B', 'value': 1000000}], 'money': '100.000 €', 'penalty': '2'},
                     'B': {'app': '40', 'q': '0', 'p': '1', 'clauses': [], 'money': '', 'penalty': '0'}}
        self.record = JornadaRegistro.objects.create(user_access=self.access, season=2026, jornada=3, division='Segunda División', datos=deepcopy(self.data))
        self.url = '/api/jornada/2026/3/'

    def post(self, **values):
        return self.client.post(self.url, json.dumps({'division': 'Segunda División', **values}), content_type='application/json')

    def test_duplicate_legacy_save_cannot_erase_clauses(self):
        incoming = deepcopy(self.data)
        del incoming['A']['clauses']
        incoming['A']['app'] = '31'
        self.assertEqual(self.post(datos=incoming).status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.datos['A']['clauses'], self.data['A']['clauses'])
        self.assertEqual(self.record.datos['A']['app'], '31')

    def test_edit_is_persistent_scoped_and_audited(self):
        items = [{'to': 'B', 'value': 2500000}]
        stale = deepcopy(self.data)
        stale['A']['app'] = '999'
        self.assertEqual(self.post(datos=stale, clause_update={'manager': 'A', 'clauses': items}).status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.datos['A']['clauses'], items)
        self.assertEqual(self.record.datos['A']['money'], '250.000 €')
        self.assertEqual(self.record.datos['A']['app'], '30')
        self.assertEqual(self.record.datos['B'], self.data['B'])
        change = CambioRegistro.objects.latest('creado')
        self.assertEqual(change.detalle['clausulas_antes']['A']['clauses'], self.data['A']['clauses'])
        self.assertEqual(change.detalle['clausulas_despues']['A']['clauses'], items)
        response = self.client.get(self.url, {'division': 'Segunda División'})
        self.assertEqual(response.json()['datos']['A']['clauses'], items)

    def test_explicit_removal_and_invalid_update(self):
        self.assertEqual(self.post(clause_update={'manager': 'A', 'clauses': []}).status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.datos['A']['money'], '0 €')
        self.assertEqual(self.record.datos['A']['penalty'], '0')
        self.assertEqual(self.record.datos['B'], self.data['B'])
        self.assertEqual(self.post(clause_update={'manager': 'A', 'clauses': [{'value': -50}]}).status_code, 400)

    def test_closed_record_cannot_be_edited_or_silently_reopened(self):
        self.record.cerrada = True
        self.record.save()
        self.assertEqual(self.post(clause_update={'manager': 'A', 'clauses': []}).status_code, 403)
        self.record.refresh_from_db()
        self.assertTrue(self.record.cerrada)
        self.assertEqual(self.record.datos, self.data)

    def test_edit_uses_latest_record_not_older_account_copy(self):
        other = get_user_model().objects.create_user('other_clause_admin')
        access = UserAccess.objects.create(user=other, role='admin')
        newest = deepcopy(self.data)
        newest['B']['app'] = '88'
        record = JornadaRegistro.objects.create(user_access=access, season=2026, jornada=3, division='Segunda División', datos=newest)
        self.assertEqual(self.post(clause_update={'manager': 'A', 'clauses': [{'to': 'B', 'value': 500000}]}).status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.datos['B']['app'], '88')
        self.assertEqual(record.datos['A']['money'], '50.000 €')
        self.assertEqual(JornadaRegistro.objects.filter(jornada=3).count(), 2)

    def test_read_only_user_cannot_edit(self):
        self.access.role = 'viewer'
        self.access.save()
        self.assertEqual(self.post(clause_update={'manager': 'A', 'clauses': []}).status_code, 403)
