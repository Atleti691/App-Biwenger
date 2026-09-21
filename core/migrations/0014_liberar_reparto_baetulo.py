from django.db import migrations


def liberar_reparto_incompleto(apps, schema_editor):
    VotoPartidoVIP = apps.get_model('core', 'VotoPartidoVIP')
    for voto in VotoPartidoVIP.objects.filter(manager__iexact='Baetulo'):
        reparto = voto.penalizaciones_objetivo or {}
        if reparto and sum(int(puntos or 0) for puntos in reparto.values()) < 50:
            voto.penalizaciones_objetivo = {}
            voto.objetivo_penalizacion = ''
            voto.save(update_fields=['penalizaciones_objetivo', 'objetivo_penalizacion'])


class Migration(migrations.Migration):
    dependencies = [('core', '0013_corregir_voto_alexjulio_vip')]
    operations = [
        migrations.RunPython(liberar_reparto_incompleto, migrations.RunPython.noop),
    ]
