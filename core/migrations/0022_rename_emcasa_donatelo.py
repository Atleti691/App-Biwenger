from django.db import migrations

DIVISION = 'Segunda División'


def is_old(name):
    return isinstance(name, str) and name.replace(' ', '').casefold() == 'emcasa'


def rename_json(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            new_key = 'Donatelo' if is_old(key) else key
            if new_key in result:
                raise RuntimeError('Existen datos de eMCasa y Donatelo en el mismo registro; revisar antes de unirlos.')
            result[new_key] = rename_json(item)
        return result
    if isinstance(value, list):
        return [rename_json(item) for item in value]
    return 'Donatelo' if is_old(value) else value


def rename_manager(apps, schema_editor):
    alias = schema_editor.connection.alias
    for model_name, unique_fields in (
        ('ManagerLiga', ['season', 'division']), ('ContactoManager', ['division']),
        ('VotoPartidoVIP', ['partido_id', 'division']), ('CodigoEmergenciaVIP', []),
    ):
        model = apps.get_model('core', model_name)
        for row in model.objects.using(alias).filter(division=DIVISION):
            if not is_old(row.manager):
                continue
            if unique_fields and model.objects.using(alias).filter(
                manager='Donatelo', **{key: getattr(row, key) for key in unique_fields},
            ).exclude(pk=row.pk).exists():
                raise RuntimeError(f'Donatelo ya existe en {model_name}; no se sobrescriben sus datos.')
            row.manager = 'Donatelo'
            row.save(using=alias, update_fields=['manager'])
    records = apps.get_model('core', 'JornadaRegistro')
    for row in records.objects.using(alias).filter(division=DIVISION):
        updated = rename_json(row.datos)
        if updated != row.datos:
            row.datos = updated
            row.save(using=alias, update_fields=['datos'])
    votes = apps.get_model('core', 'VotoPartidoVIP')
    for row in votes.objects.using(alias).filter(division=DIVISION):
        fields = []
        if is_old(row.objetivo_penalizacion):
            row.objetivo_penalizacion = 'Donatelo'
            fields.append('objetivo_penalizacion')
        updated = rename_json(row.penalizaciones_objetivo)
        if updated != row.penalizaciones_objetivo:
            row.penalizaciones_objetivo = updated
            fields.append('penalizaciones_objetivo')
        if fields:
            row.save(using=alias, update_fields=fields)
    draws = apps.get_model('core', 'CopaReySorteo')
    for row in draws.objects.using(alias).all():
        updated = [rename_json(person) if person.get('division') == DIVISION else person for person in row.participantes]
        if updated != row.participantes:
            row.participantes = updated
            row.save(using=alias, update_fields=['participantes'])
    # Authentication, passwords, permissions and historical audit entries stay unchanged.


class Migration(migrations.Migration):
    dependencies = [('core', '0021_copareysorteo')]
    operations = [migrations.RunPython(rename_manager, migrations.RunPython.noop)]
