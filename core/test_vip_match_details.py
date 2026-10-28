import importlib
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PartidoVIP, UserAccess, VotoPartidoVIP


class VIPMatchDetailsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('details_admin')
        UserAccess.objects.create(user=self.admin, role='admin', must_change_password=False)
        self.match = PartidoVIP.objects.create(titulo='Vuelve el Clasico', equipo_local='Barcelona',
            equipo_visitante='Real Madrid', jornada=10, cerrado=True, goles_reales=3,
            fecha_cierre=datetime(2026, 10, 23, 19, tzinfo=dt_timezone.utc))
        self.vote = VotoPartidoVIP.objects.create(partido=self.match, division='Primera División',
            manager='Manager prueba', posicionamiento='local', pronostico_goles='3+',
            penalizaciones_objetivo={'Otro': 50})
        for target in ('core.views.get_team_logo', 'core.views.get_preferred_team_logo'):
            patcher = patch(target, return_value='')
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_migration_fills_only_missing_clasico_display_without_touching_votes(self):
        migration = importlib.import_module('core.migrations.0026_complete_clasico_display')
        before = VotoPartidoVIP.objects.values().get(pk=self.vote.pk)
        other = PartidoVIP.objects.create(titulo='Otro partido', equipo_local='Barcelona', equipo_visitante='Real Madrid',
            jornada=10, cerrado=True, goles_reales=3, fecha_cierre=self.match.fecha_cierre)
        migration.complete_clasico(apps, SimpleNamespace(connection=connection))
        self.match.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.match.resultado, '1–2')
        self.assertIn('Raphinha (61’)', self.match.goleadores)
        self.assertIn('Mbappé (41’ y 87’)', self.match.goleadores)
        self.assertEqual(self.match.goles_reales, 3)
        self.assertEqual(other.resultado, '')
        self.assertEqual(VotoPartidoVIP.objects.values().get(pk=self.vote.pk), before)
        self.match.goleadores = 'Corrección manual'
        self.match.save(update_fields=['goleadores'])
        migration.complete_clasico(apps, SimpleNamespace(connection=connection))
        self.match.refresh_from_db()
        self.assertEqual(self.match.goleadores, 'Corrección manual')

    def test_admin_edit_is_visible_and_does_not_recalculate_or_send_mail(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('vip_management')), 'Guardar marcador y goleadores')
        before = VotoPartidoVIP.objects.values().get(pk=self.vote.pk)
        data = {'action': 'update_match_details', 'partido_id': self.match.pk,
                'resultado': '1-2', 'goleadores': 'Raphinha (61’); Mbappé (41’ y 87’)'}
        with patch('core.views.send_vip_penalty_links') as send:
            self.assertContains(self.client.post(reverse('vip_management'), data), 'actualizados.')
        send.assert_not_called()
        self.match.refresh_from_db()
        self.assertEqual(self.match.resultado, '1–2')
        self.assertEqual(self.match.goles_reales, 3)
        self.assertEqual(VotoPartidoVIP.objects.values().get(pk=self.vote.pk), before)
        self.assertNotContains(self.client.get(reverse('vip_matches')), 'Guardar marcador y goleadores')
        for score in ('2-2', 'Texto incorrecto'):
            self.client.post(reverse('vip_management'), {**data, 'resultado': score})
            self.match.refresh_from_db()
            self.assertEqual(self.match.resultado, '1–2')
