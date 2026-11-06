from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from .models import CambioRegistro, CopaReySorteo, JornadaRegistro, UserAccess


class CopaDrawCorrectionTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('Atleti69')
        self.access = UserAccess.objects.create(user=self.actor, role='admin')
        self.people = [{'manager': f'Manager {n}', 'division': 'Primera División', 'guest': n == 0}
                       for n in range(32)]
        self.people[16:20] = [
            {'manager': 'Resalso', 'division': 'Primera RFEF', 'guest': False},
            {'manager': 'Adrianpt260', 'division': 'Segunda División', 'guest': False},
            {'manager': 'Litoscaboalles', 'division': 'Primera RFEF', 'guest': False},
            {'manager': 'Semela', 'division': 'Segunda RFEF', 'guest': False},
        ]
        self.draw = CopaReySorteo.objects.create(season=2026, participantes=self.people, creado_por=self.actor)
        self.correct = import_module('core.migrations.0028_correct_copa_2026_draw').correct_draw
        self.editor = SimpleNamespace(connection=connection)

    def test_only_two_slots_change_and_audit_is_idempotent(self):
        self.correct(apps, self.editor)
        self.correct(apps, self.editor)
        self.draw.refresh_from_db()
        self.assertEqual(self.draw.participantes[17]['manager'], 'Rapido de Bouzas')
        self.assertEqual(self.draw.participantes[19]['manager'], 'A.A. Ponte Preta')
        self.assertEqual([i for i, person in enumerate(self.people) if person != self.draw.participantes[i]], [17, 19])
        audit = CambioRegistro.objects.get(accion='Corregir plazas del sorteo de Copa del Rey')
        self.assertEqual(audit.detalle['participantes_antes'], self.people)

    def test_closed_first_leg_prevents_automatic_substitution(self):
        JornadaRegistro.objects.create(user_access=self.access, season=2026, jornada=12,
            division='Primera RFEF', cerrada=True, datos={'Resalso': {'app': '0'}})
        with self.assertRaisesMessage(RuntimeError, 'puntos de Copa ya cerrados'):
            self.correct(apps, self.editor)
        self.draw.refresh_from_db()
        self.assertEqual(self.draw.participantes, self.people)
        self.assertFalse(CambioRegistro.objects.exists())
