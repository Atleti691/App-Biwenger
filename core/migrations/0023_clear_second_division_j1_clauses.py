"""Requested correction: no clauses were executed in Segunda, J1, season 2026."""
from copy import deepcopy
from django.db import migrations


def clear_clauses(apps, schema_editor):
    alias = schema_editor.connection.alias
    records = apps.get_model('core', 'JornadaRegistro')
    clauses = apps.get_model('core', 'Clausula')
    audit = apps.get_model('core', 'CambioRegistro')
    for record in records.objects.using(alias).filter(
        season=2026, jornada=1, division='Segunda División',
    ):
        data = deepcopy(record.datos)
        before = {}
        for manager, row in data.items():
            if not isinstance(row, dict):
                continue
            if row.get('clauses') or row.get('money') or str(row.get('penalty') or '0') != '0':
                before[manager] = {key: deepcopy(row.get(key)) for key in ('clauses', 'money', 'penalty')}
                row.update(clauses=[], money='', penalty='0')
        legacy = list(clauses.objects.using(alias).filter(jornada_id=record.pk).values(
            'numero', 'jugador', 'valor_dinero', 'penalizacion_dinero', 'penalizacion_puntos'))
        legacy = [{key: str(value) if key in ('valor_dinero', 'penalizacion_dinero') else value
                   for key, value in item.items()} for item in legacy]
        if not before and not legacy and not record.penalizacion_dinero_clausulas and not record.penalizacion_puntos_clausulas:
            continue
        audit.objects.using(alias).create(
            usuario_id=record.user_access.user_id, division=record.division,
            season=record.season, jornada=record.jornada,
            accion='Retirar cláusulas erróneas J1 Segunda',
            detalle={'motivo': 'Corrección solicitada por Rafael: no hubo cláusulas ejecutadas en esta jornada.',
                     'origen': 'Migración de corrección; no acción del usuario vinculado al registro',
                     'registro_id': record.pk, 'clausulas_antes': before, 'clausulas_legacy': legacy,
                     'penalizacion_dinero_antes': str(record.penalizacion_dinero_clausulas),
                     'penalizacion_puntos_antes': record.penalizacion_puntos_clausulas})
        record.datos = data
        record.penalizacion_dinero_clausulas = 0
        record.penalizacion_puntos_clausulas = 0
        # Keep closed status and timestamps: do not promote an older owner's copy to latest.
        record.save(using=alias, update_fields=['datos', 'penalizacion_dinero_clausulas', 'penalizacion_puntos_clausulas'])
        clauses.objects.using(alias).filter(jornada_id=record.pk).delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0022_rename_emcasa_donatelo')]
    operations = [migrations.RunPython(clear_clauses, migrations.RunPython.noop)]
