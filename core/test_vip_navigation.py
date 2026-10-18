from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CodigoEmergenciaVIP, JornadaRegistro, PartidoVIP, UserAccess, VotoPartidoVIP


class VIPNavigationTests(TestCase):
    def setUp(self):
        self.users = {}
        for name, role in [('vip_admin','admin'), ('vip_division_admin','collaborator'), ('vip_viewer','viewer')]:
            user = get_user_model().objects.create_user(name)
            UserAccess.objects.create(user=user, role=role, must_change_password=False,
                editable_divisions=['Primera División'] if role == 'collaborator' else [])
            self.users[role] = user
        self.match = PartidoVIP.objects.create(titulo='VIP de prueba', jornada=7,
            equipo_local='Local', equipo_visitante='Visitante',
            escudo_local='https://example.com/local.png', escudo_visitante='https://example.com/visitor.png',
            fecha_cierre=timezone.now()+timedelta(days=2))
        for target, value in [('core.views.get_team_logo','https://example.com/logo.png'),
                              ('core.views.get_preferred_team_logo','')]:
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def login(self, role):
        self.client.force_login(self.users[role])

    def payload(self):
        return {'action':'create', 'titulo':'Nuevo VIP', 'jornada':'8',
                'equipo_local':'Local', 'equipo_visitante':'Visitante',
                'escudo_local':'https://example.com/local.png', 'escudo_visitante':'https://example.com/visitor.png',
                'fecha_cierre':'2027-01-01T20:00', 'fecha_limite_penalizaciones':'2027-01-05T20:00'}

    def test_admins_have_management_card_only_in_management_menu(self):
        for role in ('admin','collaborator'):
            with self.subTest(role=role):
                self.login(role)
                response = self.client.get('/?menu=gestion')
                self.assertContains(response, reverse('vip_management'))
                self.assertContains(response, 'Gestionar partidos VIP')
                response = self.client.get('/?menu=consulta')
                self.assertContains(response, reverse('vip_matches'))
                self.assertNotContains(response, reverse('vip_management'))
                self.assertNotContains(response, 'Gestiona y consulta los partidos VIP')

    def test_viewer_and_user_preview_have_no_management_link(self):
        for role in ('viewer','admin','collaborator'):
            with self.subTest(role=role):
                self.login(role)
                self.client.get('/?vista=usuario')
                response = self.client.get('/?menu=consulta')
                self.assertContains(response, reverse('vip_matches'))
                self.assertNotContains(response, reverse('vip_management'))

    def test_consultation_is_read_only_for_all_roles(self):
        for role in ('viewer','admin','collaborator'):
            with self.subTest(role=role):
                self.login(role)
                response = self.client.get(reverse('vip_matches'))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'VIP de prueba')
                self.assertContains(response, f'/partidos-vip/votar/{self.match.pk}/')
                self.assertNotContains(response, '➕ Crear partido VIP')
                self.assertNotContains(response, '<form')
                self.assertFalse(response.context['can_create_vip'])
                self.assertFalse(response.context['is_admin'])
                self.assertFalse(response.context['can_follow_vip'])
                for action in ('create','close','remind','manual_vote','manual_penalty','reset_penalty','emergency_code'):
                    data = {**self.payload(), 'action':action, 'partido_id':self.match.pk}
                    self.assertEqual(self.client.post(reverse('vip_matches'), data).status_code, 403)
        self.assertEqual(PartidoVIP.objects.count(), 1)
        self.match.refresh_from_db()
        self.assertFalse(self.match.cerrado)
        self.assertEqual(VotoPartidoVIP.objects.count(), 0)
        self.assertEqual(CodigoEmergenciaVIP.objects.count(), 0)

    def test_management_rejects_viewer_even_with_legacy_division_assignments(self):
        self.login('viewer')
        access = self.users['viewer'].useraccess
        access.editable_divisions = ['Primera División']
        access.save()
        self.assertEqual(self.client.get(reverse('vip_management')).status_code, 403)
        self.assertEqual(self.client.post(reverse('vip_management'), self.payload()).status_code, 403)
        self.assertEqual(PartidoVIP.objects.count(), 1)

    def test_admin_and_division_admin_can_create_from_management(self):
        for role in ('admin','collaborator'):
            with self.subTest(role=role):
                self.login(role)
                response = self.client.get(reverse('vip_management'))
                self.assertContains(response, '➕ Crear partido VIP')
                self.assertTrue(response.context['can_follow_vip'])
                before = PartidoVIP.objects.count()
                response = self.client.post(reverse('vip_management'), self.payload())
                self.assertContains(response, 'Partido VIP creado.')
                self.assertEqual(PartidoVIP.objects.count(), before+1)

    def test_anonymous_must_login_for_both_screens(self):
        for route in ('vip_matches','vip_management'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 302)

    def test_consultation_does_not_save_logo_updates(self):
        self.login('admin')
        with patch('core.views.get_preferred_team_logo', return_value='https://example.com/preferred.png'):
            self.client.get(reverse('vip_matches'))
        self.match.refresh_from_db()
        self.assertEqual(self.match.escudo_local, 'https://example.com/local.png')

    def test_participation_bar_uses_real_votes_and_preserves_73(self):
        roster = {'Primera División':[f'Manager {index}' for index in range(80)]}
        VotoPartidoVIP.objects.bulk_create([VotoPartidoVIP(partido=self.match, division='Primera División',
            manager=f'Manager {index}', posicionamiento='local', pronostico_goles='2') for index in range(73)])
        self.login('viewer')
        with patch('core.views.active_league_managers', return_value=roster):
            response = self.client.get(reverse('vip_matches'))
        match = response.context['partidos'][0]
        self.assertEqual(match.participantes, 73)
        self.assertEqual(match.total_managers, 80)
        self.assertEqual(match.porcentaje_participacion, 91)
        self.assertContains(response, '73 de 80 han votado')
        self.assertContains(response, 'aria-valuenow="91"')
        for action in ('manual_vote','manual_penalty','reset_penalty','emergency_code','remind_penalty'):
            self.assertNotContains(response, f'name="action" value="{action}"')

    def test_empty_participation_and_retired_voter(self):
        self.login('viewer')
        with patch('core.views.active_league_managers', return_value={}):
            response = self.client.get(reverse('vip_matches'))
            self.assertContains(response, '0 de 0 han votado')
            self.assertContains(response, 'aria-valuenow="0"')
            VotoPartidoVIP.objects.create(partido=self.match, division='Primera División',
                manager='Manager retirado', posicionamiento='local', pronostico_goles='2')
            response = self.client.get(reverse('vip_matches'))
            self.assertContains(response, '1 de 1 han votado')
            self.assertContains(response, 'aria-valuenow="100"')

    def test_results_dropdown_is_per_match_and_reuses_statistics(self):
        self.match.cerrado = True
        self.match.goles_reales = 2
        self.match.save()
        VotoPartidoVIP.objects.create(partido=self.match, division='Primera División', manager='AlexJulio',
            posicionamiento='local', pronostico_goles='2', penalizaciones_objetivo={'Rexza':50})
        JornadaRegistro.objects.create(user_access=self.users['admin'].useraccess, season=2026,
            jornada=7, division='Primera División', cerrada=True, datos={'AlexJulio':{'app':'0','q':'9'}})
        other = PartidoVIP.objects.create(titulo='Otro partido', jornada=8, equipo_local='Otro local',
            equipo_visitante='Otro visitante', fecha_cierre=timezone.now()+timedelta(days=2))
        self.login('viewer')
        with patch('core.views.send_vip_position_winner_emails') as send:
            response = self.client.get(reverse('vip_matches'))
        send.assert_not_called()
        self.assertContains(response, 'Resultados del partido VIP', count=2)
        self.assertContains(response, f'id="vip-results-{self.match.pk}"')
        self.assertContains(response, f'id="vip-results-{other.pk}"')
        self.assertNotContains(response, '📊 Estadísticas VIP')
        self.assertNotContains(response, 'Quién ha votado y quién está pendiente')
        self.assertNotContains(response, 'Ver quién ejecutó cada penalización')
        match = next(item for item in response.context['partidos'] if item.pk == self.match.pk)
        first = next(row for row in match.results_panel['divisions'] if row['name'] == 'Primera División')
        self.assertEqual(first['votes'], 1)
        self.assertEqual(first['positions']['local'], 1)
        self.assertEqual(first['goals'][2]['count'], 1)
        self.assertEqual(first['targets'], [('Rexza',50)])
        self.assertEqual(first['media_local'], 0)
        self.assertEqual(first['positioning_winner'], 'Local')
        self.assertTrue(first['calculated'])
        self.assertEqual(match.results_panel['match'].pk, self.match.pk)

    def test_private_followup_and_manual_actions_remain_in_management(self):
        self.login('admin')
        response = self.client.get(reverse('vip_management'))
        self.assertContains(response, 'Quién ha votado y quién está pendiente')
        self.assertContains(response, 'value="remind"')
        self.assertContains(response, 'value="close"')
        self.assertContains(response, 'value="emergency_code"')
        self.assertContains(response, 'Introducir votos realizados fuera de la aplicación')
        self.assertContains(response, 'Ver quién ejecutó cada penalización')
