"""Remove the non-participant's empty league records, stopping on conflicts."""
from django.db import migrations


def remove_nonparticipant(apps, schema_editor):
    alias = schema_editor.connection.alias
    name, division = 'Patontografos F.C', 'Primera RFEF'
    records = apps.get_model('core', 'JornadaRegistro').objects.using(alias).filter(division=division)
    votes = apps.get_model('core', 'VotoPartidoVIP').objects.using(alias)
    draws = apps.get_model('core', 'CopaReySorteo').objects.using(alias)
    # Never silently remove results or another manager's clauses or point allocations.
    for vote in votes.filter(division=division):
        if (vote.manager == name or vote.objetivo_penalizacion == name
                or name in (vote.penalizaciones_objetivo or {})):
            raise RuntimeError('Patontografos tiene votos o repartos VIP; revisar antes de eliminar.')
    for draw in draws.all():
        if any(p.get('division') == division and p.get('manager') == name for p in draw.participantes):
            raise RuntimeError('Patontografos aparece en un cuadro de Copa; revisar antes de eliminar.')
    for record in records:
        for manager, row in (record.datos or {}).items():
            if not isinstance(row, dict):
                raise RuntimeError('Hay datos de jornada no válidos; revisar antes de eliminar.')
            if manager == name:
                if (row.get('clauses') or any(str(row.get(k) or '').strip() not in ('', '0', '0 €', '0.00')
                                             for k in ('app', 'p', 'q', 'money', 'penalty'))):
                    raise RuntimeError('Patontografos tiene datos de jornada no vacíos; revisar antes de eliminar.')
            elif any(c.get('to', c.get('by')) == name for c in row.get('clauses', []) if isinstance(c, dict)):
                raise RuntimeError('Hay cláusulas de otro manager dirigidas a Patontografos; revisar antes de eliminar.')
    for record in records:
        if name in (record.datos or {}):
            data = dict(record.datos)
            del data[name]
            record.datos = data
            record.save(update_fields=['datos'])
    apps.get_model('core', 'ManagerLiga').objects.using(alias).filter(division=division, manager=name).delete()
    apps.get_model('core', 'ContactoManager').objects.using(alias).filter(division=division, manager=name).delete()
    apps.get_model('core', 'CodigoEmergenciaVIP').objects.using(alias).filter(division=division, manager=name).delete()
    apps.get_model('core', 'CambioRegistro').objects.using(alias).filter(division=division, accion='Baja de Patontografos F.C').delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0028_correct_copa_2026_draw')]
    operations = [migrations.RunPython(remove_nonparticipant, migrations.RunPython.noop)]
