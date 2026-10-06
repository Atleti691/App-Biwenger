import importlib
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from types import SimpleNamespace
from .models import CambioRegistro, Clausula, JornadaRegistro, UserAccess


class ClearSecondJ1Tests(TestCase):
    def test_scoped_correction_preserves_scores_and_backup(self):
        user = get_user_model().objects.create_user('test-owner')
        access = UserAccess.objects.create(user=user)
        data = {'Manager': {'app': '42', 'q': '', 'p': '0', 'money': '100.000 €',
                            'penalty': '2', 'clauses': [{'to': 'Other', 'value': 1000000}]}}
        records = [JornadaRegistro.objects.create(user_access=access, season=season,
                    jornada=number, division=division, datos=data, cerrada=True,
                    penalizacion_puntos_clausulas=2)
                   for season, number, division in [(2026, 1, 'Segunda División'),
                       (2026, 2, 'Segunda División'), (2026, 1, 'Primera División'),
                       (2025, 1, 'Segunda División')]]
        target = records[0]
        timestamp = target.updated_at
        Clausula.objects.create(jornada=target, numero=1, jugador='Other', valor_dinero=1000000)
        correction = importlib.import_module('core.migrations.0023_clear_second_division_j1_clauses')
        correction.clear_clauses(apps, SimpleNamespace(connection=connection))
        target.refresh_from_db()
        self.assertEqual(target.datos['Manager'], {'app': '42', 'q': '', 'p': '0',
                                                 'money': '', 'penalty': '0', 'clauses': []})
        self.assertTrue(target.cerrada)
        self.assertEqual(target.updated_at, timestamp)
        self.assertEqual(target.penalizacion_puntos_clausulas, 0)
        self.assertFalse(target.clausulas.exists())
        log = CambioRegistro.objects.get()
        self.assertEqual(log.detalle['clausulas_antes']['Manager']['penalty'], '2')
        self.assertEqual(log.detalle['clausulas_legacy'][0]['valor_dinero'], '1000000.00')
        for record in records[1:]:
            record.refresh_from_db()
            self.assertEqual(record.datos, data)
        correction.clear_clauses(apps, SimpleNamespace(connection=connection))
        self.assertEqual(CambioRegistro.objects.count(), 1)
