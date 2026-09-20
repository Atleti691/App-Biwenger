from django.db import migrations, models


def migrar_penalizaciones(apps, schema_editor):
    VotoPartidoVIP = apps.get_model('core', 'VotoPartidoVIP')
    for voto in VotoPartidoVIP.objects.exclude(objetivo_penalizacion=''):
        voto.penalizaciones_objetivo = {voto.objetivo_penalizacion: 50}
        voto.save(update_fields=['penalizaciones_objetivo'])


class Migration(migrations.Migration):
    dependencies = [('core', '0011_partidovip_jornada')]
    operations = [
        migrations.AddField(
            model_name='votopartidovip',
            name='penalizaciones_objetivo',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(migrar_penalizaciones, migrations.RunPython.noop),
    ]
