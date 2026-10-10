"""Requested retirement: preserve results, remove active roster and mailing contact."""
from django.db import migrations


def retire_manager(apps, schema_editor):
    alias = schema_editor.connection.alias
    manager_model = apps.get_model('core', 'ManagerLiga')
    contact_model = apps.get_model('core', 'ContactoManager')
    audit_model = apps.get_model('core', 'CambioRegistro')
    user_model = apps.get_model('auth', 'User')
    division, name = 'Primera RFEF', 'Patontografos F.C'
    managers = manager_model.objects.using(alias).filter(season=2026, division=division, manager=name)
    contacts = contact_model.objects.using(alias).filter(division=division, manager=name)
    contact_backup = list(contacts.values('id', 'division', 'manager', 'email', 'provincia'))
    active_ids = list(managers.filter(activo=True).values_list('id', flat=True))
    if not contact_backup and not active_ids:
        return
    actor = user_model.objects.using(alias).filter(username__iexact='Atleti69').first()
    # Do not remove personal contact details unless there is a recoverable audit.
    if contact_backup and not actor:
        raise RuntimeError('No se puede archivar el contacto sin el superadministrador Atleti69.')
    if actor:
        audit_model.objects.using(alias).create(
            usuario_id=actor.pk, division=division, season=2026, jornada=0,
            accion='Baja de Patontografos F.C',
            detalle={'motivo': 'Retirada de la liga solicitada por Rafael.',
                     'origen': 'Migración de baja solicitada; no inicio de sesión del usuario registrado.',
                     'manager': name, 'managers_activos_antes': active_ids,
                     'contactos_archivados': contact_backup,
                     'historial_y_cuenta_conservados': True})
    managers.update(activo=False)
    contacts.delete()


class Migration(migrations.Migration):
    dependencies = [('core', '0023_clear_second_division_j1_clauses')]
    operations = [migrations.RunPython(retire_manager, migrations.RunPython.noop)]
