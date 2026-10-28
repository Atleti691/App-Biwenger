import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import CorreoPenalizacionVIP, ContactoManager, PartidoVIP, UserAccess, VotoPartidoVIP
from .views import send_vip_penalty_links


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BREVO_WEBHOOK_TOKEN='test-secret')
class VIPEmailTrackingTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('test_admin')
        UserAccess.objects.create(user=self.admin, role='admin', must_change_password=False)
        self.match = PartidoVIP.objects.create(titulo='Premio VIP', equipo_local='Local', equipo_visitante='Visitante',
            fecha_cierre=timezone.now()-timedelta(days=1), cerrado=True, goles_reales=2,
            fecha_limite_penalizaciones=timezone.now()+timedelta(hours=12))
        self.winner = VotoPartidoVIP.objects.create(partido=self.match, division='Primera División',
            manager='AlexJulio', posicionamiento='local', pronostico_goles='2')
        ContactoManager.objects.create(division=self.winner.division, manager=self.winner.manager,
            email='winner@example.com', provincia='Madrid')
        self.request = RequestFactory().get('/')
        self.request.user = self.admin
        for target in ('core.views.get_team_logo', 'core.views.get_preferred_team_logo'):
            patcher = patch(target, return_value='')
            patcher.start()
            self.addCleanup(patcher.stop)

    def event(self, attempt, **extra):
        payload = {'event': 'delivered', 'email': attempt.email,
            'X-Mailin-custom': f'vip_attempt:{attempt.referencia}',
            'ts_event': (timezone.now()+timedelta(seconds=2)).timestamp(), **extra}
        return self.client.post(reverse('brevo_vip_events'), data=json.dumps(payload),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer test-secret')

    def test_send_tracks_acceptance_not_delivery_and_unique_reference(self):
        self.assertEqual(send_vip_penalty_links(self.request, self.match, [self.winner]), 1)
        attempt = CorreoPenalizacionVIP.objects.get()
        self.assertEqual(attempt.estado, 'enviado')
        self.assertEqual(mail.outbox[0].to, ['winner@example.com'])
        self.assertEqual(mail.outbox[0].extra_headers['X-Mailin-custom'], f'vip_attempt:{attempt.referencia}')
        self.assertIn('50 puntos', mail.outbox[0].body)
        self.assertIn('Plazo máximo', mail.outbox[0].body)

    def test_individual_failures_and_missing_contact_are_recorded(self):
        missing = VotoPartidoVIP.objects.create(partido=self.match, division='Primera División',
            manager='Sin contacto', posicionamiento='local', pronostico_goles='2')
        with patch('core.views.get_connection') as connection:
            connection.return_value.send_messages.return_value = 0
            self.assertEqual(send_vip_penalty_links(self.request, self.match, [self.winner, missing]), 0)
        self.assertEqual(CorreoPenalizacionVIP.objects.get(voto=self.winner).estado, 'error')
        self.assertEqual(CorreoPenalizacionVIP.objects.get(voto=missing).estado, 'sin_correo')

    def test_send_exception_does_not_prevent_other_recipients(self):
        second = VotoPartidoVIP.objects.create(partido=self.match, division='Primera División',
            manager='Segundo ganador', posicionamiento='local', pronostico_goles='2')
        ContactoManager.objects.create(division=second.division, manager=second.manager,
            email='second@example.com', provincia='Madrid')
        with patch('core.views.get_connection') as connection, self.assertLogs('core.views', level='ERROR'):
            connection.return_value.send_messages.side_effect = [RuntimeError('SMTP no disponible'), 1]
            self.assertEqual(send_vip_penalty_links(self.request, self.match, [self.winner, second]), 1)
        self.assertEqual(CorreoPenalizacionVIP.objects.get(voto=self.winner).estado, 'error')
        self.assertEqual(CorreoPenalizacionVIP.objects.get(voto=second).estado, 'enviado')

    def test_webhook_requires_configured_secret_and_valid_payload(self):
        with override_settings(BREVO_WEBHOOK_TOKEN=''):
            response = self.client.post(reverse('brevo_vip_events'), '{}', content_type='application/json',
                HTTP_AUTHORIZATION='Bearer test-secret')
            self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('brevo_vip_events'), 'not-json', content_type='application/json',
            HTTP_AUTHORIZATION='Bearer test-secret')
        self.assertEqual(response.status_code, 400)

    def test_secure_delivery_and_out_of_order_events(self):
        attempt = CorreoPenalizacionVIP.objects.create(voto=self.winner, email='winner@example.com', estado='enviado')
        self.assertEqual(self.client.post(reverse('brevo_vip_events'), '{}', content_type='application/json').status_code, 403)
        self.assertEqual(self.event(attempt, email='other@example.com').json()['updated'], 0)
        self.assertEqual(self.event(attempt).json()['updated'], 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.estado, 'entregado')
        self.assertEqual(self.event(attempt, event='deferred').json()['updated'], 0)
        self.assertEqual(self.event(attempt, event='hard_bounce', ts_event=(timezone.now()-timedelta(days=1)).timestamp()).json()['updated'], 0)
        attempt.refresh_from_db()
        self.assertEqual(attempt.estado, 'entregado')

    def test_rejection_is_visible_but_not_fabricated(self):
        attempt = CorreoPenalizacionVIP.objects.create(voto=self.winner, email='winner@example.com', estado='enviado')
        self.assertEqual(self.event(attempt, event='hard_bounce', reason='Mailbox unavailable').json()['updated'], 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.estado, 'rechazado')
        self.assertEqual(attempt.detalle, 'Mailbox unavailable')

    def test_final_reminder_only_pending_and_once(self):
        VotoPartidoVIP.objects.create(partido=self.match, division='Primera División', manager='Ya repartió',
            posicionamiento='local', pronostico_goles='2', penalizaciones_objetivo={'Otro': 50})
        VotoPartidoVIP.objects.create(partido=self.match, division='Primera División', manager='No acertó',
            posicionamiento='local', pronostico_goles='1')
        self.client.force_login(self.admin)
        data = {'action': 'remind_penalty_last_day', 'partido_id': self.match.pk}
        response = self.client.post(reverse('vip_management'), data)
        self.assertContains(response, 'Recordatorio enviado a 1 de 1')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Últimas 24 horas', mail.outbox[0].subject)
        self.client.post(reverse('vip_management'), data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(CorreoPenalizacionVIP.objects.count(), 1)

    def test_reminders_cannot_send_early_or_expired_and_viewer_cannot_send(self):
        self.client.force_login(self.admin)
        data = {'action': 'remind_penalty_last_day', 'partido_id': self.match.pk}
        self.match.fecha_limite_penalizaciones = timezone.now()+timedelta(days=2)
        self.match.save()
        self.assertContains(self.client.post(reverse('vip_management'), data), 'solo se puede enviar durante las últimas 24 horas')
        self.match.fecha_limite_penalizaciones = timezone.now()-timedelta(seconds=1)
        self.match.save()
        for action in ('remind_penalty_last_day', 'remind_penalty'):
            self.assertContains(self.client.post(reverse('vip_management'), {**data, 'action': action}), 'El plazo de reparto ha terminado')
        self.assertFalse(CorreoPenalizacionVIP.objects.exists())
        viewer = get_user_model().objects.create_user('email_viewer')
        UserAccess.objects.create(user=viewer, role='viewer', must_change_password=False)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(reverse('vip_management'), data).status_code, 403)
        self.assertEqual(self.client.post(reverse('vip_matches'), data).status_code, 403)

    def test_history_is_private_and_legacy_sends_remain_unknown(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('vip_management'))
        self.assertContains(response, 'Sin registro de envío')
        CorreoPenalizacionVIP.objects.create(voto=self.winner, email='private-destination@example.com', estado='entregado')
        response = self.client.get(reverse('vip_management'))
        self.assertContains(response, 'Entrega confirmada por Brevo')
        self.assertContains(response, 'private-destination@example.com')
        response = self.client.get(reverse('vip_matches'))
        self.assertNotContains(response, 'private-destination@example.com')
        self.assertNotContains(response, 'Recordar pendientes · últimas 24 h')
