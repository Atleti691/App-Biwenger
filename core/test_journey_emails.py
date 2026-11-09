from io import BytesIO
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from PIL import Image

from .journey_emails import send_journey_standings, standings_png
from .models import CambioRegistro, ContactoManager, JornadaRegistro, UserAccess
from .views import statistics_data


@override_settings(EMAIL_BACKEND='core.email_backend.EmailBackend',
    EMAIL_DELIVERY_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    LEAGUE_APP_URL='https://liga-amigos-xi.onrender.com')
class JourneyEmailTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user('standings_admin')
        self.access = UserAccess.objects.create(user=self.admin, role='admin', must_change_password=False)
        self.record = JornadaRegistro.objects.create(user_access=self.access, season=2026, jornada=11,
            division='Primera División', cerrada=True,
            datos={'Uno': {'app': '100', 'q': '2', 'p': '1', 'penalty': '5'}, 'Dos': {'app': '80'}})
        for division, manager, email in [('Primera División', 'Uno', 'ONE@example.com'),
                ('Primera División', 'Dos', 'one@example.com'),
                ('Primera División', 'Retirado', 'retired@example.com'),
                ('Segunda División', 'Otro', 'other@example.com')]:
            ContactoManager.objects.create(division=division, manager=manager, email=email, provincia='Madrid')
        roster = patch('core.views.active_league_managers', return_value={
            'Primera División': ['Uno', 'Dos'], 'Segunda División': ['Otro']})
        roster.start()
        self.addCleanup(roster.stop)
        for target in ('core.cup.cup_awards', 'core.views.vip_adjustments_for_journey'):
            patcher = patch(target, return_value={})
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_division_only_private_recipients_png_and_direct_link(self):
        self.assertEqual(send_journey_standings(self.record.pk, self.admin.pk), 2)
        self.assertEqual(len(mail.outbox), 2)
        message = next(msg for msg in mail.outbox if msg.body.startswith('Hola, Uno.'))
        self.assertEqual(message.bcc, [])
        self.assertEqual(message.to, ['ONE@example.com'])
        self.assertNotIn('cerrada', message.subject.lower())
        self.assertIn('Primera División', message.subject)
        self.assertNotIn('Otro', message.body)
        self.assertIn('Uno: 115 puntos', message.body)
        html = message.alternatives[0][0]
        self.assertIn('cid:clasificacion-', html)
        self.assertIn('division=Primera+Divisi%C3%B3n', html)
        self.assertEqual(html.count('data-league-app-footer="true"'), 1)
        attachment = message.attachments[0]
        self.assertEqual(attachment.get_content_type(), 'image/png')
        self.assertEqual(attachment['Content-Disposition'].split(';')[0], 'inline')
        image = Image.open(BytesIO(attachment.get_payload(decode=True)))
        self.assertEqual(image.width, 1100)
        self.assertGreater(image.height, 400)
        self.assertIn('multipart/related', message.message().as_string())

    def test_image_uses_exact_same_totals_as_statistics_with_vip_and_cup(self):
        with patch('core.views.vip_adjustments_for_journey', return_value={('Primera División', 'Uno'): 90}), \
             patch('core.cup.cup_awards', return_value={(11, 'Primera División', 'Uno'): 15}), \
             patch('core.journey_emails.standings_png', wraps=standings_png) as render:
            expected = statistics_data(2026, 11, 'Primera División', 'general')['rows']
            send_journey_standings(self.record.pk, self.admin.pk)
        self.assertEqual(render.call_args.args[2], sorted(expected, key=lambda row: -row['total']))
        self.assertEqual(render.call_args.args[3]['Uno'], 220)

    def test_no_open_round_or_missing_recipients_email(self):
        self.record.cerrada = False
        self.record.save()
        self.assertEqual(send_journey_standings(self.record.pk, self.admin.pk), 0)
        self.record.cerrada = True
        self.record.save()
        ContactoManager.objects.filter(division='Primera División').delete()
        self.assertEqual(send_journey_standings(self.record.pk, self.admin.pk), 0)
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_close_registers_one_after_commit_notification_not_on_ordinary_save(self):
        self.record.cerrada = False
        self.record.save()
        self.client.force_login(self.admin)
        url = '/api/jornada/2026/11/?division=Primera%20Divisi%C3%B3n'
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(url, data=json.dumps({'cerrada': True}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 2)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.client.post(url, data=json.dumps({'cerrada': True}), content_type='application/json')
        self.assertEqual(len(callbacks), 0)
        self.assertEqual(len(mail.outbox), 2)

    def test_private_clause_amount_and_legacy_total(self):
        self.record.datos['Uno'].update(clauses=[{'to': 'Dos', 'value': 1000000},
            {'to': 'Dos', 'value': 2000000}, {'to': 'Dos', 'value': 3000000}])
        self.record.datos['Dos'].update(money='42.000 €', clauses=[])
        self.record.save()
        send_journey_standings(self.record.pk, self.admin.pk)
        first = next(msg for msg in mail.outbox if msg.body.startswith('Hola, Uno.'))
        second = next(msg for msg in mail.outbox if msg.body.startswith('Hola, Dos.'))
        self.assertIn('900.000 €', first.body)
        self.assertIn('3 cláusula', first.body)
        self.assertIn('900.000 €', first.alternatives[0][0])
        self.assertNotIn('42.000 €', first.body)
        self.assertIn('42.000 €', second.body)
        self.assertNotIn('900.000 €', second.body)
        self.assertNotIn('Has realizado', second.body)

    def test_repeat_close_does_not_duplicate_unchanged_email(self):
        self.assertEqual(send_journey_standings(self.record.pk, self.admin.pk), 2)
        self.assertEqual(send_journey_standings(self.record.pk, self.admin.pk), 0)
        self.assertEqual(len(mail.outbox), 2)
        self.record.datos['Uno']['money'] = '1.000 €'
        self.record.save()
        self.assertEqual(send_journey_standings(self.record.pk, self.admin.pk), 1)
        self.assertIn('1.000 €', mail.outbox[-1].body)

    def test_mail_failure_does_not_undo_saved_close(self):
        self.record.cerrada = False
        self.record.save()
        self.client.force_login(self.admin)
        with patch('core.journey_emails.standings_png', side_effect=RuntimeError('test rendering error')), \
             self.assertLogs('core.journey_emails', level='ERROR'), \
             self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/jornada/2026/11/?division=Primera%20Divisi%C3%B3n',
                data=json.dumps({'cerrada': True}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertTrue(self.record.cerrada)
        self.assertTrue(CambioRegistro.objects.filter(accion='error al enviar clasificación').exists())

    def test_image_supports_all_names_and_long_names_and_stats_link_selects_division(self):
        rows = [{'manager': 'Nombre muy largo con acentos áéíóú y varios apellidos '*3, 'total': -1234}]
        image = Image.open(BytesIO(standings_png('Segunda División', 206, rows, {})))
        self.assertGreater(image.height, 450)
        self.client.force_login(self.admin)
        response = self.client.get('/estadisticas/?division=Segunda%20Divisi%C3%B3n')
        self.assertContains(response, '<option selected>Segunda División</option>')
