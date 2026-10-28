from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from .email_backend import with_app_invitation


@override_settings(LEAGUE_APP_URL='https://liga-amigos-xi.onrender.com',
    EMAIL_BACKEND='core.email_backend.EmailBackend',
    EMAIL_DELIVERY_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AppEmailFooterTests(SimpleTestCase):
    def test_every_plain_email_gets_app_button_and_short_summary(self):
        message = EmailMessage('Tu código', 'Código: 123456', to=['one@example.com'],
            bcc=['hidden@example.com'], headers={'X-Mailin-custom': 'test-tracking'})
        message.attach('datos.txt', 'Contenido adjunto', 'text/plain')
        self.assertEqual(message.send(), 1)
        delivered = mail.outbox[-1]
        self.assertIn('Tu liga, a un clic', delivered.body)
        self.assertIn('Código: 123456', delivered.body)
        self.assertEqual(delivered.bcc, ['hidden@example.com'])
        self.assertEqual(delivered.extra_headers['X-Mailin-custom'], 'test-tracking')
        self.assertEqual(len(delivered.attachments), 1)
        html, mimetype = delivered.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('clasificaciones, los resultados, los goles', html)
        self.assertIn('Entrar en la aplicación</a>', html)
        self.assertIn('https://liga-amigos-xi.onrender.com/login/', html)
        self.assertNotIn('Tu liga, a un clic', message.body)

    def test_html_and_plain_footers_are_not_duplicated(self):
        message = EmailMultiAlternatives('Resumen', 'Texto original', to=['one@example.com'])
        message.attach_alternative('<html><body><p>Texto HTML</p></body></html>', 'text/html')
        once = with_app_invitation(message)
        twice = with_app_invitation(once)
        self.assertEqual(twice.body.count('Tu liga, a un clic'), 1)
        self.assertEqual(twice.alternatives[0][0].count('data-league-app-footer="true"'), 1)
        self.assertIn('Texto HTML', twice.alternatives[0][0])
        self.assertTrue(twice.alternatives[0][0].endswith('</body></html>'))

    def test_html_only_email_stays_html_and_untrusted_plain_text_is_escaped(self):
        message = EmailMessage('Prueba', '<p>Correo HTML</p>', to=['one@example.com'])
        message.content_subtype = 'html'
        result = with_app_invitation(message)
        self.assertEqual(result.content_subtype, 'html')
        self.assertIn('Entrar en la aplicación', result.body)
        plain = with_app_invitation(EmailMessage('Texto', '<script>alert(1)</script>', to=['one@example.com']))
        self.assertNotIn('<script>', plain.alternatives[0][0])

    def test_wrapper_handles_empty_batch(self):
        self.assertEqual(mail.get_connection().send_messages([]), 0)
