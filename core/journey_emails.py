"""Division-scoped closing email with the exact web standings as a PNG."""
from io import BytesIO
from email.mime.image import MIMEImage
from pathlib import Path
from urllib.parse import urlencode
import logging
import hashlib
import json

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont
import reportlab

from .journeys import journey_label
from .clause_data import normalize_clauses, clause_totals
from .models import CambioRegistro, ContactoManager, JornadaRegistro

logger = logging.getLogger(__name__)


def standings_png(division, journey, rows, round_totals):
    font_dir = Path(reportlab.__file__).parent / 'fonts'
    def font(size, bold=False):
        return ImageFont.truetype(str(font_dir / ('VeraBd.ttf' if bold else 'Vera.ttf')), size)
    measure = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    normal, bold = font(27), font(28, True)
    def wrap_name(name):
        lines, line = [], ''
        for character in str(name):
            if line and measure.textlength(line + character, font=normal) > 530:
                lines.append(line)
                line = ''
            line += character
        return [*lines, line] if line else lines or ['—']
    prepared = [(row, wrap_name(row['manager'])) for row in rows]
    heights = [max(68, len(lines)*34+24) for _, lines in prepared]
    image = Image.new('RGB', (1100, 324+sum(heights)), '#ffffff')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1100, 186), fill='#172e5c')
    draw.text((38, 24), 'LIGA AMIGOS XI', font=font(22, True), fill='#c9dcff')
    draw.text((38, 65), division, font=font(39, True), fill='#ffffff')
    draw.text((38, 126), f'{journey_label(journey)} · Clasificación general actualizada', font=font(25), fill='#e1eaff')
    draw.rectangle((0, 186, 1100, 242), fill='#edf2fc')
    draw.text((32, 202), 'POS.', font=font(21, True), fill='#475873')
    draw.text((125, 202), 'MANAGER', font=font(21, True), fill='#475873')
    draw.text((890, 202), 'JORNADA', font=font(21, True), fill='#475873', anchor='ra')
    draw.text((1060, 202), 'TOTAL', font=font(21, True), fill='#475873', anchor='ra')
    def number(value):
        return f'{int(value):,}'.replace(',', '.')
    y = 242
    for index, ((row, lines), height) in enumerate(zip(prepared, heights), 1):
        draw.rectangle((0, y, 1100, y+height), fill='#eef4ff' if index == 1 else '#f7f9fc' if index % 2 == 0 else '#ffffff')
        draw.text((38, y+20), str(index), font=normal, fill='#60718a')
        for offset, line in enumerate(lines):
            draw.text((125, y+18+offset*34), line, font=normal, fill='#172033')
        draw.text((890, y+18), number(round_totals.get(row['manager'], 0)), font=normal, fill='#475873', anchor='ra')
        draw.text((1060, y+18), number(row['total']), font=bold, fill='#172033', anchor='ra')
        y += height
    draw.text((38, y+18), f'{len(rows)} managers · Puntos netos de la liga · {timezone.localtime():%d/%m/%Y %H:%M}', font=font(19), fill='#637083')
    draw.text((38, y+47), 'Consulta los detalles y el resto de torneos en la aplicación.', font=font(19), fill='#637083')
    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()


def send_journey_standings(record_id, actor_id):
    """Send each manager a private, personalized email for the closed division.

    Called only after commit. A mail/image failure never reopens or rolls back data.
    """
    from .views import active_league_managers, statistics_data
    record = JornadaRegistro.objects.get(pk=record_id)
    if not record.cerrada:
        return 0
    try:
        active = set(active_league_managers().get(record.division, []))
        contacts = ContactoManager.objects.filter(division=record.division).exclude(email='')
        recipients = [contact for contact in contacts
                      if contact.manager in active and contact.email.strip()]
        if not recipients:
            return 0
        rows = sorted(statistics_data(record.season, record.jornada, record.division, 'general')['rows'],
            key=lambda row: -row['total'])
        round_totals = {row['manager']: row['total'] for row in
            statistics_data(record.season, record.jornada, record.division)['rows']}
        if not rows:
            return 0
        image = standings_png(record.division, record.jornada, rows, round_totals)
        stats_url = settings.LEAGUE_APP_URL + '/estadisticas/?' + urlencode({'division': record.division})
        cid = f'clasificacion-{record.pk}@liga-amigos-xi'
        sent = 0
        failed = 0
        previous = CambioRegistro.objects.filter(division=record.division, season=record.season,
            jornada=record.jornada, accion='enviar clasificación individual').values_list('detalle', flat=True)
        already_sent = {item.get('huella') for item in previous if item.get('envio_aceptado')}
        for contact in recipients:
            row = (record.datos or {}).get(contact.manager, {})
            try:
                clauses = normalize_clauses(row.get('clauses', []))
            except (ValueError, AttributeError):
                clauses = []
            # Legacy rounds may retain the total but have lost individual details.
            totals = clause_totals(clauses) if clauses else None
            money = totals['money'] if totals else str(row.get('money') or '').strip()
            has_money = any(char in '123456789' for char in money)
            context = {'division': record.division, 'journey': journey_label(record.jornada),
                       'rows': rows, 'image_cid': cid, 'stats_url': stats_url,
                       'app_url': settings.LEAGUE_APP_URL + '/login/', 'manager': contact.manager,
                       'clause_money': money if has_money else '', 'clause_count': len(clauses) if clauses else None}
            fingerprint = hashlib.sha256(json.dumps({'manager': contact.manager, 'email': contact.email.strip().casefold(),
                'rows': [(standing['manager'], standing['total']) for standing in rows],
                'round_totals': round_totals, 'clause_money': context['clause_money'],
                'clause_count': context['clause_count']}, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
            if fingerprint in already_sent:
                continue
            text = (f'Hola, {contact.manager}.\n\nYa está actualizada la clasificación de {record.division} '
                    f'tras la {journey_label(record.jornada).lower()}.\n\n')
            if has_money:
                if clauses:
                    text += f'Has realizado {len(clauses)} cláusula(s).\n'
                text += f'Penalización en dinero por cláusulas: {money}.\n\n'
            text += ('\n'.join(f'{index}. {standing["manager"]}: {standing["total"]} puntos' for index, standing in enumerate(rows, 1))
                     + f'\n\nVer mi clasificación: {stats_url}\n\nLa imagen completa va incluida en este correo.')
            message = EmailMultiAlternatives(subject=f'Tu clasificación actualizada · {record.division} · {journey_label(record.jornada)}',
                body=text, to=[contact.email.strip()])
            message.mixed_subtype = 'related'
            message.attach_alternative(render_to_string('journey_standings_email.html', context), 'text/html')
            attachment = MIMEImage(image, _subtype='png')
            attachment.add_header('Content-ID', f'<{cid}>')
            attachment.add_header('Content-Disposition', 'inline',
                filename=f'clasificacion-{slugify(record.division)}-{record.jornada}.png')
            message.attach(attachment)
            try:
                result = message.send(fail_silently=False) or 0
                sent += result
                if not result:
                    failed += 1
                else:
                    CambioRegistro.objects.create(usuario_id=actor_id, division=record.division,
                        season=record.season, jornada=record.jornada, accion='enviar clasificación individual',
                        detalle={'manager': contact.manager, 'huella': fingerprint, 'envio_aceptado': True})
                    already_sent.add(fingerprint)
            except Exception:
                failed += 1
                logger.exception('No se pudo enviar la clasificación a %s en registro %s', contact.manager, record_id)
        CambioRegistro.objects.create(usuario_id=actor_id, division=record.division,
            season=record.season, jornada=record.jornada, accion='enviar clasificación de división',
            detalle={'envio_aceptado': bool(sent), 'destinatarios': len(recipients),
                     'envios_aceptados': sent, 'envios_fallidos': failed,
                     'imagen_incluida': True, 'sin_confirmacion_de_entrega_individual': True})
        return sent
    except Exception:
        logger.exception('No se pudo enviar la clasificación del registro %s', record_id)
        CambioRegistro.objects.create(usuario_id=actor_id, division=record.division,
            season=record.season, jornada=record.jornada, accion='error al enviar clasificación',
            detalle={'envio_aceptado': False, 'revisar_brevo_antes_de_reintentar': True})
        return 0
