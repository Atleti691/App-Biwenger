from django.db import migrations


def corregir_voto_alexjulio(apps, schema_editor):
    VotoPartidoVIP = apps.get_model('core', 'VotoPartidoVIP')
    VotoPartidoVIP.objects.filter(
        partido_id=1,
        division='Primera División',
        manager='AlexJulio',
    ).update(
        posicionamiento='visitante',
        pronostico_goles='3+',
        origen='correccion_admin',
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0012_votopartidovip_penalizaciones_objetivo')]
    operations = [
        migrations.RunPython(corregir_voto_alexjulio, migrations.RunPython.noop),
    ]
