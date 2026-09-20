from django.db import migrations, models


def asignar_jornada_siete(apps, schema_editor):
    PartidoVIP = apps.get_model('core', 'PartidoVIP')
    PartidoVIP.objects.filter(pk=1, jornada__isnull=True).update(jornada=7)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_votosvip_manual_y_autorizacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='partidovip',
            name='jornada',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(asignar_jornada_siete, migrations.RunPython.noop),
    ]
