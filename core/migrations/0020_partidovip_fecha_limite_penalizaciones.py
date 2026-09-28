from datetime import datetime

from django.db import migrations, models
from django.utils import timezone


def asignar_plazo_partidos_existentes(apps, schema_editor):
    PartidoVIP = apps.get_model('core', 'PartidoVIP')
    deadline = timezone.make_aware(datetime(2026, 9, 30, 23, 59))
    PartidoVIP.objects.filter(fecha_limite_penalizaciones__isnull=True).update(
        fecha_limite_penalizaciones=deadline
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0019_sugerencia_analisis')]

    operations = [
        migrations.AddField(
            model_name='partidovip',
            name='fecha_limite_penalizaciones',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(asignar_plazo_partidos_existentes, migrations.RunPython.noop),
    ]
