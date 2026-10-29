"""Remove the expiry only for the account explicitly authorised by Rafael."""
from django.db import migrations


def clear_checo_expiry(apps, schema_editor):
    alias = schema_editor.connection.alias
    Access = apps.get_model('core', 'UserAccess')
    User = apps.get_model('auth', 'User')
    Audit = apps.get_model('core', 'CambioRegistro')
    accounts = Access.objects.using(alias).filter(user__username__iexact='Checo21',
        user__is_active=True, role='viewer', access_expires_at__isnull=False).select_related('user')
    if not accounts.exists():
        return
    actor = User.objects.using(alias).filter(username__iexact='Atleti69').first()
    if not actor:
        raise RuntimeError('No se puede quitar la caducidad de Checo21 sin registrar la autorización de Atleti69.')
    for account in accounts:
        Audit.objects.using(alias).create(usuario_id=actor.pk, jornada=0,
            accion='quitar caducidad de acceso', detalle={'usuario': account.user.username,
                'caducidad_anterior': account.access_expires_at.isoformat(), 'caducidad_nueva': None,
                'origen': 'Migración solicitada expresamente por Rafael el 29/10/2026',
                'perfil_y_contrasena_conservados': True})
        Access.objects.using(alias).filter(pk=account.pk).update(access_expires_at=None)


class Migration(migrations.Migration):
    dependencies = [('core', '0026_complete_clasico_display')]
    operations = [migrations.RunPython(clear_checo_expiry, migrations.RunPython.noop)]
