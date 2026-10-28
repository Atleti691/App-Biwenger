"""Add the shared application invitation to all Django mail before delivery."""
from copy import copy
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.template.loader import render_to_string

FOOTER_TITLE = 'Tu liga, a un clic'
HTML_MARKER = 'data-league-app-footer="true"'


def with_app_invitation(message):
    """Keep recipients, attachments and tracking headers; never duplicate the footer."""
    context = {'app_url': settings.LEAGUE_APP_URL + '/login/'}
    footer = render_to_string('email_app_footer.html', context)
    plain_footer = (f'\n\n{FOOTER_TITLE}\nConsulta las clasificaciones, los resultados, los goles, '
                    f'tus cláusulas y los torneos. ¡Entra y sigue la liga!\nEntrar en la aplicación: {context["app_url"]}')
    body = message.body
    is_html = message.content_subtype == 'html'
    if not is_html and FOOTER_TITLE not in body:
        body += plain_footer
    result = EmailMultiAlternatives(subject=message.subject, body=body,
        from_email=message.from_email, to=message.to, bcc=message.bcc, cc=message.cc,
        reply_to=message.reply_to, headers=copy(message.extra_headers), attachments=list(message.attachments),
        connection=message.connection)
    result.encoding = message.encoding
    result.mixed_subtype = message.mixed_subtype
    result.content_subtype = message.content_subtype

    def add_html_footer(html):
        if HTML_MARKER in html:
            return html
        if re.search(r'</body\s*>', html, re.I):
            return re.sub(r'</body\s*>', lambda match: footer + match.group(), html, count=1, flags=re.I)
        return html + footer

    if is_html:
        result.body = add_html_footer(body)
    has_html = is_html
    for content, mimetype in getattr(message, 'alternatives', []):
        if mimetype == 'text/html':
            content = add_html_footer(content)
            has_html = True
        result.attach_alternative(content, mimetype)
    if not has_html:
        result.attach_alternative(render_to_string('email_with_app_footer.html',
            {**context, 'body': message.body}), 'text/html')
    return result


class EmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        backend = settings.EMAIL_DELIVERY_BACKEND
        if backend == 'core.email_backend.EmailBackend':
            backend = 'django.core.mail.backends.smtp.EmailBackend'
        self.delivery = get_connection(backend=backend, fail_silently=fail_silently, **kwargs)

    def open(self):
        return self.delivery.open()

    def close(self):
        return self.delivery.close()

    def send_messages(self, email_messages):
        return self.delivery.send_messages([with_app_invitation(message) for message in email_messages or []])
