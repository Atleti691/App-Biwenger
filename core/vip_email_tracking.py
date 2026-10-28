"""Authenticated Brevo delivery events for precisely identified VIP email attempts."""
import json
import secrets
from datetime import datetime, timezone as datetime_timezone
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import CorreoPenalizacionVIP


@csrf_exempt
@require_POST
def brevo_vip_events(request):
    secret = getattr(settings, 'BREVO_WEBHOOK_TOKEN', '')
    if not secret or not secrets.compare_digest(request.headers.get('Authorization', ''), f'Bearer {secret}'):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    if len(request.body) > 65536:
        return JsonResponse({'error': 'Petición demasiado grande'}, status=413)
    try:
        payload = json.loads(request.body)
        events = payload if isinstance(payload, list) else [payload]
        if len(events) > 100 or any(not isinstance(event, dict) for event in events):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Datos no válidos'}, status=400)
    mapping = {'delivered': 'entregado', 'opened': 'entregado', 'unique_opened': 'entregado',
               'click': 'entregado', 'hard_bounce': 'rechazado', 'soft_bounce': 'aplazado',
               'blocked': 'rechazado', 'invalid': 'rechazado', 'error': 'rechazado',
               'deferred': 'aplazado'}
    updated = 0
    for event in events:
        state = mapping.get(event.get('event'))
        reference = str(event.get('X-Mailin-custom', ''))
        if not state or not reference.startswith('vip_attempt:'):
            continue
        try:
            reference = UUID(reference.removeprefix('vip_attempt:'))
            if event.get('ts_event') is not None:
                event_time = datetime.fromtimestamp(float(event['ts_event']), tz=datetime_timezone.utc)
            else:
                event_time = parse_datetime(str(event.get('date', '')))
                if event_time and timezone.is_naive(event_time):
                    event_time = timezone.make_aware(event_time)
            if event_time is None:
                continue
        except (ValueError, TypeError, OverflowError, OSError):
            continue
        with transaction.atomic():
            attempt = CorreoPenalizacionVIP.objects.select_for_update().filter(referencia=reference).first()
            if not attempt or attempt.email.casefold() != str(event.get('email', '')).strip().casefold():
                continue
            if event_time < attempt.creado.replace(microsecond=0) or (attempt.evento_fecha and event_time <= attempt.evento_fecha):
                continue
            # Opens/deliveries confirm receipt, a later deferral must not undo that evidence.
            if attempt.estado == 'entregado' and state == 'aplazado':
                continue
            attempt.estado = state
            attempt.evento_fecha = event_time
            attempt.detalle = str(event.get('reason', ''))[:300]
            attempt.save(update_fields=['estado', 'evento_fecha', 'detalle'])
            updated += 1
    return JsonResponse({'updated': updated})
