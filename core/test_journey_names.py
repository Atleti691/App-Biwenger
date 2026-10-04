import importlib
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase

from .journeys import journey_label, ordered_journeys
from .models import ContactoManager, CopaReySorteo, JornadaRegistro, ManagerLiga, PartidoVIP, UserAccess, VotoPartidoVIP
from .views import manager_account
from django.utils import timezone


class JourneyLabelTests(SimpleTestCase):
    def test_ap_order_and_names(self):
        numbers = ordered_journeys()
        self.assertEqual(numbers[:8], [1, 2, 101, 3, 4, 5, 106, 6])
        self.assertEqual(len(numbers), 40)
        self.assertEqual(journey_label(101), 'Jornada 1AP')
        self.assertEqual(journey_label(106), 'Jornada 6AP')
        self.assertEqual(journey_label(2), 'Jornada 2')

    def test_statistics_selector_keeps_internal_ids(self):
        html = render_to_string('statistics.html', {'divisions': [], 'jornadas': ordered_journeys()})
        self.assertIn('<option value="101">Jornada 1AP</option>', html)
        self.assertIn('<option value="106">Jornada 6AP</option>', html)
        self.assertLess(html.index('value="2"'), html.index('value="101"'))
        self.assertLess(html.index('value="101"'), html.index('value="3"'))


class DonateloRenameTests(TestCase):
    def test_rename_preserves_journeys_votes_contacts_and_login(self):
        user = get_user_model().objects.create_user('eMCasa', password='TestPassword123!')
        access = UserAccess.objects.create(user=user, role='viewer')
        ManagerLiga.objects.create(season=2099, division='Segunda División', manager='eMCasa')
        contact = ContactoManager.objects.create(division='Segunda División', manager='eMCasa', email='example@example.com', provincia='Madrid')
        record = JornadaRegistro.objects.create(user_access=access, season=2099, division='Segunda División', jornada=101,
            datos={'eMCasa': {'app': '32', 'q': '4', 'p': '1', 'clauses': [], 'penalty': '2', 'money': '100.000 €'},
                   'Otro': {'app': '10', 'clauses': [{'to': 'eMCasa', 'value': 1000000}]}})
        match = PartidoVIP.objects.create(titulo='Prueba', equipo_local='A', equipo_visitante='B', fecha_cierre=timezone.now())
        vote = VotoPartidoVIP.objects.create(partido=match, division='Segunda División', manager='eMCasa', posicionamiento='local', pronostico_goles='1')
        other = VotoPartidoVIP.objects.create(partido=match, division='Segunda División', manager='Otro', posicionamiento='local', pronostico_goles='1', penalizaciones_objetivo={'eMCasa': 25}, objetivo_penalizacion='eMCasa')
        draw = CopaReySorteo.objects.create(season=2099, participantes=[{'division': 'Segunda División', 'manager': 'eMCasa'}])
        migration = importlib.import_module('core.migrations.0022_rename_emcasa_donatelo')
        migration.rename_manager(apps, SimpleNamespace(connection=connection))
        record.refresh_from_db();contact.refresh_from_db();vote.refresh_from_db();other.refresh_from_db();draw.refresh_from_db();user.refresh_from_db()
        self.assertEqual(record.jornada, 101)
        self.assertEqual(record.datos['Donatelo']['app'], '32')
        self.assertEqual(record.datos['Donatelo']['money'], '100.000 €')
        self.assertEqual(record.datos['Otro']['clauses'][0]['to'], 'Donatelo')
        self.assertEqual(contact.manager, 'Donatelo')
        self.assertEqual(vote.manager, 'Donatelo')
        self.assertEqual(other.penalizaciones_objetivo, {'Donatelo': 25})
        self.assertEqual(other.objetivo_penalizacion, 'Donatelo')
        self.assertEqual(draw.participantes[0]['manager'], 'Donatelo')
        self.assertEqual(user.username, 'eMCasa')
        self.assertTrue(user.check_password('TestPassword123!'))
        self.assertEqual(manager_account('Donatelo'), user)
        # Safe to run again without shifting or duplicating data.
        migration.rename_manager(apps, SimpleNamespace(connection=connection))
        self.assertEqual(ManagerLiga.objects.filter(season=2099, manager='Donatelo').count(), 1)

    def test_json_collision_is_not_overwritten(self):
        migration = importlib.import_module('core.migrations.0022_rename_emcasa_donatelo')
        with self.assertRaises(RuntimeError):
            migration.rename_json({'eMCasa': {'app': 10}, 'Donatelo': {'app': 20}})
